"""结构化抽取模块

从用户描述文本中抽取节点、边和状态信息。
使用单次LLM调用完成全部抽取（原4次合并为1次）。
"""

import json
import re
import uuid
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field
from pdca.core.logger import get_logger
from pdca.core.llm import OpenAILLM, get_llm_manager, get_llm_for_task
from pdca.core.utils import parse_json_response
from pdca.core.prompts import SYSTEM_PROMPTS, EXTRACT_PROMPT

logger = get_logger(__name__)


# ============== 数据模型 ==============

class ExtractedNode(BaseModel):
    """抽取出的节点"""
    node_id: str = Field(..., description="节点唯一标识")
    name: str = Field(..., description="节点名称")
    type: str = Field(..., description="节点类型: tool/thought/control")
    description: Optional[str] = Field(default=None, description="节点功能描述")
    inputs: list[str] = Field(default_factory=list, description="输入参数列表")
    outputs: list[str] = Field(default_factory=list, description="输出参数列表")
    config: dict[str, Any] = Field(default_factory=dict, description="节点配置")


class ExtractedEdge(BaseModel):
    """抽取出的边"""
    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    condition: Optional[str] = Field(default=None, description="条件表达式")
    type: str = Field(default="sequential", description="边类型: sequential/conditional/parallel")


class ExtractedState(BaseModel):
    """抽取出的状态"""
    field_name: str = Field(..., description="状态字段名称")
    type: str = Field(..., description="字段类型")
    default_value: Any = Field(default=None, description="默认值")
    description: Optional[str] = Field(default=None, description="字段描述")
    required: bool = Field(default=False, description="是否必填")


class StructuredDocument(BaseModel):
    """结构化抽取结果文档"""
    nodes: list[ExtractedNode] = Field(default_factory=list, description="节点列表")
    edges: list[ExtractedEdge] = Field(default_factory=list, description="边列表")
    states: list[ExtractedState] = Field(default_factory=list, description="状态列表")
    raw_text: str = Field(..., description="原始输入文本")
    missing_info: list[str] = Field(default_factory=list, description="缺失信息列表")


class ClarificationQuestion(BaseModel):
    """澄清问题"""
    question: str = Field(..., description="问题内容")
    related_field: Optional[str] = Field(default=None, description="关联字段")
    priority: str = Field(default="medium", description="优先级: high/medium/low")


# ============== JSON 加载器 ==============

_NODE_TYPE_MAP: dict[str, str] = {
    "tool_node": "tool",
    "thinking_node": "thought",
    "control_node": "control",
}

_EDGE_TYPE_MAP: dict[str, str] = {
    "sequential": "sequential",
    "conditional": "conditional",
    "parallel": "parallel",
    "loop": "loop",
    "error": "error",
}


