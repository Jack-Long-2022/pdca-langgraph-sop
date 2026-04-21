"""结构化抽取模块

从用户描述文本中抽取节点、边和状态信息
使用LLM进行深度推理，质量优先
"""

import json
import re
import uuid
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field
from pdca.core.logger import get_logger
from pdca.core.llm import get_llm_manager, BaseLLM

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


# ============== LLM节点抽取器 ==============

class NodeExtractor:
    """节点抽取器 - 使用LLM深度理解文本并抽取节点"""
    
    # Node type definitions for LLM
    NODE_TYPE_DEFINITIONS = {
        "tool": "执行具体操作，如调用API、处理数据、存储文件等",
        "thought": "进行思考、分析、判断、推理等活动",
        "control": "控制流程，如开始、结束、条件分支、循环等"
    }
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """初始化节点抽取器
        
        Args:
            llm: LLM实例，如果为None则使用默认LLM
        """
        self.llm = llm or get_llm_manager().get_llm()
    
    def extract(self, text: str) -> list[ExtractedNode]:
        """从文本中抽取节点（使用LLM推理）
        
        Args:
            text: 用户描述文本
        
        Returns:
            节点列表
        """
        logger.debug("extracting_nodes_with_llm", text_length=len(text))
        
        prompt = self._build_extraction_prompt(text)
        
        try:
            response = self.llm.generate(prompt)
            nodes = self._parse_llm_response(response, text)
            logger.info("nodes_extraction_complete", count=len(nodes))
            return nodes
        except Exception as e:
            logger.error("llm_extraction_failed", error=str(e))
            # Fallback to simple extraction
            return self._fallback_extract(text)
    
    def _build_extraction_prompt(self, text: str) -> str:
        """构建抽取Prompt"""
        return f"""你是一个工作流架构师，需要从用户描述中抽取节点。

用户描述：
{text}

请分析这段描述，识别出所有关键的工作流节点。对于每个节点，请确定：
1. 节点名称（简洁的动作描述）
2. 节点类型（tool/thought/control）
3. 节点功能描述
4. 输入参数（如有）
5. 输出参数（如有）

节点类型定义：
- tool: 执行具体操作（调用API、处理数据、存储文件等）
- thought: 进行思考分析（分析、判断、推理、总结等）
- control: 控制流程（开始、结束、条件分支、循环等）

请以JSON格式输出节点列表：
{{
    "nodes": [
        {{
            "name": "节点名称",
            "type": "tool|thought|control",
            "description": "节点功能描述",
            "inputs": ["参数1", "参数2"],
            "outputs": ["输出1"]
        }}
    ]
}}

只输出JSON，不要有其他内容。"""
    
    def _parse_llm_response(self, response: str, original_text: str) -> list[ExtractedNode]:
        """解析LLM响应"""
        try:
            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                nodes_data = data.get("nodes", [])
                
                nodes = []
                for node_data in nodes_data:
                    node = ExtractedNode(
                        node_id=f"node_{uuid.uuid4().hex[:8]}",
                        name=node_data.get("name", "未命名节点"),
                        type=node_data.get("type", "tool"),
                        description=node_data.get("description"),
                        inputs=node_data.get("inputs", []),
                        outputs=node_data.get("outputs", []),
                        config={}
                    )
                    nodes.append(node)
                
                return nodes
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", error=str(e))
        
        return self._fallback_extract(original_text)
    
    def _fallback_extract(self, text: str) -> list[ExtractedNode]:
        """备用抽取方法（简单正则）"""
        logger.warning("using_fallback_extraction")
        
        # 简单的动词短语提取
        patterns = [
            r'(?:首先|先|第一|接着|然后|之后|随后|最后|最终)([^\n，。！？]+)',
            r'([^\n，。！？]+(?:调用|执行|运行|使用|获取|查询|分析|判断|生成|创建|开始|结束))',
        ]
        
        phrases = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            phrases.extend(matches)
        
        # 去重
        seen = set()
        unique_phrases = []
        for p in phrases:
            p = p.strip()
            if p and p not in seen and len(p) >= 2:
                seen.add(p)
                unique_phrases.append(p)
        
        nodes = []
        for i, phrase in enumerate(unique_phrases[:10]):  # 最多10个节点
            node_type = self._infer_node_type(phrase)
            nodes.append(ExtractedNode(
                node_id=f"node_{uuid.uuid4().hex[:8]}",
                name=phrase[:20],
                type=node_type,
                description=f"从文本抽取: {phrase}",
                inputs=[],
                outputs=[],
                config={}
            ))
        
        return nodes
    
    def _infer_node_type(self, text: str) -> str:
        """推理节点类型"""
        text_lower = text.lower()
        
        control_keywords = ['开始', '结束', '终止', '如果', '当', '则', '分支', '循环']
        for kw in control_keywords:
            if kw in text:
                return 'control'
        
        thought_keywords = ['分析', '思考', '判断', '评估', '总结', '推理', '理解', '识别']
        for kw in thought_keywords:
            if kw in text:
                return 'thought'
        
        return 'tool'


