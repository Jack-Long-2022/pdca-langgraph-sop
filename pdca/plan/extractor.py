"""结构化抽取模块

从用户描述文本中抽取节点、边和状态信息
"""

import re
import uuid
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


# ============== 节点抽取器 ==============

class NodeExtractor:
    """节点抽取器 - 从文本中识别和抽取节点"""
    
    # 工具节点关键词
    TOOL_KEYWORDS = [
        '调用', '执行', '运行', '使用', '获取', '查询', '发送', '上传', '下载',
        '处理', '转换', '格式化', '验证', '检查', '计算', '存储', '保存'
    ]
    
    # 思维节点关键词
    THOUGHT_KEYWORDS = [
        '分析', '思考', '判断', '评估', '总结', '生成', '创建', '设计',
        '规划', '推理', '理解', '识别', '分类', '提取'
    ]
    
    # 控制节点关键词
    CONTROL_KEYWORDS = [
        '开始', '结束', '终止', '跳过', '重试', '循环', '分支',
        '如果', '当', '则', '否则', '或者'
    ]
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """初始化节点抽取器
        
        Args:
            llm: LLM实例，如果为None则使用默认LLM
        """
        self.llm = llm or get_llm_manager().get_llm()
    
    def _identify_node_type(self, verb_phrase: str) -> str:
        """识别节点类型
        
        Args:
            verb_phrase: 动词短语
        
        Returns:
            节点类型: tool/thought/control
        """
        # 优先检查控制关键词（特别是开头的控制词如"开始"、"结束"）
        for keyword in self.CONTROL_KEYWORDS:
            if verb_phrase.startswith(keyword):
                return 'control'
        
        # 检查思维关键词
        for keyword in self.THOUGHT_KEYWORDS:
            if keyword in verb_phrase:
                return 'thought'
        
        # 检查工具关键词
        for keyword in self.TOOL_KEYWORDS:
            if keyword in verb_phrase:
                return 'tool'
        
        # 默认为工具节点
        return 'tool'
    
    def _extract_verb_phrases(self, text: str) -> list[str]:
        """提取动词短语
        
        Args:
            text: 输入文本
        
        Returns:
            动词短语列表
        """
        # 使用正则表达式提取动词开头的短语
        # 匹配 "先/然后/接着" 等顺序词后面的动词短语
        patterns = [
            r'(?:首先|先|第一|接着|然后|之后|随后|最后|最终)([^\n，。！？]+)',
            r'([^\n，。！？]+(?:调用|执行|运行|使用|获取|查询|分析|判断|生成|创建|开始|结束))',
        ]
        
        phrases = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            phrases.extend(matches)
        
        return phrases
    
    def _generate_node_name(self, verb_phrase: str) -> str:
        """生成节点名称
        
        Args:
            verb_phrase: 动词短语
        
        Returns:
            节点名称
        """
        # 清理并格式化名称
        name = verb_phrase.strip()
        # 移除句末标点
        name = re.sub(r'[。！？；]$', '', name)
        # 限制长度
        if len(name) > 20:
            name = name[:17] + '...'
        return name
    
    def extract(self, text: str) -> list[ExtractedNode]:
        """从文本中抽取节点
        
        Args:
            text: 用户描述文本
        
        Returns:
            节点列表
        """
        logger.debug("extracting_nodes", text_length=len(text))
        
        nodes = []
        verb_phrases = self._extract_verb_phrases(text)
        
        for i, phrase in enumerate(verb_phrases):
            node_type = self._identify_node_type(phrase)
            node = ExtractedNode(
                node_id=f"node_{uuid.uuid4().hex[:8]}",
                name=self._generate_node_name(phrase),
                type=node_type,
                description=f"从文本抽取: {phrase}",
                inputs=[],
                outputs=[],
                config={}
            )
            nodes.append(node)
            logger.debug("node_extracted", node_id=node.node_id, name=node.name, type=node_type)
        
        logger.info("nodes_extraction_complete", count=len(nodes))
        return nodes


# ============== 边抽取器 ==============