class JSONLoader:
    """从 prompt-to-langgraph 技能输出的 JSON 文件加载结构化文档"""

    def load(self, json_path: Path) -> StructuredDocument:
        """加载 JSON 文件并转换为 StructuredDocument"""
        logger.info("json_loader_start", path=str(json_path))

        if not json_path.exists():
            raise FileNotFoundError(f"JSON 文件不存在: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        config = data.get("config", {})
        analysis = data.get("analysis", {})

        if not config:
            raise ValueError("JSON 缺少 config 顶层键")

        nodes = self._map_nodes(config.get("nodes", []))
        edges = self._map_edges(config.get("edges", []))
        states = self._map_states(config.get("state_schema", {}).get("fields", []))
        raw_text = config.get("metadata", {}).get("source_input", "")
        missing_info = [
            f"{a.get('type', '未知')}: {a.get('question', '')}"
            for a in analysis.get("ambiguities", [])
        ]

        document = StructuredDocument(
            nodes=nodes, edges=edges, states=states,
            raw_text=raw_text, missing_info=missing_info,
        )
        logger.info("json_loader_complete", node_count=len(nodes), edge_count=len(edges))
        return document

    def _map_nodes(self, raw_nodes: list[dict]) -> list[ExtractedNode]:
        nodes = []
        for raw in raw_nodes:
            node_type = _NODE_TYPE_MAP.get(raw.get("node_type", "tool_node"), "tool")
            inputs = [f["name"] for f in raw.get("input_schema", {}).get("fields", []) if "name" in f]
            outputs = [f["name"] for f in raw.get("output_schema", {}).get("fields", []) if "name" in f]
            extra = {k: v for k, v in raw.items() if k in {"node_subtype", "metadata", "input_schema", "output_schema"}}
            nodes.append(ExtractedNode(
                node_id=raw.get("node_id", f"node_{uuid.uuid4().hex[:8]}"),
                name=raw.get("node_name", "未命名节点"),
                type=node_type,
                description=raw.get("description"),
                inputs=inputs, outputs=outputs, config=extra,
            ))
        return nodes

    def _map_edges(self, raw_edges: list[dict]) -> list[ExtractedEdge]:
        edges = []
        for raw in raw_edges:
            edge_type = _EDGE_TYPE_MAP.get(raw.get("edge_type", "sequential"), "sequential")
            edges.append(ExtractedEdge(
                source=raw.get("source", ""),
                target=raw.get("target", ""),
                condition=raw.get("condition"),
                type=edge_type,
            ))
        return edges

    def _map_states(self, raw_fields: list[dict]) -> list[ExtractedState]:
        return [
            ExtractedState(
                field_name=raw.get("name", ""),
                type=raw.get("type", "string"),
                default_value=raw.get("default_value"),
                description=raw.get("description"),
                required=raw.get("required", False),
            )
            for raw in raw_fields
        ]


# ============== 核心抽取函数 ==============

def _build_document(text: str, data: dict) -> StructuredDocument:
    """从LLM返回的JSON数据构建StructuredDocument"""
    nodes = []
    for n in data.get("nodes", []):
        nodes.append(ExtractedNode(
            node_id=f"node_{uuid.uuid4().hex[:8]}",
            name=n.get("name", "未命名节点"),
            type=n.get("type", "tool"),
            description=n.get("description"),
            inputs=n.get("inputs", []),
            outputs=n.get("outputs", []),
            config={},
        ))

    # 建立节点名称→ID映射
    node_name_to_id = {n.name: n.node_id for n in nodes}

    edges = []
    for e in data.get("edges", []):
        source_name = e.get("source", "")
        target_name = e.get("target", "")
        source_id = node_name_to_id.get(source_name, source_name)
        target_id = node_name_to_id.get(target_name, target_name)
        edges.append(ExtractedEdge(
            source=source_id,
            target=target_id,
            condition=e.get("condition"),
            type=e.get("type", "sequential"),
        ))

    states = [
        ExtractedState(
            field_name=s.get("field_name", "unknown"),
            type=s.get("type", "string"),
            default_value=s.get("default_value"),
            description=s.get("description"),
            required=s.get("required", False),
        )
        for s in data.get("states", [])
    ]

    return StructuredDocument(
        nodes=nodes, edges=edges, states=states,
        raw_text=text,
        missing_info=data.get("missing_info", []),
    )


def _fallback_extract(text: str) -> StructuredDocument:
    """LLM失败时的简单正则抽取"""
    logger.warning("using_fallback_extraction")
    patterns = [
        r'(?:首先|先|第一|接着|然后|之后|随后|最后|最终)([^\n，。！？]+)',
        r'([^\n，。！？]+(?:调用|执行|运行|使用|获取|查询|分析|判断|生成|创建|开始|结束))',
    ]
    phrases = []
    for pattern in patterns:
        phrases.extend(re.findall(pattern, text))

    seen = set()
    unique = []
    for p in phrases:
        p = p.strip()
        if p and p not in seen and len(p) >= 2:
            seen.add(p)
            unique.append(p)

    control_kw = ['开始', '结束', '终止', '如果', '当', '则', '分支', '循环']
    thought_kw = ['分析', '思考', '判断', '评估', '总结', '推理', '理解', '识别']

    nodes = []
    for phrase in unique[:10]:
        node_type = 'control' if any(kw in phrase for kw in control_kw) else \
                    'thought' if any(kw in phrase for kw in thought_kw) else 'tool'
        nodes.append(ExtractedNode(
            node_id=f"node_{uuid.uuid4().hex[:8]}",
            name=phrase[:20], type=node_type,
            description=f"从文本抽取: {phrase}",
            inputs=[], outputs=[], config={},
        ))

    # 顺序连接
    edges = [
        ExtractedEdge(source=nodes[i].node_id, target=nodes[i+1].node_id, type="sequential")
        for i in range(len(nodes) - 1)
    ]

    return StructuredDocument(
        nodes=nodes, edges=edges,
        states=[
            ExtractedState(field_name="inputText", type="string", default_value="", description="用户输入文本", required=True),
            ExtractedState(field_name="result", type="any", description="处理结果", required=True),
        ],
        raw_text=text,
    )


# ============== 公共 API ==============

class StructuredExtractor:
    """结构化抽取器 — 单次LLM调用完成全部抽取"""

    def __init__(
        self,
        llm: Optional[OpenAILLM] = None,
        json_path: Optional[Path] = None,
    ):
        self.llm = llm
        self.json_path = json_path

    def extract(self, text: str) -> StructuredDocument:
        """执行完整的结构化抽取"""
        # Dev-time: 从JSON文件加载
        if self.json_path and self.json_path.exists():
            logger.info("structured_extraction_from_json", path=str(self.json_path))
            return JSONLoader().load(self.json_path)

        logger.info("structured_extraction_start", text_length=len(text))

        llm = self.llm or get_llm_for_task("extract")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["extract"]},
            {"role": "user", "content": EXTRACT_PROMPT.format(text=text)},
        ]

        try:
            response = llm.generate_messages(messages)
            data = parse_json_response(response)
            if data:
                document = _build_document(text, data)
                logger.info("structured_extraction_complete",
                           node_count=len(document.nodes),
                           edge_count=len(document.edges))
                return document
        except Exception as e:
            logger.error("llm_extraction_failed", error=str(e))

        return _fallback_extract(text)