# ============== LLM边抽取器 ==============

class EdgeExtractor:
    """边抽取器 - 使用LLM理解节点间关系"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """初始化边抽取器
        
        Args:
            llm: LLM实例，如果为None则使用默认LLM
        """
        self.llm = llm or get_llm_manager().get_llm()
    
    def extract(self, text: str, nodes: list[ExtractedNode]) -> list[ExtractedEdge]:
        """从文本和节点列表中抽取边（使用LLM推理）
        
        Args:
            text: 用户描述文本
            nodes: 节点列表
        
        Returns:
            边列表
        """
        logger.debug("extracting_edges_with_llm", text_length=len(text), node_count=len(nodes))
        
        if len(nodes) < 2:
            logger.warning("insufficient_nodes_for_edges", node_count=len(nodes))
            return []
        
        # 构建节点信息
        node_info = "\n".join([
            f"- {i+1}. {n.name} ({n.type}): {n.description or '无'}"
            for i, n in enumerate(nodes)
        ])
        
        prompt = f"""你是一个工作流设计师，需要确定节点之间的连接关系。

节点列表：
{node_info}

用户原始描述：
{text}

请分析节点之间的逻辑关系，确定边的连接：
1. 边的源节点和目标节点
2. 边的类型（sequential/conditional/parallel）
3. 条件表达式（如果是条件边）

边类型定义：
- sequential: 顺序执行，A完成后执行B
- conditional: 条件执行，满足条件才执行
- parallel: 并行执行

请以JSON格式输出边列表：
{{
    "edges": [
        {{
            "source": "源节点名称",
            "target": "目标节点名称",
            "type": "sequential|conditional|parallel",
            "condition": "条件表达式（如果是条件边）"
        }}
    ]
}}

只输出JSON，不要有其他内容。"""
        
        try:
            response = self.llm.generate(prompt)
            edges = self._parse_llm_response(response, nodes)
            logger.info("edges_extraction_complete", count=len(edges))
            return edges
        except Exception as e:
            logger.error("llm_edge_extraction_failed", error=str(e))
            return self._fallback_extract(nodes)
    
    def _parse_llm_response(self, response: str, nodes: list[ExtractedNode]) -> list[ExtractedEdge]:
        """解析LLM响应"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                edges_data = data.get("edges", [])
                
                # 创建节点名称到节点的映射
                node_map = {n.name: n for n in nodes}
                
                edges = []
                for edge_data in edges_data:
                    source_name = edge_data.get("source", "")
                    target_name = edge_data.get("target", "")
                    
                    if source_name in node_map and target_name in node_map:
                        edges.append(ExtractedEdge(
                            source=node_map[source_name].node_id,
                            target=node_map[target_name].node_id,
                            condition=edge_data.get("condition"),
                            type=edge_data.get("type", "sequential")
                        ))
                
                return edges
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", error=str(e))
        
        return self._fallback_extract(nodes)
    
    def _fallback_extract(self, nodes: list[ExtractedNode]) -> list[ExtractedEdge]:
        """备用方法：创建顺序边"""
        logger.warning("using_fallback_edge_extraction")
        
        edges = []
        for i in range(len(nodes) - 1):
            edges.append(ExtractedEdge(
                source=nodes[i].node_id,
                target=nodes[i + 1].node_id,
                type='sequential'
            ))
        
        return edges


# ============== LLM状态抽取器 ==============