class EdgeExtractor:
    """边抽取器 - 从文本中识别节点之间的关系"""
    
    # 顺序连接词
    SEQUENTIAL_WORDS = ['然后', '接着', '之后', '随后', '再', '接着', '最后', '最终']
    
    # 条件连接词
    CONDITIONAL_WORDS = ['如果', '当', '只要', '假如', '若是', '要是']
    
    # 分支连接词
    BRANCH_WORDS = ['或者', '或者', '要么', '或者', '还是', '或者']
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """初始化边抽取器
        
        Args:
            llm: LLM实例，如果为None则使用默认LLM
        """
        self.llm = llm or get_llm_manager().get_llm()
    
    def _identify_edge_type(self, word: str, context: str = "") -> tuple[str, Optional[str]]:
        """识别边类型
        
        Args:
            word: 连接词
            context: 上下文文本
        
        Returns:
            (边类型, 条件表达式)
        """
        if word in self.CONDITIONAL_WORDS:
            # 尝试提取条件表达式
            condition = self._extract_condition(context)
            return ('conditional', condition)
        
        if word in self.BRANCH_WORDS:
            return ('conditional', None)
        
        return ('sequential', None)
    
    def _extract_condition(self, context: str) -> Optional[str]:
        """提取条件表达式
        
        Args:
            context: 上下文文本
        
        Returns:
            条件表达式
        """
        # 简单实现：提取"如果X则Y"格式中的X
        match = re.search(r'如果(.+?)[则|那么|就]', context)
        if match:
            return match.group(1).strip()
        return None
    
    def _find_connections(self, text: str, nodes: list[ExtractedNode]) -> list[tuple[int, int, str]]:
        """查找节点间的连接关系
        
        Args:
            text: 原始文本
            nodes: 节点列表
        
        Returns:
            (源节点索引, 目标节点索引, 连接词) 列表
        """
        connections = []
        
        for i, word in enumerate(self.SEQUENTIAL_WORDS + self.CONDITIONAL_WORDS + self.BRANCH_WORDS):
            if word in text:
                # 查找连接词前的节点
                word_pos = text.find(word)
                for j, node in enumerate(nodes):
                    if node.name in text[:word_pos] and j < len(nodes) - 1:
                        connections.append((j, j + 1, word))
        
        return connections
    
    def extract(self, text: str, nodes: list[ExtractedNode]) -> list[ExtractedEdge]:
        """从文本和节点列表中抽取边
        
        Args:
            text: 用户描述文本
            nodes: 节点列表
        
        Returns:
            边列表
        """
        logger.debug("extracting_edges", text_length=len(text), node_count=len(nodes))
        
        edges = []
        
        if len(nodes) < 2:
            logger.warning("insufficient_nodes_for_edges", node_count=len(nodes))
            return edges
        
        # 查找显式连接
        connections = self._find_connections(text, nodes)
        
        for source_idx, target_idx, connector in connections:
            edge_type, condition = self._identify_edge_type(connector, text)
            
            edge = ExtractedEdge(
                source=nodes[source_idx].node_id,
                target=nodes[target_idx].node_id,
                condition=condition,
                type=edge_type
            )
            edges.append(edge)
            logger.debug("edge_extracted", 
                        source=nodes[source_idx].name, 
                        target=nodes[target_idx].name,
                        type=edge_type)
        
        # 如果没有找到显式连接，假设顺序连接
        if not edges and len(nodes) > 1:
            for i in range(len(nodes) - 1):
                edge = ExtractedEdge(
                    source=nodes[i].node_id,
                    target=nodes[i + 1].node_id,
                    type='sequential'
                )
                edges.append(edge)
            logger.info("default_sequential_edges_created", count=len(edges))
        
        logger.info("edges_extraction_complete", count=len(edges))
        return edges


# ============== 状态抽取器 ==============

class StateExtractor:
    """状态抽取器 - 从文本中识别数据对象和中间结果"""
    
    # 常见数据类型模式 - 限制前面内容的长度避免过度匹配
    DATA_PATTERNS = [
        (r'([^，,。\n]{1,5})的结果', 'result'),
        (r'([^，,。\n]{1,5})的内容', 'content'),
        (r'([^，,。\n]{1,5})的数据', 'data'),
        (r'([^，,。\n]{1,5})的信息', 'info'),
        (r'([^，,。\n]{1,5})的列表', 'list'),
        (r'([^，,。\n]{1,5})的数量', 'count'),
        (r'([^，,。\n]{1,5})的状态', 'status'),
    ]
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """初始化状态抽取器
        
        Args:
            llm: LLM实例，如果为None则使用默认LLM
        """
        self.llm = llm or get_llm_manager().get_llm()
    
    def _infer_type(self, field_name: str) -> str:
        """推断字段类型
        
        Args:
            field_name: 字段名称
        
        Returns:
            类型字符串
        """
        field_lower = field_name.lower()
        
        if '数量' in field_name or 'count' in field_lower:
            return 'integer'
        if '列表' in field_name or 'list' in field_lower:
            return 'array'
        if '状态' in field_name or 'status' in field_lower:
            return 'string'
        if '结果' in field_name or 'result' in field_lower:
            return 'any'
        
        return 'string'
    
    def _is_result_field(self, field_name: str) -> bool:
        """判断是否为结果字段
        
        Args:
            field_name: 字段名称
        
        Returns:
            是否为结果字段
        """
        result_keywords = ['结果', 'content', 'data', 'info', 'output']
        return any(kw in field_name.lower() for kw in result_keywords)
    
    def extract(self, text: str) -> list[ExtractedState]:
        """从文本中抽取状态定义
        
        Args:
            text: 用户描述文本
        
        Returns:
            状态列表
        """
        logger.debug("extracting_states", text_length=len(text))
        
        states = []
        seen_fields = set()
        
        for pattern, default_type in self.DATA_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                field_name = match.strip()
                
                # 去重
                if field_name in seen_fields:
                    continue
                seen_fields.add(field_name)
                
                # 跳过太短或太长的字段名
                if len(field_name) < 2 or len(field_name) > 30:
                    continue
                
                state = ExtractedState(
                    field_name=field_name,
                    type=self._infer_type(field_name),
                    default_value=None,
                    description=f"从文本抽取: {field_name}",
                    required=self._is_result_field(field_name)
                )
                states.append(state)
                logger.debug("state_extracted", field_name=field_name, type=state.type)
        
        # 添加默认状态
        if not states:
            states.append(ExtractedState(
                field_name="input_text",
                type="string",
                default_value="",
                description="用户输入文本",
                required=True
            ))
            states.append(ExtractedState(
                field_name="result",
                type="any",
                description="处理结果",
                required=True
            ))
        
        logger.info("states_extraction_complete", count=len(states))
        return states


