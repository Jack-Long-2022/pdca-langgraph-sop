"""PDCA 可复用组件库

将工作流中的节点、边、状态和提示词沉淀为可复用模板：
- 每次生成工作流后自动保存组件模板
- 新建工作流时查找已有模板进行复用
- 在 GRRAVP 复盘中识别并固化可复用知识

使用方法：
    from pdca.core.component_library import ComponentLibrary

    library = ComponentLibrary(library_dir=".pdca_components")
    # 查找相似节点
    match = library.lookup_node("获取API数据", "从外部API获取数据")
    # 保存新节点
    library.save_node(node_definition, workflow_name="my_workflow")
"""

import json
import re
import hashlib
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from pdca.core.logger import get_logger
from pdca.core.utils import parse_json_response

logger = get_logger(__name__)


# ============== 数据模型 ==============

class NodeTemplate(BaseModel):
    """节点模板"""
    template_id: str = Field(..., description="模板唯一标识")
    name: str = Field(..., description="节点名称")
    name_keywords: list[str] = Field(default_factory=list, description="名称关键词（用于匹配）")
    type: str = Field(..., description="节点类型: tool/thought/control")
    description: str = Field(default="", description="节点功能描述")
    inputs: list[str] = Field(default_factory=list, description="输入参数")
    outputs: list[str] = Field(default_factory=list, description="输出参数")
    config: Dict[str, Any] = Field(default_factory=dict, description="节点配置")
    source_workflow: str = Field(default="", description="来源工作流")
    usage_count: int = Field(default=0, description="复用次数")
    last_used: str = Field(default="", description="最后使用时间")
    created_at: str = Field(default="", description="创建时间")


class EdgeTemplate(BaseModel):
    """边模板"""
    template_id: str = Field(..., description="模板唯一标识")
    source_type: str = Field(..., description="源节点类型关键词")
    target_type: str = Field(..., description="目标节点类型关键词")
    edge_type: str = Field(default="sequential", description="边类型")
    condition: Optional[str] = Field(default=None, description="条件表达式")
    description: str = Field(default="", description="边描述")
    source_workflow: str = Field(default="", description="来源工作流")
    usage_count: int = Field(default=0, description="复用次数")
    last_used: str = Field(default="", description="最后使用时间")
    created_at: str = Field(default="", description="创建时间")


class StateTemplate(BaseModel):
    """状态模板"""
    template_id: str = Field(..., description="模板唯一标识")
    field_name: str = Field(..., description="字段名称")
    name_keywords: list[str] = Field(default_factory=list, description="名称关键词")
    type: str = Field(..., description="字段类型")
    default_value: Any = Field(default=None, description="默认值")
    description: str = Field(default="", description="字段描述")
    required: bool = Field(default=False, description="是否必填")
    source_workflow: str = Field(default="", description="来源工作流")
    usage_count: int = Field(default=0, description="复用次数")
    last_used: str = Field(default="", description="最后使用时间")
    created_at: str = Field(default="", description="创建时间")


class PromptTemplate(BaseModel):
    """提示词模板"""
    template_id: str = Field(..., description="模板唯一标识")
    task_type: str = Field(..., description="任务类型: extract/config/code/test/report/review")
    name: str = Field(..., description="提示词名称")
    content: str = Field(default="", description="提示词内容")
    name_keywords: list[str] = Field(default_factory=list, description="名称关键词")
    source_workflow: str = Field(default="", description="来源工作流")
    usage_count: int = Field(default=0, description="复用次数")
    last_used: str = Field(default="", description="最后使用时间")
    created_at: str = Field(default="", description="创建时间")


class ComponentLibraryIndex(BaseModel):
    """组件库索引 — 内存中的工作模型"""
    nodes: Dict[str, NodeTemplate] = Field(default_factory=dict)
    edges: Dict[str, EdgeTemplate] = Field(default_factory=dict)
    states: Dict[str, StateTemplate] = Field(default_factory=dict)
    prompts: Dict[str, PromptTemplate] = Field(default_factory=dict)
    saved_at: str = Field(default="")


class CatalogEntry(BaseModel):
    """轻量目录条目 — 用于渐进式加载"""
    id: str
    category: str  # node / edge / state / prompt
    name: str
    summary: str
    keywords: list[str] = Field(default_factory=list)


# ============== 关键词工具 ==============

# 常见中文停用词
_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会",
    "着", "没有", "看", "好", "自己", "这", "那", "他", "她", "它",
    "被", "从", "把", "对", "与", "而", "但", "如", "或", "等",
    # 英文停用词
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "and", "or", "not", "but",
}