def extract_structure(
    text: str,
    llm: Optional[OpenAILLM] = None,
    json_path: Optional[Path] = None,
) -> StructuredDocument:
    """快速执行结构化抽取"""
    return StructuredExtractor(llm, json_path=json_path).extract(text)


def extract_with_clarification(
    text: str,
    llm: Optional[OpenAILLM] = None,
    json_path: Optional[Path] = None,
) -> tuple[StructuredDocument, list[ClarificationQuestion]]:
    """抽取并生成澄清问题"""
    document = extract_structure(text, llm, json_path)

    # 基于缺失信息生成澄清问题
    questions = [
        ClarificationQuestion(question=info, priority="medium")
        for info in document.missing_info
    ]

    # 补充检查：无描述的节点
    for node in document.nodes:
        if not node.description or "从文本抽取" in (node.description or ""):
            questions.append(ClarificationQuestion(
                question=f"请详细描述节点「{node.name}」的具体功能",
                related_field=f"node:{node.node_id}",
                priority="high",
            ))

    # 补充检查：无条件表达式的条件边
    for edge in document.edges:
        if edge.type == 'conditional' and not edge.condition:
            questions.append(ClarificationQuestion(
                question=f"请说明条件边的判断逻辑",
                related_field=f"edge:{edge.source}->{edge.target}",
                priority="high",
            ))

    # 按优先级排序
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    questions.sort(key=lambda q: priority_order.get(q.priority, 1))

    return document, questions[:5]