class StateExtractor:
    """状态抽取器 - 使用LLM识别数据对象和状态"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """初始化状态抽取器
        
        Args:
            llm: LLM实例，如果为None则使用默认LLM
        """
        self.llm = llm or get_llm_manager().get_llm()
    
    def extract(self, text: str) -> list[ExtractedState]:
        """从文本中抽取状态定义（使用LLM推理）
        
        Args:
            text: 用户描述文本
        
        Returns:
            状态列表
        """
        logger.debug("extracting_states_with_llm", text_length=len(text))
        
        prompt = f"""你是一个数据架构师，需要从工作流描述中识别状态和数据对象。

工作流描述：
{text}

请分析这个工作流需要管理的数据：
1. 输入数据（工作流开始时需要的数据）
2. 中间状态（工作流执行过程中产生的数据）
3. 输出数据（工作流完成时产生的结果）
4. 控制数据（循环次数、标志位等）

对于每个数据对象，请确定：
- 字段名称（英文，驼峰命名）
- 数据类型（string/integer/boolean/array/object）
- 默认值（如有）
- 是否必填

请以JSON格式输出状态列表：
{{
    "states": [
        {{
            "field_name": "字段名称",
            "type": "string|integer|boolean|array|object",
            "default_value": 默认值,
            "description": "字段描述",
            "required": true|false
        }}
    ]
}}

只输出JSON，不要有其他内容。"""
        
        try:
            response = self.llm.generate(prompt)
            states = self._parse_llm_response(response)
            logger.info("states_extraction_complete", count=len(states))
            return states
        except Exception as e:
            logger.error("llm_state_extraction_failed", error=str(e))
            return self._fallback_extract()
    
    def _parse_llm_response(self, response: str) -> list[ExtractedState]:
        """解析LLM响应"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                states_data = data.get("states", [])
                
                states = []
                for state_data in states_data:
                    states.append(ExtractedState(
                        field_name=state_data.get("field_name", "unknown"),
                        type=state_data.get("type", "string"),
                        default_value=state_data.get("default_value"),
                        description=state_data.get("description"),
                        required=state_data.get("required", False)
                    ))
                
                return states
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", error=str(e))
        
        return self._fallback_extract()
    
    def _fallback_extract(self) -> list[ExtractedState]:
        """备用方法：返回默认状态"""
        return [
            ExtractedState(
                field_name="inputText",
                type="string",
                default_value="",
                description="用户输入文本",
                required=True
            ),
            ExtractedState(
                field_name="result",
                type="any",
                description="处理结果",
                required=True
            )
        ]


# ============== JSON 加载器 ==============

# SKILL.md node_type → ExtractedNode.type 映射
_NODE_TYPE_MAP: dict[str, str] = {
    "tool_node": "tool",
    "thinking_node": "thought",
    "control_node": "control",
}

# SKILL.md edge_type → ExtractedEdge.type 映射
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
        """加载 JSON 文件并转换为 StructuredDocument

        Args:
            json_path: JSON 文件路径

        Returns:
            结构化文档

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: JSON 格式不符合预期
        """
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
        missing_info = self._extract_missing_info(analysis.get("ambiguities", []))

        document = StructuredDocument(
            nodes=nodes,
            edges=edges,
            states=states,
            raw_text=raw_text,
            missing_info=missing_info,
        )

        logger.info(
            "json_loader_complete",
            node_count=len(nodes),
            edge_count=len(edges),
            state_count=len(states),
        )
        return document

    def _map_nodes(self, raw_nodes: list[dict]) -> list[ExtractedNode]:
        """映射 SKILL JSON 节点到 ExtractedNode"""
        nodes = []
        for raw in raw_nodes:
            node_type = _NODE_TYPE_MAP.get(
                raw.get("node_type", "tool_node"), "tool"
            )
            inputs = [
                f["name"]
                for f in raw.get("input_schema", {}).get("fields", [])
                if "name" in f
            ]
            outputs = [
                f["name"]
                for f in raw.get("output_schema", {}).get("fields", [])
                if "name" in f
            ]
            # 额外字段保留到 config
            extra_keys = {
                "node_subtype",
                "metadata",
                "input_schema",
                "output_schema",
            }
            extra = {k: v for k, v in raw.items() if k in extra_keys}

            nodes.append(
                ExtractedNode(
                    node_id=raw.get("node_id", f"node_{uuid.uuid4().hex[:8]}"),
                    name=raw.get("node_name", "未命名节点"),
                    type=node_type,
                    description=raw.get("description"),
                    inputs=inputs,
                    outputs=outputs,
                    config=extra,
                )
            )
        return nodes

    def _map_edges(self, raw_edges: list[dict]) -> list[ExtractedEdge]:
        """映射 SKILL JSON 边到 ExtractedEdge"""
        edges = []
        for raw in raw_edges:
            edge_type = _EDGE_TYPE_MAP.get(
                raw.get("edge_type", "sequential"), "sequential"
            )
            edges.append(
                ExtractedEdge(
                    source=raw.get("source", ""),
                    target=raw.get("target", ""),
                    condition=raw.get("condition"),
                    type=edge_type,
                )
            )
        return edges

    def _map_states(self, raw_fields: list[dict]) -> list[ExtractedState]:
        """映射 SKILL JSON 状态字段到 ExtractedState"""
        states = []
        for raw in raw_fields:
            states.append(
                ExtractedState(
                    field_name=raw.get("name", ""),
                    type=raw.get("type", "string"),
                    default_value=raw.get("default_value"),
                    description=raw.get("description"),
                    required=raw.get("required", False),
                )
            )
        return states

    def _extract_missing_info(self, ambiguities: list[dict]) -> list[str]:
        """从 analysis.ambiguities 提取缺失信息"""
        return [
            f"{a.get('type', '未知')}: {a.get('question', '')}"
            for a in ambiguities
        ]