# ============== 结构化抽取总控 ==============

class StructuredExtractor:
    """结构化抽取总控 - 协调三个抽取器"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """初始化结构化抽取器
        
        Args:
            llm: LLM实例，如果为None则使用默认LLM
        """
        self.llm = llm
        self.node_extractor = NodeExtractor(llm)
        self.edge_extractor = EdgeExtractor(llm)
        self.state_extractor = StateExtractor(llm)
    
    def extract(self, text: str) -> StructuredDocument:
        """执行完整的结构化抽取
        
        Args:
            text: 用户描述文本
        
        Returns:
            结构化文档
        """
        logger.info("structured_extraction_start", text_length=len(text))
        
        # 1. 抽取节点
        nodes = self.node_extractor.extract(text)
        
        # 2. 抽取边（依赖节点）
        edges = self.edge_extractor.extract(text, nodes)
        
        # 3. 抽取状态
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
        """检查缺失信息
        
        Args:
            text: 原始文本
            nodes: 节点列表
            edges: 边列表
            states: 状态列表
        
        Returns:
            缺失信息列表
        """
        missing = []
        
        # 检查节点数量
        if len(nodes) < 2:
            missing.append("节点数量不足，至少需要2个节点")
        
        # 检查边连通性
        if edges:
            node_ids = {n.node_id for n in nodes}
            connected = set()
            for edge in edges:
                connected.add(edge.source)
                connected.add(edge.target)
            
            if connected != node_ids:
                disconnected = node_ids - connected
                missing.append(f"存在未连接的节点: {disconnected}")
        
        # 检查状态定义
        if not states:
            missing.append("缺少状态定义")
        
        return missing


# ============== 澄清引导引擎 ==============

class ClarificationEngine:
    """澄清引导引擎 - 识别信息缺失并生成澄清问题"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """初始化澄清引擎
        
        Args:
            llm: LLM实例，如果为None则使用默认LLM
        """
        self.llm = llm or get_llm_manager().get_llm()
    
    def identify_ambiguities(self, document: StructuredDocument) -> list[ClarificationQuestion]:
        """识别文档中的歧义
        
        Args:
            document: 结构化文档
        
        Returns:
            澄清问题列表
        """
        questions = []
        
        # 检查缺失的节点描述
        for node in document.nodes:
            if not node.description or node.description.startswith("从文本抽取"):
                questions.append(ClarificationQuestion(
                    question=f"请详细描述节点「{node.name}」的具体功能",
                    related_field=f"node:{node.node_id}",
                    priority="high"
                ))
        
        # 检查缺失的边条件
        for edge in document.edges:
            if edge.type == 'conditional' and not edge.condition:
                questions.append(ClarificationQuestion(
                    question=f"请说明节点间的条件判断逻辑",
                    related_field=f"edge:{edge.source}->{edge.target}",
                    priority="high"
                ))
        
        # 检查缺失的状态类型
        for state in document.states:
            if state.type == 'any':
                questions.append(ClarificationQuestion(
                    question=f"请明确「{state.field_name}」的数据类型",
                    related_field=f"state:{state.field_name}",
                    priority="medium"
                ))
        
        # 检查整体流程完整性
        if len(document.nodes) < 2:
            questions.append(ClarificationQuestion(
                question="工作流似乎过于简单，请确认是否描述了完整的流程？",
                related_field="workflow",
                priority="high"
            ))
        
        logger.info("ambiguities_identified", count=len(questions))
        return questions
    
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
        
        # 限制数量
        return questions[:max_questions]


# ============== 便捷函数 ==============

def extract_structure(text: str, llm: Optional[BaseLLM] = None) -> StructuredDocument:
    """快速执行结构化抽取
    
    Args:
        text: 用户描述文本
        llm: LLM实例
    
    Returns:
        结构化文档
    """
    extractor = StructuredExtractor(llm)
    return extractor.extract(text)


def extract_with_clarification(
    text: str, 
    llm: Optional[BaseLLM] = None
) -> tuple[StructuredDocument, list[ClarificationQuestion]]:
    """抽取并生成澄清问题
    
    Args:
        text: 用户描述文本
        llm: LLM实例
    
    Returns:
        (结构化文档, 澄清问题列表)
    """
    extractor = StructuredExtractor(llm)
    document = extractor.extract(text)
    
    clarifier = ClarificationEngine(llm)
    questions = clarifier.generate_questions(document)
    
    return document, questions