def _extract_keywords(text: str) -> list[str]:
    """从文本中提取关键词（中英文混合处理）

    策略：
    1. 提取所有英文单词（长度>=2）
    2. 提取中文连续字符段，按常见连接词拆分为2-4字词组
    3. 过滤停用词
    """
    if not text:
        return []

    text = text.lower().strip()
    keywords = []

    # 1. 提取英文单词
    english_words = re.findall(r'[a-z][a-z0-9_]+', text)
    for word in english_words:
        if word not in _STOP_WORDS:
            keywords.append(word)

    # 2. 提取中文片段，按连接词和标点拆分
    # 先用英文/数字/标点将文本分割为纯中文片段
    chinese_segments = re.findall(r'[\u4e00-\u9fff]+', text)

    # 常见中文连接词（用于拆分长中文片段）
    connective_pattern = re.compile(r'[的得了在是与而又但或如果虽然]')

    for segment in chinese_segments:
        # 按连接词拆分
        sub_parts = connective_pattern.split(segment)
        for part in sub_parts:
            part = part.strip()
            if len(part) >= 2 and part not in _STOP_WORDS:
                # 对于较长的片段，提取2字窗口
                if len(part) <= 4:
                    keywords.append(part)
                else:
                    # 滑动窗口提取2字词
                    for i in range(len(part) - 1):
                        bigram = part[i:i+2]
                        if bigram not in _STOP_WORDS:
                            keywords.append(bigram)
            elif len(part) == 1 and part not in _STOP_WORDS:
                keywords.append(part)

    return keywords


def _keyword_match_score(query_keywords: list[str], template_keywords: list[str]) -> float:
    """关键词匹配评分 (Jaccard 风格)

    返回 0.0~1.0 的匹配分数
    """
    if not query_keywords:
        return 0.0

    query_set = set(kw.lower() for kw in query_keywords)
    template_set = set(kw.lower() for kw in template_keywords)

    if not template_set:
        return 0.0

    overlap = query_set & template_set
    return len(overlap) / len(query_set)


# ============== YAML 持久化 ==============

_TYPE_FILES = {
    "nodes": "nodes.yaml",
    "edges": "edges.yaml",
    "states": "states.yaml",
    "prompts": "prompts.yaml",
}

_MODEL_MAP = {
    "nodes": NodeTemplate,
    "edges": EdgeTemplate,
    "states": StateTemplate,
    "prompts": PromptTemplate,
}


def _load_yaml_file(filepath: Path) -> dict | None:
    """加载 YAML 文件，不存在返回 None"""
    if not filepath.exists():
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _save_yaml_file(filepath: Path, data: dict):
    """保存 YAML 文件（UTF-8，不转义中文）"""
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ============== 核心组件库 ==============