# ============== 结构化抽取总控 ==============

class StructuredExtractor:
    """结构化抽取总控 - 协调三个LLM抽取器"""

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        json_path: Optional[Path] = None,
    ):
        """初始化结构化抽取器

        Args:
            llm: LLM实例，如果为None则使用默认LLM
            json_path: 技能输出的 JSON 文件路径，存在时优先加载
        """
        self.llm = llm
        self.json_path = json_path
        self.node_extractor = NodeExtractor(llm)
        self.edge_extractor = EdgeExtractor(llm)
        self.state_extractor = StateExtractor(llm)

    def extract(self, text: str) -> StructuredDocument:
        """执行完整的结构化抽取（使用LLM推理）

        优先从 json_path 加载（Dev-time），否则走LLM抽取。

        Args:
            text: 用户描述文本

        Returns:
            结构化文档
        """
        # Dev-time: 从技能输出的 JSON 文件加载
        if self.json_path and self.json_path.exists():
            logger.info(
                "structured_extraction_from_json",
                path=str(self.json_path),
            )
            return JSONLoader().load(self.json_path)

        # LLM抽取
        logger.info("structured_extraction_start", text_length=len(text))
        
        # 1. 抽取节点（LLM推理）
        nodes = self.node_extractor.extract(text)
        
        # 2. 抽取边（LLM推理）
        edges = self.edge_extractor.extract(text, nodes)
        
        # 3. 抽取状态（LLM推理）
        states = self.state_extractor.extract(text)
        
        # 4. 检查缺失信息
        missing_info = self._check_missing_info(text, nodes, edges, states)
        
        document = StructuredDocument(
            nodes=nodes,
            edges=edges,
            states=states,
            raw_text=text,
            missing_info=missing_info
        )
        
        logger.info("structured_extraction_complete",
                   node_count=len(nodes),
                   edge_count=len(edges),
                   state_count=len(states),
                   missing_count=len(missing_info))
        
        return document
    
    def _check_missing_info(
        self, 
        text: str, 
        nodes: list[ExtractedNode], 
        edges: list[ExtractedEdge], 
        states: list[ExtractedState]
    ) -> list[str]:
        """检查缺失信息"""
        missing = []
        
        if len(nodes) < 2:
            missing.append("节点数量不足，至少需要2个节点")
        
        if edges:
            node_ids = {n.node_id for n in nodes}
            connected = set()
            for edge in edges:
                connected.add(edge.source)
                connected.add(edge.target)
            
            if connected != node_ids:
                disconnected = node_ids - connected
                missing.append(f"存在未连接的节点: {disconnected}")
        
        if not states:
            missing.append("缺少状态定义")
        
        return missing


# ============== LLM澄清引导引擎 ==============

