"""测试结构化抽取模块"""

import pytest
from unittest.mock import MagicMock, patch
from pdca.plan.extractor import (
    NodeExtractor,
    EdgeExtractor,
    StateExtractor,
    StructuredExtractor,
    ClarificationEngine,
    ExtractedNode,
    ExtractedEdge,
    ExtractedState,
    StructuredDocument,
    ClarificationQuestion,
    extract_structure,
    extract_with_clarification
)


class TestNodeExtractor:
    """NodeExtractor测试"""
    
    def test_identify_node_type_tool(self):
        """测试识别工具节点"""
        extractor = NodeExtractor(llm=MagicMock())
        assert extractor._identify_node_type("调用API获取数据") == 'tool'
        assert extractor._identify_node_type("执行查询操作") == 'tool'
        assert extractor._identify_node_type("上传文件到服务器") == 'tool'
    
    def test_identify_node_type_thought(self):
        """测试识别思维节点"""
        extractor = NodeExtractor(llm=MagicMock())
        assert extractor._identify_node_type("分析用户意图") == 'thought'
        assert extractor._identify_node_type("判断数据有效性") == 'thought'
        assert extractor._identify_node_type("生成报告摘要") == 'thought'
    
    def test_identify_node_type_control(self):
        """测试识别控制节点"""
        extractor = NodeExtractor(llm=MagicMock())
        assert extractor._identify_node_type("开始处理流程") == 'control'
        assert extractor._identify_node_type("结束当前任务") == 'control'
        assert extractor._identify_node_type("如果条件满足") == 'control'
    
    def test_generate_node_name(self):
        """测试生成节点名称"""
        extractor = NodeExtractor(llm=MagicMock())
        
        name = extractor._generate_node_name("调用API获取数据")
        assert name == "调用API获取数据"
        
        # 测试截断
        long_name = "调用API获取用户数据并进行一系列处理操作"
        name = extractor._generate_node_name(long_name)
        assert len(name) <= 20
        assert name.endswith('...')
    
    def test_extract_nodes_with_sequential_words(self):
        """测试抽取带有顺序词的节点"""
        extractor = NodeExtractor(llm=MagicMock())
        text = "首先调用API获取数据，然后分析用户意图，最后生成报告"
        
        nodes = extractor.extract(text)
        
        assert len(nodes) >= 1
        assert all(isinstance(n, ExtractedNode) for n in nodes)
    
    def test_extract_nodes_returns_valid_structure(self):
        """测试抽取结果的结构有效性"""
        extractor = NodeExtractor(llm=MagicMock())
        text = "调用工具执行任务"
        
        nodes = extractor.extract(text)
        
        for node in nodes:
            assert node.node_id.startswith('node_')
            assert len(node.name) > 0
            assert node.type in ['tool', 'thought', 'control']


class TestEdgeExtractor:
    """EdgeExtractor测试"""
    
    def test_identify_edge_type_sequential(self):
        """测试识别顺序边"""
        extractor = EdgeExtractor(llm=MagicMock())
        edge_type, condition = extractor._identify_edge_type("然后")
        assert edge_type == 'sequential'
        assert condition is None
    
    def test_identify_edge_type_conditional(self):
        """测试识别条件边"""
        extractor = EdgeExtractor(llm=MagicMock())
        edge_type, condition = extractor._identify_edge_type("如果")
        assert edge_type == 'conditional'
    
    def test_extract_condition(self):
        """测试提取条件表达式"""
        extractor = EdgeExtractor(llm=MagicMock())
        
        context = "如果数据有效则执行下一步"
        condition = extractor._extract_condition(context)
        assert condition == "数据有效"
        
        context = "当用户已登录时"
        condition = extractor._extract_condition(context)
        assert condition is None  # 不匹配模式
    
    def test_extract_edges_with_connectors(self):
        """测试抽取有连接词的边"""
        extractor = EdgeExtractor(llm=MagicMock())
        
        nodes = [
            ExtractedNode(node_id="n1", name="获取数据", type="tool"),
            ExtractedNode(node_id="n2", name="分析数据", type="thought"),
            ExtractedNode(node_id="n3", name="生成报告", type="thought")
        ]
        
        text = "首先获取数据，然后分析数据，最后生成报告"
        edges = extractor.extract(text, nodes)
        
        # 应该创建顺序边
        assert len(edges) >= 2
    
    def test_extract_edges_default_sequential(self):
        """测试默认创建顺序边"""
        extractor = EdgeExtractor(llm=MagicMock())
        
        nodes = [
            ExtractedNode(node_id="n1", name="步骤1", type="tool"),
            ExtractedNode(node_id="n2", name="步骤2", type="tool")
        ]
        
        edges = extractor.extract("步骤1 步骤2", nodes)
        
        assert len(edges) == 1
        assert edges[0].type == 'sequential'
        assert edges[0].source == 'n1'
        assert edges[0].target == 'n2'
    
    def test_extract_edges_insufficient_nodes(self):
        """测试节点不足时返回空"""
        extractor = EdgeExtractor(llm=MagicMock())
        
        nodes = [ExtractedNode(node_id="n1", name="唯一节点", type="tool")]
        edges = extractor.extract("唯一节点", nodes)
        
        assert len(edges) == 0