class ComponentLibrary:
    """可复用组件库

    功能：
    1. 积累：工作流生成后自动保存组件模板
    2. 检索：新建工作流时查找相似已有组件
    3. 固化：从 GRRAVP 复盘中识别可复用知识

    持久化目录结构：
        .pdca_components/
            catalog.yaml     # 轻量索引（name + summary + keywords）
            nodes.yaml       # 完整节点模板
            edges.yaml       # 完整边模板
            states.yaml      # 完整状态模板
            prompts.yaml     # 完整提示词模板
    """

    def __init__(
        self,
        library_dir: str = ".pdca_components",
        llm: Optional[Any] = None,
        enable_llm_matching: bool = False,
    ):
        self.library_dir = Path(library_dir)
        self.library_dir.mkdir(parents=True, exist_ok=True)
        self._llm = llm
        self.enable_llm_matching = enable_llm_matching
        self._load()

    # ============== 持久化 ==============

    def _load(self):
        """从磁盘加载（自动检测旧格式并迁移）"""
        # 检测旧版 index.json → 迁移
        legacy_file = self.library_dir / "index.json"
        if legacy_file.exists() and not (self.library_dir / "catalog.yaml").exists():
            self._migrate_from_json(legacy_file)
            return

        # 加载 per-type YAML 文件
        self._index = ComponentLibraryIndex()
        for type_name, file_name in _TYPE_FILES.items():
            data = _load_yaml_file(self.library_dir / file_name)
            if data and "templates" in data:
                model_class = _MODEL_MAP[type_name]
                collection = getattr(self._index, type_name)
                for tid, tdata in data["templates"].items():
                    collection[tid] = model_class(**tdata)

    def _save(self):
        """保存到磁盘（per-type YAML + catalog）"""
        now = datetime.now().isoformat()

        # 写 per-type 文件
        for type_name, file_name in _TYPE_FILES.items():
            collection = getattr(self._index, type_name)
            data = {
                "version": "2.0",
                "saved_at": now,
                "templates": {tid: t.model_dump() for tid, t in collection.items()},
            }
            _save_yaml_file(self.library_dir / file_name, data)

        # 写 catalog
        self._rebuild_and_save_catalog(now)

    def _rebuild_and_save_catalog(self, now: str = ""):
        """重建并保存轻量目录"""
        now = now or datetime.now().isoformat()
        entries = []

        for t in self._index.nodes.values():
            entries.append(CatalogEntry(
                id=t.template_id, category="node", name=t.name,
                summary=f"{t.description} ({t.type})" if t.description else f"({t.type})",
                keywords=t.name_keywords,
            ))
        for t in self._index.edges.values():
            entries.append(CatalogEntry(
                id=t.template_id, category="edge",
                name=f"{t.source_type} -> {t.target_type}",
                summary=f"{t.edge_type}" + (f" when {t.condition}" if t.condition else ""),
                keywords=_extract_keywords(f"{t.source_type} {t.target_type}"),
            ))
        for t in self._index.states.values():
            req = "required" if t.required else "optional"
            entries.append(CatalogEntry(
                id=t.template_id, category="state", name=t.field_name,
                summary=f"{t.type} ({req}) {t.description}".strip(),
                keywords=t.name_keywords,
            ))
        for t in self._index.prompts.values():
            entries.append(CatalogEntry(
                id=t.template_id, category="prompt", name=t.name,
                summary=f"[{t.task_type}] {t.name}",
                keywords=t.name_keywords,
            ))

        catalog_data = {
            "version": "2.0",
            "saved_at": now,
            "total_components": len(entries),
            "components": [e.model_dump() for e in entries],
        }
        _save_yaml_file(self.library_dir / "catalog.yaml", catalog_data)

    def _migrate_from_json(self, legacy_file: Path):
        """从旧版 index.json 迁移到 YAML 格式"""
        logger.info("migrating_component_library", source=str(legacy_file))
        with open(legacy_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self._index = ComponentLibraryIndex(**data)
        self._save()
        backup_path = legacy_file.rename(legacy_file.with_suffix(".json.bak"))
        logger.info("migration_complete", backup=str(backup_path))

    def _generate_id(self, prefix: str, name: str) -> str:
        """生成模板ID（与 memory.py 的 _generate_memory_id 模式一致）"""
        hash_input = f"{prefix}_{name}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    # ============== 查找方法（双层匹配） ==============

    def _should_use_llm(self, override: Optional[bool] = None) -> bool:
        """判断是否启用 LLM 匹配"""
        if override is not None:
            return override and self._llm is not None
        return self.enable_llm_matching and self._llm is not None

    def _llm_lookup(self, category: str, query: str, **kwargs) -> Optional[Any]:
        """Tier 2: LLM 语义匹配回退"""
        if not self._llm:
            return None

        # 从 catalog 读取候选
        catalog_data = _load_yaml_file(self.library_dir / "catalog.yaml")
        if not catalog_data:
            return None

        candidates = [
            e for e in catalog_data.get("components", [])
            if e.get("category") == category
        ]
        if not candidates:
            return None

        candidates_text = "\n".join(
            f"  - ID: {e['id']}, Name: {e['name']}, Summary: {e.get('summary', '')}"
            for e in candidates
        )

        from pdca.core.prompts import COMPONENT_LLM_MATCH_PROMPT
        prompt = COMPONENT_LLM_MATCH_PROMPT.format(
            category=category,
            query=query.strip(),
            candidates=candidates_text,
        )

        try:
            response = self._llm.generate_messages([
                {"role": "system", "content": "你是组件匹配专家。根据查询从候选组件中选择最佳匹配。输出严格的JSON。"},
                {"role": "user", "content": prompt},
            ])
            result = parse_json_response(response)
            if result and result.get("match_id"):
                match_id = result["match_id"]
                collection_map = {
                    "node": self._index.nodes,
                    "edge": self._index.edges,
                    "state": self._index.states,
                    "prompt": self._index.prompts,
                }
                collection = collection_map.get(category, {})
                match = collection.get(match_id)
                if match:
                    match.usage_count += 1
                    match.last_used = datetime.now().isoformat()
                    self._save()
                    logger.info("llm_component_matched",
                               category=category, match_id=match_id,
                               confidence=result.get("confidence", 0))
                    return match
        except Exception as e:
            logger.warning("llm_matching_failed", error=str(e))

        return None

    def lookup_node(
        self,
        name: str,
        description: str = "",
        node_type: Optional[str] = None,
        threshold: float = 0.3,
        use_llm: Optional[bool] = None,
    ) -> Optional[NodeTemplate]:
        """查找相似节点模板（双层匹配）

        Args:
            name: 节点名称
            description: 节点描述
            node_type: 可选，节点类型过滤
            threshold: 最低匹配阈值
            use_llm: 是否启用 LLM 语义回退（None=跟随全局设置）

        Returns:
            最佳匹配的 NodeTemplate，无匹配返回 None
        """
        # Tier 1: 关键词匹配
        query_keywords = _extract_keywords(f"{name} {description}")

        if query_keywords:
            candidates = list(self._index.nodes.values())
            if node_type:
                candidates = [n for n in candidates if n.type == node_type]

            best_match = None
            best_score = 0.0

            for template in candidates:
                score = _keyword_match_score(query_keywords, template.name_keywords)
                if node_type and template.type == node_type:
                    score += 0.1
                if score > best_score:
                    best_score = score
                    best_match = template

            if best_match and best_score >= threshold:
                best_match.usage_count += 1
                best_match.last_used = datetime.now().isoformat()
                self._save()
                logger.info("node_template_matched",
                           template=best_match.name, score=best_score,
                           query=name)
                return best_match

        # Tier 2: LLM 语义回退
        if self._should_use_llm(use_llm):
            return self._llm_lookup("node", f"{name} {description}",
                                    node_type=node_type)

        return None

    def lookup_edge(
        self,
        source_name: str,
        target_name: str,
        edge_type: Optional[str] = None,
        use_llm: Optional[bool] = None,
    ) -> Optional[EdgeTemplate]:
        """查找相似边模板（双层匹配）"""
        # Tier 1
        source_keywords = _extract_keywords(source_name)
        target_keywords = _extract_keywords(target_name)

        best_match = None
        best_score = 0.0

        for template in self._index.edges.values():
            if edge_type and template.edge_type != edge_type:
                continue

            source_score = _keyword_match_score(source_keywords, _extract_keywords(template.source_type))
            target_score = _keyword_match_score(target_keywords, _extract_keywords(template.target_type))
            score = (source_score + target_score) / 2

            if score > best_score:
                best_score = score
                best_match = template

        if best_match and best_score >= 0.3:
            best_match.usage_count += 1
            best_match.last_used = datetime.now().isoformat()
            self._save()
            return best_match

        # Tier 2
        if self._should_use_llm(use_llm):
            return self._llm_lookup("edge", f"{source_name} -> {target_name}",
                                    edge_type=edge_type)

        return None

    def lookup_state(
        self,
        field_name: str,
        field_type: Optional[str] = None,
        use_llm: Optional[bool] = None,
    ) -> Optional[StateTemplate]:
        """查找相似状态模板（双层匹配）"""
        # Tier 1
        query_keywords = _extract_keywords(field_name)

        best_match = None
        best_score = 0.0

        for template in self._index.states.values():
            if field_type and template.type != field_type:
                continue

            score = _keyword_match_score(query_keywords, template.name_keywords)
            if template.field_name.lower() == field_name.lower():
                score += 0.5

            if score > best_score:
                best_score = score
                best_match = template

        if best_match and best_score >= 0.4:
            best_match.usage_count += 1
            best_match.last_used = datetime.now().isoformat()
            self._save()
            return best_match

        # Tier 2
        if self._should_use_llm(use_llm):
            return self._llm_lookup("state", field_name, field_type=field_type)

        return None

    def lookup_prompt(
        self,
        task_type: str,
        name: str = "",
        use_llm: Optional[bool] = None,
    ) -> Optional[PromptTemplate]:
        """查找相似提示词模板（双层匹配）"""
        # Tier 1
        query_keywords = _extract_keywords(name)

        best_match = None
        best_score = 0.0

        for template in self._index.prompts.values():
            if template.task_type != task_type:
                continue

            score = _keyword_match_score(query_keywords, template.name_keywords)
            if score > best_score:
                best_score = score
                best_match = template

        if best_match and best_score >= 0.3:
            best_match.usage_count += 1
            best_match.last_used = datetime.now().isoformat()
            self._save()
            return best_match

        # Tier 2
        if self._should_use_llm(use_llm):
            return self._llm_lookup("prompt", name, task_type=task_type)

        return None

    # ============== 保存方法 ==============

    def save_node(self, node: Any, workflow_name: str = "") -> NodeTemplate:
        """保存节点模板

        Args:
            node: NodeDefinition 或 ExtractedNode 实例
            workflow_name: 来源工作流名称

        Returns:
            保存的 NodeTemplate
        """
        name = getattr(node, 'name', str(node))
        template_id = self._generate_id("node", name)
        description = getattr(node, 'description', '') or ""

        # 检查是否已存在相同名称的模板
        for existing in self._index.nodes.values():
            if existing.name == name and existing.type == getattr(node, 'type', 'tool'):
                # 更新已有模板的使用信息
                existing.usage_count += 1
                existing.last_used = datetime.now().isoformat()
                existing.source_workflow = workflow_name
                self._save()
                logger.info("node_template_updated", name=name)
                return existing

        template = NodeTemplate(
            template_id=template_id,
            name=name,
            name_keywords=_extract_keywords(f"{name} {description}"),
            type=getattr(node, 'type', 'tool'),
            description=description,
            inputs=getattr(node, 'inputs', []),
            outputs=getattr(node, 'outputs', []),
            config=getattr(node, 'config', {}),
            source_workflow=workflow_name,
            created_at=datetime.now().isoformat(),
        )

        self._index.nodes[template_id] = template
        self._save()
        logger.info("node_template_saved", name=name, template_id=template_id)
        return template

    def save_edge(
        self,
        edge: Any,
        source_name: str = "",
        target_name: str = "",
        workflow_name: str = "",
    ) -> EdgeTemplate:
        """保存边模板"""
        source = getattr(edge, 'source', source_name)
        target = getattr(edge, 'target', target_name)
        template_id = self._generate_id("edge", f"{source}_{target}")

        # 检查是否已存在
        for existing in self._index.edges.values():
            if (existing.source_type == source and existing.target_type == target
                    and existing.edge_type == getattr(edge, 'type', 'sequential')):
                existing.usage_count += 1
                existing.last_used = datetime.now().isoformat()
                self._save()
                return existing

        template = EdgeTemplate(
            template_id=template_id,
            source_type=source_name or source,
            target_type=target_name or target,
            edge_type=getattr(edge, 'type', 'sequential'),
            condition=getattr(edge, 'condition', None),
            description=f"{source} -> {target}",
            source_workflow=workflow_name,
            created_at=datetime.now().isoformat(),
        )

        self._index.edges[template_id] = template
        self._save()
        logger.info("edge_template_saved", source=source, target=target)
        return template

    def save_state(self, state: Any, workflow_name: str = "") -> StateTemplate:
        """保存状态模板"""
        field_name = getattr(state, 'field_name', str(state))
        template_id = self._generate_id("state", field_name)

        # 检查是否已存在
        for existing in self._index.states.values():
            if existing.field_name == field_name:
                existing.usage_count += 1
                existing.last_used = datetime.now().isoformat()
                self._save()
                return existing

        description = getattr(state, 'description', '') or ""
        template = StateTemplate(
            template_id=template_id,
            field_name=field_name,
            name_keywords=_extract_keywords(f"{field_name} {description}"),
            type=getattr(state, 'type', 'string'),
            default_value=getattr(state, 'default_value', None),
            description=description,
            required=getattr(state, 'required', False),
            source_workflow=workflow_name,
            created_at=datetime.now().isoformat(),
        )

        self._index.states[template_id] = template
        self._save()
        logger.info("state_template_saved", field_name=field_name)
        return template

    def save_prompt(
        self,
        task_type: str,
        name: str,
        content: str,
        workflow_name: str = "",
    ) -> PromptTemplate:
        """保存提示词模板"""
        template_id = self._generate_id("prompt", name)

        # 检查是否已存在
        for existing in self._index.prompts.values():
            if existing.name == name and existing.task_type == task_type:
                existing.content = content
                existing.usage_count += 1
                existing.last_used = datetime.now().isoformat()
                self._save()
                return existing

        template = PromptTemplate(
            template_id=template_id,
            task_type=task_type,
            name=name,
            content=content,
            name_keywords=_extract_keywords(name),
            source_workflow=workflow_name,
            created_at=datetime.now().isoformat(),
        )

        self._index.prompts[template_id] = template
        self._save()
        logger.info("prompt_template_saved", name=name, task_type=task_type)
        return template

    # ============== 批量语义匹配 ==============

    def batch_match(self, config: Any, llm: Optional[Any] = None) -> dict[str, list[dict]]:
        """LLM 批量语义匹配：一次调用匹配所有 nodes/edges/states

        Args:
            config: WorkflowConfig 实例
            llm: OpenAILLM 实例（为 None 时使用 self._llm）

        Returns:
            {"nodes": [...], "edges": [...], "states": [...]}
            每个元素: {"query_name": str, "matched": NodeTemplate|None, "confidence": float,
                       "enhanced_fields": dict}
        """
        llm = llm or self._llm
        if not llm:
            logger.warning("batch_match_no_llm")
            return {"nodes": [], "edges": [], "states": []}

        catalog_data = _load_yaml_file(self.library_dir / "catalog.yaml")
        if not catalog_data:
            return {"nodes": [], "edges": [], "states": []}

        all_catalog = catalog_data.get("components", [])

        nodes = getattr(config, 'nodes', [])
        edges = getattr(config, 'edges', [])
        states = getattr(config, 'state', [])

        # 建立节点 ID→名称映射（边的 source/target 是 ID）
        node_id_to_name = {n.node_id: n.name for n in nodes if hasattr(n, 'node_id')}

        results: dict[str, list[dict]] = {}

        # --- 按类别分批匹配 ---
        for category, items, query_builder in [
            ("node", nodes, self._build_node_queries),
            ("state", states, self._build_state_queries),
        ]:
            if not items:
                results[category + "s"] = []
                continue
            queries_text = query_builder(items)
            candidates_text = self._format_catalog_candidates(all_catalog, category)
            if not candidates_text.strip():
                results[category + "s"] = [{"query_name": getattr(it, 'name', getattr(it, 'field_name', '')),
                                           "matched": None, "confidence": 0.0, "enhanced_fields": {}}
                                          for it in items]
                continue
            matches = self._do_batch_llm_match(category, queries_text, candidates_text, llm)
            results[category + "s"] = self._resolve_matches(category, matches, items)

        # --- 边匹配（基于节点名称） ---
        if edges:
            queries_text = self._build_edge_queries(edges, node_id_to_name)
            candidates_text = self._format_catalog_candidates(all_catalog, "edge")
            if candidates_text.strip():
                matches = self._do_batch_llm_match("edge", queries_text, candidates_text, llm)
                results["edges"] = self._resolve_edge_matches(matches, edges, node_id_to_name)
            else:
                results["edges"] = [{"query_name": f"{e.source}->{e.target}", "matched": None,
                                     "confidence": 0.0, "enhanced_fields": {}} for e in edges]
        else:
            results["edges"] = []

        logger.info("batch_component_matched",
                    nodes=len(results.get("nodes", [])),
                    edges=len(results.get("edges", [])),
                    states=len(results.get("states", [])))
        return results

    def batch_enhance(self, config: Any, llm: Optional[Any] = None) -> Any:
        """批量语义匹配 + 增强配置（填充空字段）

        Args:
            config: WorkflowConfig 实例
            llm: OpenAILLM 实例

        Returns:
            增强后的 WorkflowConfig（原地修改并返回）
        """
        results = self.batch_match(config, llm)
        enhanced_count = 0

        # 增强 nodes
        for match_info in results.get("nodes", []):
            name = match_info.get("query_name", "")
            enhanced = match_info.get("enhanced_fields", {})
            if not enhanced:
                continue
            for node in getattr(config, 'nodes', []):
                if node.name == name:
                    if not node.description and enhanced.get("description"):
                        node.description = enhanced["description"]
                    if not node.inputs and enhanced.get("inputs"):
                        node.inputs = enhanced["inputs"]
                    if not node.outputs and enhanced.get("outputs"):
                        node.outputs = enhanced["outputs"]
                    enhanced_count += 1
                    logger.info("batch_node_enhanced", node=name)
                    break

        # 增强 states
        for match_info in results.get("states", []):
            name = match_info.get("query_name", "")
            enhanced = match_info.get("enhanced_fields", {})
            if not enhanced:
                continue
            for state in getattr(config, 'state', []):
                if state.field_name == name:
                    if not state.description and enhanced.get("description"):
                        state.description = enhanced["description"]
                    enhanced_count += 1
                    logger.info("batch_state_enhanced", state=name)
                    break

        logger.info("batch_enhance_complete", enhanced_count=enhanced_count)
        return config

    # --- 批量匹配辅助方法 ---

    def _build_node_queries(self, nodes: list) -> str:
        lines = []
        for n in nodes:
            name = getattr(n, 'name', '')
            ntype = getattr(n, 'type', 'tool')
            desc = getattr(n, 'description', '') or ''
            inputs = getattr(n, 'inputs', []) or []
            outputs = getattr(n, 'outputs', []) or []
            missing = []
            if not desc:
                missing.append("description")
            if not inputs:
                missing.append("inputs")
            if not outputs:
                missing.append("outputs")
            lines.append(
                f'- 名称: "{name}", 类型: {ntype}, 描述: "{desc}", '
                f'输入: {inputs}, 输出: {outputs}, 缺失字段: {missing}'
            )
        return "\n".join(lines)

    def _build_state_queries(self, states: list) -> str:
        lines = []
        for s in states:
            fname = getattr(s, 'field_name', '')
            ftype = getattr(s, 'type', 'string')
            desc = getattr(s, 'description', '') or ''
            required = getattr(s, 'required', False)
            missing = []
            if not desc:
                missing.append("description")
            lines.append(
                f'- 字段: "{fname}", 类型: {ftype}, 描述: "{desc}", 必填: {required}, 缺失字段: {missing}'
            )
        return "\n".join(lines)

    def _build_edge_queries(self, edges: list, node_id_to_name: dict) -> str:
        lines = []
        for e in edges:
            source = getattr(e, 'source', '')
            target = getattr(e, 'target', '')
            etype = getattr(e, 'type', 'sequential')
            cond = getattr(e, 'condition', '') or ''
            source_name = node_id_to_name.get(source, source)
            target_name = node_id_to_name.get(target, target)
            lines.append(
                f'- 源: "{source_name}", 目标: "{target_name}", '
                f'类型: {etype}, 条件: "{cond}"'
            )
        return "\n".join(lines)

    def _format_catalog_candidates(self, all_catalog: list, category: str) -> str:
        candidates = [e for e in all_catalog if e.get("category") == category]
        if not candidates:
            return ""
        lines = []
        for c in candidates:
            lines.append(f'- ID: {c["id"]}, 名称: "{c["name"]}", 摘要: {c.get("summary", "")}')
        return "\n".join(lines)

    def _do_batch_llm_match(self, category: str, queries_text: str,
                           candidates_text: str, llm: Any) -> list[dict]:
        """执行一次 LLM 批量匹配调用"""
        from pdca.core.prompts import BATCH_MATCH_PROMPT

        prompt = BATCH_MATCH_PROMPT.format(
            category=category,
            queries=queries_text,
            candidates=candidates_text,
        )

        try:
            response = llm.generate_messages([
                {"role": "system", "content": "你是组件库语义匹配专家。只输出纯JSON，不要任何额外文本。"},
                {"role": "user", "content": prompt},
            ])
            data = parse_json_response(response)
            if data and "matches" in data:
                return data["matches"]
        except Exception as e:
            logger.warning("batch_llm_match_failed", category=category, error=str(e))

        return []

    def _resolve_matches(self, category: str, matches: list[dict],
                         items: list) -> list[dict]:
        """将 LLM 匹配结果解析为带模板引用的结构"""
        collection_map = {"node": self._index.nodes, "state": self._index.states}
        collection = collection_map.get(category, {})
        results = []

        for item in items:
            item_name = getattr(item, 'name', getattr(item, 'field_name', ''))
            match_entry = None
            for m in matches:
                if m.get("query_name") == item_name:
                    match_entry = m
                    break

            if not match_entry:
                results.append({"query_name": item_name, "matched": None,
                               "confidence": 0.0, "enhanced_fields": {}})
                continue

            matched_id = match_entry.get("matched_id")
            template = collection.get(matched_id) if matched_id else None

            if template:
                template.usage_count += 1
                template.last_used = datetime.now().isoformat()

            results.append({
                "query_name": item_name,
                "matched": template,
                "confidence": match_entry.get("confidence", 0.0),
                "enhanced_fields": match_entry.get("enhanced_fields", {}),
            })

        if any(r["matched"] for r in results):
            self._save()

        return results

    def _resolve_edge_matches(self, matches: list[dict], edges: list,
                              node_id_to_name: dict) -> list[dict]:
        """将 LLM 匹配结果解析为边匹配结构"""
        results = []
        for e in edges:
            source = getattr(e, 'source', '')
            target = getattr(e, 'target', '')
            source_name = node_id_to_name.get(source, source)
            target_name = node_id_to_name.get(target, target)
            query_key = f"{source_name}->{target_name}"

            match_entry = None
            for m in matches:
                mq = m.get("query_name", "")
                if mq == query_key or mq == f"{source_name} -> {target_name}":
                    match_entry = m
                    break

            matched_id = match_entry.get("matched_id") if match_entry else None
            template = self._index.edges.get(matched_id) if matched_id else None

            if template:
                template.usage_count += 1
                template.last_used = datetime.now().isoformat()

            results.append({
                "query_name": query_key,
                "matched": template,
                "confidence": match_entry.get("confidence", 0.0) if match_entry else 0.0,
                "enhanced_fields": {},
            })

        if any(r["matched"] for r in results):
            self._save()

        return results

    # ============== 批量保存 ==============

    def save_workflow_config(self, config: Any, workflow_name: str = ""):
        """从 WorkflowConfig 保存所有组件模板

        Args:
            config: WorkflowConfig 实例
            workflow_name: 工作流名称
        """
        workflow_name = workflow_name or getattr(config, 'meta', None) and config.meta.name or "unknown"
        nodes = getattr(config, 'nodes', [])
        edges = getattr(config, 'edges', [])
        states = getattr(config, 'state', [])

        # 建立节点ID→名称映射（用于边的 source/target）
        node_id_to_name = {n.node_id: n.name for n in nodes if hasattr(n, 'node_id')}

        saved_counts = {"nodes": 0, "edges": 0, "states": 0}

        for node in nodes:
            self.save_node(node, workflow_name)
            saved_counts["nodes"] += 1

        for edge in edges:
            source_name = node_id_to_name.get(getattr(edge, 'source', ''), '')
            target_name = node_id_to_name.get(getattr(edge, 'target', ''), '')
            self.save_edge(edge, source_name, target_name, workflow_name)
            saved_counts["edges"] += 1

        for state in states:
            self.save_state(state, workflow_name)
            saved_counts["states"] += 1

        logger.info("workflow_config_saved_to_library",
                    workflow=workflow_name,
                    **saved_counts)

    def discover_reusable_components(
        self,
        review_result: Any,
        config: Any,
        workflow_name: str = "",
    ) -> list[dict]:
        """从 GRRAVP 复盘结果中识别可复用组件（知识固化）

        分析策略：
        1. 成功因素中提到的节点 → 值得复用
        2. 必需状态字段 → 通用状态模式
        3. 高优先级优化建议 → 提示词/方法模式

        Args:
            review_result: GRBARPReviewResult 实例
            config: WorkflowConfig 实例
            workflow_name: 工作流名称

        Returns:
            发现列表: [{"category": "node|state|prompt", "name": "...", "reason": "..."}]
        """
        discoveries = []
        workflow_name = workflow_name or getattr(config, 'meta', None) and config.meta.name or "unknown"

        # 1. 从成功因素中识别节点模式
        result_analysis = getattr(review_result, 'result_analysis', {})
        if isinstance(result_analysis, dict):
            success_factors = result_analysis.get("success_factors", [])
            nodes = getattr(config, 'nodes', [])

            for node in nodes:
                node_name = getattr(node, 'name', '')
                node_desc = getattr(node, 'description', '') or ''

                for factor in success_factors:
                    if (node_name and node_name.lower() in factor.lower()) or \
                       (node_desc and node_desc.lower() in factor.lower()):
                        discoveries.append({
                            "category": "node",
                            "name": node_name,
                            "reason": f"成功因素中识别到: {factor[:80]}",
                            "component": node,
                        })
                        break

        # 2. 识别必需状态模式
        states = getattr(config, 'state', [])
        for state in states:
            if getattr(state, 'required', False):
                field_name = getattr(state, 'field_name', '')
                discoveries.append({
                    "category": "state",
                    "name": field_name,
                    "reason": "必需状态，在多个工作流中常见",
                    "component": state,
                })

        # 3. 从高优先级优化中提取提示模式
        action_planning = getattr(review_result, 'action_planning', {})
        if isinstance(action_planning, dict):
            actions = action_planning.get("actions", [])
            for action in actions:
                if isinstance(action, dict) and action.get("priority") == "high":
                    action_text = action.get("action", "")
                    discoveries.append({
                        "category": "prompt",
                        "name": f"optimization_{action_text[:30]}",
                        "reason": f"高优先级优化: {action_text[:80]}",
                        "content": str(action),
                    })

        # 将发现的组件保存到库中
        for d in discoveries:
            if d["category"] == "node" and "component" in d:
                self.save_node(d["component"], workflow_name)
            elif d["category"] == "state" and "component" in d:
                self.save_state(d["component"], workflow_name)
            elif d["category"] == "prompt" and "content" in d:
                self.save_prompt("review_discovery", d["name"], d["content"], workflow_name)

        logger.info("reusable_components_discovered",
                    workflow=workflow_name,
                    count=len(discoveries))

        return discoveries

    # ============== 统计与维护 ==============

    def get_statistics(self) -> dict:
        """获取组件库统计信息"""
        return {
            "total_templates": (
                len(self._index.nodes) +
                len(self._index.edges) +
                len(self._index.states) +
                len(self._index.prompts)
            ),
            "node_templates": len(self._index.nodes),
            "edge_templates": len(self._index.edges),
            "state_templates": len(self._index.states),
            "prompt_templates": len(self._index.prompts),
            "total_usage": (
                sum(n.usage_count for n in self._index.nodes.values()) +
                sum(e.usage_count for e in self._index.edges.values()) +
                sum(s.usage_count for s in self._index.states.values()) +
                sum(p.usage_count for p in self._index.prompts.values())
            ),
        }

    def prune_unused(self, keep_recent: int = 200):
        """清理低使用率的模板

        保留条件：使用次数 > 0 或在最近 keep_recent 条之内
        """
        pruned = 0

        for collection_name in ["nodes", "edges", "states", "prompts"]:
            collection = getattr(self._index, collection_name)
            candidates = sorted(
                collection.values(),
                key=lambda t: t.usage_count,
                reverse=True,
            )
            to_keep = {t.template_id for t in candidates[:keep_recent]}

            for tid in list(collection.keys()):
                if tid not in to_keep:
                    del collection[tid]
                    pruned += 1

        if pruned > 0:
            self._save()
            logger.info("library_pruned", removed=pruned)

        return pruned

    def list_templates(self, category: Optional[str] = None) -> list[dict]:
        """列出模板摘要

        Args:
            category: 可选，筛选类别: node/edge/state/prompt

        Returns:
            模板摘要列表
        """
        results = []

        if category is None or category == "node":
            for t in self._index.nodes.values():
                results.append({
                    "category": "node", "id": t.template_id,
                    "name": t.name, "type": t.type,
                    "usage_count": t.usage_count,
                })

        if category is None or category == "edge":
            for t in self._index.edges.values():
                results.append({
                    "category": "edge", "id": t.template_id,
                    "name": f"{t.source_type} -> {t.target_type}",
                    "usage_count": t.usage_count,
                })

        if category is None or category == "state":
            for t in self._index.states.values():
                results.append({
                    "category": "state", "id": t.template_id,
                    "name": t.field_name, "type": t.type,
                    "usage_count": t.usage_count,
                })

        if category is None or category == "prompt":
            for t in self._index.prompts.values():
                results.append({
                    "category": "prompt", "id": t.template_id,
                    "name": t.name, "task_type": t.task_type,
                    "usage_count": t.usage_count,
                })

        return results