class ClarificationEngine:
    """澄清引导引擎 - 使用LLM智能识别信息缺失并生成澄清问题"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """初始化澄清引擎
        
        Args:
            llm: LLM实例，如果为None则使用默认LLM
        """
        self.llm = llm or get_llm_manager().get_llm()
    
    def identify_ambiguities(self, document: StructuredDocument) -> list[ClarificationQuestion]:
        """识别文档中的歧义（使用LLM深度分析）
        
        Args:
            document: 结构化文档
        
        Returns:
            澄清问题列表
        """
        # 构建文档摘要
        nodes_summary = "\n".join([
            f"- {n.name} ({n.type}): {n.description or '无描述'}"
            for n in document.nodes
        ])
        edges_summary = "\n".join([
            f"- {e.source} -> {e.target} ({e.type})"
            for e in document.edges
        ])
        states_summary = "\n".join([
            f"- {s.field_name} ({s.type}): {s.description or '无'}"
            for s in document.states
        ])
        
        prompt = f"""你是一个需求分析师，需要识别工作流设计中的信息缺失。

当前工作流结构：

节点：
{nodes_summary}

边：
{edges_summary}

状态：
{states_summary}

原始描述：
{document.raw_text}

请分析这个工作流设计中存在的歧义和缺失信息，生成澄清问题。重点关注：
1. 节点功能不明确的地方
2. 边连接逻辑不清楚的地方
3. 状态定义不完整的地方
4. 可能导致执行失败的条件

请以JSON格式输出澄清问题：
{{
    "questions": [
        {{
            "question": "问题内容",
            "related_field": "关联字段（如 node:xxx 或 edge:xxx）",
            "priority": "high|medium|low"
        }}
    ]
}}

只输出JSON，不要有其他内容。"""
        
        try:
            response = self.llm.generate(prompt)
            return self._parse_questions_response(response)
        except Exception as e:
            logger.error("llm_clarification_failed", error=str(e))
            return self._fallback_identify(document)
    
    def _parse_questions_response(self, response: str) -> list[ClarificationQuestion]:
        """解析LLM响应"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                questions_data = data.get("questions", [])
                
                questions = []
                for q_data in questions_data:
                    questions.append(ClarificationQuestion(
                        question=q_data.get("question", ""),
                        related_field=q_data.get("related_field"),
                        priority=q_data.get("priority", "medium")
                    ))
                
                return questions
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", error=str(e))
        
        return []
    
    def _fallback_identify(self, document: StructuredDocument) -> list[ClarificationQuestion]:
        """备用识别方法"""
        questions = []
        
        for node in document.nodes:
            if not node.description or "从文本抽取" in (node.description or ""):
                questions.append(ClarificationQuestion(
                    question=f"请详细描述节点「{node.name}」的具体功能",
                    related_field=f"node:{node.node_id}",
                    priority="high"
                ))
        
        for edge in document.edges:
            if edge.type == 'conditional' and not edge.condition:
                questions.append(ClarificationQuestion(
                    question=f"请说明节点间的条件判断逻辑",
                    related_field=f"edge:{edge.source}->{edge.target}",
                    priority="high"
                ))
        
        return questions[:5]
    
    def generate_questions(
        self, 
        document: StructuredDocument,
        max_questions: int = 5
    ) -> list[ClarificationQuestion]:
        """生成澄清问题
        
        Args:
            document: 结构化文档
            max_questions: 最大问题数量
        
        Returns:
            澄清问题列表
        """
        questions = self.identify_ambiguities(document)
        
        # 按优先级排序
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        questions.sort(key=lambda q: priority_order.get(q.priority, 1))
        
        return questions[:max_questions]


# ============== 便捷函数 ==============

def extract_structure(
    text: str,
    llm: Optional[BaseLLM] = None,
    json_path: Optional[Path] = None,
) -> StructuredDocument:
    """快速执行结构化抽取

    Args:
        text: 用户描述文本
        llm: LLM实例
        json_path: 技能输出的 JSON 文件路径

    Returns:
        结构化文档
    """
    extractor = StructuredExtractor(llm, json_path=json_path)
    return extractor.extract(text)


def extract_with_clarification(
    text: str,
    llm: Optional[BaseLLM] = None,
    json_path: Optional[Path] = None,
) -> tuple[StructuredDocument, list[ClarificationQuestion]]:
    """抽取并生成澄清问题

    Args:
        text: 用户描述文本
        llm: LLM实例
        json_path: 技能输出的 JSON 文件路径

    Returns:
        (结构化文档, 澄清问题列表)
    """
    extractor = StructuredExtractor(llm, json_path=json_path)
    document = extractor.extract(text)
    
    clarifier = ClarificationEngine(llm)
    questions = clarifier.generate_questions(document)
    
    return document, questions