class TestStateExtractor:
    """StateExtractor测试"""
    
    def test_infer_type_integer(self):
        """测试推断整数类型"""
        extractor = StateExtractor(llm=MagicMock())
        assert extractor._infer_type("用户数量") == 'integer'
        assert extractor._infer_type("数据count") == 'integer'
    
    def test_infer_type_array(self):
        """测试推断数组类型"""
        extractor = StateExtractor(llm=MagicMock())
        assert extractor._infer_type("用户列表") == 'array'
        assert extractor._infer_type("item list") == 'array'
    
    def test_infer_type_string(self):
        """测试推断字符串类型"""
        extractor = StateExtractor(llm=MagicMock())
        assert extractor._infer_type("用户名") == 'string'
        assert extractor._infer_type("状态status") == 'string'
    
    def test_is_result_field(self):
        """测试判断结果字段"""
        extractor = StateExtractor(llm=MagicMock())
        assert extractor._is_result_field("分析结果") is True
        assert extractor._is_result_field("output_data") is True
        assert extractor._is_result_field("用户姓名") is False
    
    def test_extract_states_from_text(self):
        """测试从文本抽取状态"""
        extractor = StateExtractor(llm=MagicMock())
        # 使用更清晰简单的模式
        text = "提取分析结果并保存"
        
        states = extractor.extract(text)
        
        assert len(states) >= 1
        assert all(isinstance(s, ExtractedState) for s in states)
        # 验证能提取到状态
        assert any("结果" in s.field_name or "input" in s.field_name.lower() for s in states)
    
    def test_extract_states_deduplication(self):
        """测试状态去重"""
        extractor = StateExtractor(llm=MagicMock())
        text = "用户数据、用户数据、用户数据"
        
        states = extractor.extract(text)
        
        field_names = [s.field_name for s in states]
        assert len(field_names) == len(set(field_names))


class TestStructuredExtractor:
    """StructuredExtractor测试"""
    
    def test_extract_complete_workflow(self):
        """测试完整工作流抽取"""
        extractor = StructuredExtractor(llm=MagicMock())
        text = """
        首先调用API获取用户数据，
        然后分析用户行为模式，
        最后生成用户画像报告
        """
        
        document = extractor.extract(text)
        
        assert isinstance(document, StructuredDocument)
        assert len(document.nodes) >= 1
        assert len(document.edges) >= 1
        assert len(document.states) >= 1
        assert document.raw_text == text
    
    def test_check_missing_info_incomplete_workflow(self):
        """测试检查不完整工作流"""
        extractor = StructuredExtractor(llm=MagicMock())
        
        # 单节点工作流
        nodes = [ExtractedNode(node_id="n1", name="唯一节点", type="tool")]
        edges = []
        states = [ExtractedState(field_name="result", type="any")]
        
        missing = extractor._check_missing_info("唯一节点", nodes, edges, states)
        
        assert len(missing) >= 1
        assert any("节点数量" in info for info in missing)
    
    def test_extract_realistic_workflow(self):
        """测试真实工作流抽取"""
        extractor = StructuredExtractor(llm=MagicMock())
        text = """
        开发流程如下：
        1. 首先获取GitHub仓库列表
        2. 然后对每个仓库进行健康度分析
        3. 接着生成分析报告
        4. 最后将报告发送到企业微信
        """
        
        document = extractor.extract(text)
        
        assert len(document.nodes) >= 4
        assert document.raw_text == text
        # 应该有顺序边连接各个节点
        assert len(document.edges) >= 3


class TestClarificationEngine:
    """ClarificationEngine测试"""
    
    def test_identify_ambiguities_missing_descriptions(self):
        """测试识别缺失描述"""
        engine = ClarificationEngine(llm=MagicMock())
        
        document = StructuredDocument(
            nodes=[
                ExtractedNode(
                    node_id="n1",
                    name="处理节点",
                    type="tool",
                    description="从文本抽取: 处理任务"  # 模糊描述
                )
            ],
            edges=[],
            states=[],
            raw_text="处理节点"
        )
        
        questions = engine.identify_ambiguities(document)
        
        assert len(questions) >= 1
        assert any("处理节点" in q.question for q in questions)
    
    def test_generate_questions_respects_max(self):
        """测试生成问题数量限制"""
        engine = ClarificationEngine(llm=MagicMock())
        
        document = StructuredDocument(
            nodes=[
                ExtractedNode(node_id=f"n{i}", name=f"节点{i}", type="tool")
                for i in range(10)
            ],
            edges=[],
            states=[],
            raw_text=""
        )
        
        questions = engine.generate_questions(document, max_questions=3)
        
        assert len(questions) <= 3
    
    def test_questions_sorted_by_priority(self):
        """测试问题按优先级排序"""
        engine = ClarificationEngine(llm=MagicMock())
        
        document = StructuredDocument(
            nodes=[
                ExtractedNode(node_id="n1", name="节点1", type="tool"),
                ExtractedNode(node_id="n2", name="节点2", type="tool")
            ],
            edges=[],
            states=[],
            raw_text=""
        )
        
        questions = engine.generate_questions(document)
        
        if len(questions) >= 2:
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            for i in range(len(questions) - 1):
                assert priority_order.get(questions[i].priority, 1) <= \
                       priority_order.get(questions[i + 1].priority, 1)


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_extract_structure(self):
        """测试快速抽取函数"""
        document = extract_structure("获取数据，分析数据", llm=MagicMock())
        
        assert isinstance(document, StructuredDocument)
        assert document.raw_text == "获取数据，分析数据"
    
    def test_extract_with_clarification(self):
        """测试带澄清问题的抽取"""
        document, questions = extract_with_clarification(
            "获取数据", 
            llm=MagicMock()
        )
        
        assert isinstance(document, StructuredDocument)
        assert isinstance(questions, list)
