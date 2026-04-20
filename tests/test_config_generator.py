"""测试配置生成模块"""

import pytest
from unittest.mock import MagicMock
from pdca.plan.config_generator import (
    ConfigGenerator,
    PromptTemplates,
    generate_config,
    generate_config_with_refinement
)
from pdca.plan.extractor import (
    StructuredDocument,
    ExtractedNode,
    ExtractedEdge,
    ExtractedState,
    extract_structure
)
from pdca.core.config import (
    WorkflowConfig,
    WorkflowMeta,
    NodeDefinition,
    EdgeDefinition,
    StateDefinition
)


class TestPromptTemplates:
    """PromptTemplates测试"""
    
    def test_get_node_refinement_prompt(self):
        """测试获取节点细化prompt"""
        prompt = PromptTemplates.get_node_refinement_prompt(
            node_name="测试节点",
            node_description="这是一个测试节点",
            node_type="tool"
        )
        
        assert "测试节点" in prompt
        assert "这是一个测试节点" in prompt
        assert "tool" in prompt
    
    def test_get_workflow_optimization_prompt(self):
        """测试获取工作流优化prompt"""
        nodes = [
            {"name": "节点1", "description": "描述1"},
            {"name": "节点2", "description": "描述2"}
        ]
        edges = [
            {"source": "n1", "target": "n2"}
        ]
        
        prompt = PromptTemplates.get_workflow_optimization_prompt(
            workflow_description="测试工作流",
            nodes=nodes,
            edges=edges
        )
        
        assert "测试工作流" in prompt
        assert "节点1" in prompt
        assert "n1 -> n2" in prompt
    
    def test_get_config_generation_prompt(self):
        """测试获取配置生成prompt"""
        prompt = PromptTemplates.get_config_generation_prompt(
            workflow_name="测试工作流",
            workflow_description="这是一个测试工作流",
            nodes=[{"name": "节点1", "type": "tool"}],
            edges=[{"source": "n1", "target": "n2", "type": "sequential"}],
            states=[{"field_name": "result", "type": "string"}]
        )
        
        assert "测试工作流" in prompt
        assert "节点1" in prompt


class TestConfigGenerator:
    """ConfigGenerator测试"""
    
    def test_generate_workflow_id_format(self):
        """测试工作流ID格式"""
        generator = ConfigGenerator()
        workflow_id = generator._generate_workflow_id()
        
        assert workflow_id.startswith("wf_")
        # "wf_" (3) + hex[:12] (12) = 15
        assert len(workflow_id) == 15
    
    def test_generate_version_default(self):
        """测试默认版本号"""
        generator = ConfigGenerator()
        version = generator._generate_version()
        
        assert version == "0.1.0"
    
    def test_generate_timestamp_format(self):
        """测试时间戳格式"""
        generator = ConfigGenerator()
        timestamp = generator._generate_timestamp()
        
        assert timestamp.endswith("Z")
        assert "T" in timestamp
    
    def test_convert_node(self):
        """测试节点转换"""
        generator = ConfigGenerator()
        
        extracted = ExtractedNode(
            node_id="n1",
            name="测试节点",
            type="tool",
            description="测试描述",
            inputs=["input1"],
            outputs=["output1"],
            config={"timeout": 30}
        )
        
        node_def = generator._convert_node(extracted)
        
        assert isinstance(node_def, NodeDefinition)
        assert node_def.node_id == "n1"
        assert node_def.name == "测试节点"
        assert node_def.type == "tool"
        assert node_def.inputs == ["input1"]
        assert node_def.config == {"timeout": 30}
    
    def test_convert_edge(self):
        """测试边转换"""
        generator = ConfigGenerator()
        
        extracted = ExtractedEdge(
            source="n1",
            target="n2",
            condition="x > 0",
            type="conditional"
        )
        
        edge_def = generator._convert_edge(extracted)
        
        assert isinstance(edge_def, EdgeDefinition)
        assert edge_def.source == "n1"
        assert edge_def.target == "n2"
        assert edge_def.condition == "x > 0"
        assert edge_def.type == "conditional"
    
    def test_convert_state(self):
        """测试状态转换"""
        generator = ConfigGenerator()
        
        extracted = ExtractedState(
            field_name="result",
            type="string",
            default_value="",
            description="结果字段",
            required=True
        )
        
        state_def = generator._convert_state(extracted)
        
        assert isinstance(state_def, StateDefinition)
        assert state_def.field_name == "result"
        assert state_def.type == "string"
        assert state_def.required is True
    
    def test_generate_from_document(self):
        """测试从文档生成配置"""
        generator = ConfigGenerator()
        
        document = StructuredDocument(
            nodes=[
                ExtractedNode(node_id="n1", name="开始", type="control"),
                ExtractedNode(node_id="n2", name="处理", type="tool"),
                ExtractedNode(node_id="n3", name="结束", type="control")
            ],
            edges=[
                ExtractedEdge(source="n1", target="n2"),
                ExtractedEdge(source="n2", target="n3")
            ],
            states=[
                ExtractedState(field_name="result", type="string")
            ],
            raw_text="测试工作流"
        )
        
        config = generator.generate(document, "测试工作流")
        
        assert isinstance(config, WorkflowConfig)
        assert config.meta.name == "测试工作流"
        assert len(config.nodes) == 3
        assert len(config.edges) == 2
        assert len(config.state) == 1
        assert config.meta.workflow_id.startswith("wf_")
    
    def test_generate_infers_description(self):
        """测试描述推断"""
        generator = ConfigGenerator()
        
        short_text = "简短描述"
        document = StructuredDocument(
            nodes=[],
            edges=[],
            states=[],
            raw_text=short_text
        )
        
        config = generator.generate(document)
        assert config.meta.description == short_text
        
        long_text = "a" * 200
        document.raw_text = long_text
        config = generator.generate(document)
        assert len(config.meta.description) == 100
        assert config.meta.description.endswith("...")
    
    def test_generate_global_config(self):
        """测试全局配置生成"""
        generator = ConfigGenerator()
        
        document = StructuredDocument(
            nodes=[],
            edges=[],
            states=[],
            raw_text="测试",
            missing_info=["缺失信息1"]
        )
        
        config = generator.generate(document)
        
        assert config.config["extraction_version"] == "1.0"
        assert config.config["has_missing_info"] is True
        assert "缺失信息1" in config.config["warnings"]
    
    def test_generate_with_template(self):
        """测试使用模板生成"""
        generator = ConfigGenerator(config_template={"custom": "value"})
        
        document = StructuredDocument(
            nodes=[],
            edges=[],
            states=[],
            raw_text="测试"
        )
        
        config = generator.generate(document)
        
        assert config.config["custom"] == "value"
    
    def test_generate_empty_document(self):
        """测试空文档生成"""
        generator = ConfigGenerator()
        
        document = StructuredDocument(
            nodes=[],
            edges=[],
            states=[],
            raw_text=""
        )
        
        config = generator.generate(document)
        
        assert isinstance(config, WorkflowConfig)
        assert config.meta.name.startswith("工作流_")


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_generate_config(self):
        """测试快速生成函数"""
        document = StructuredDocument(
            nodes=[
                ExtractedNode(node_id="n1", name="节点", type="tool")
            ],
            edges=[],
            states=[],
            raw_text="测试"
        )
        
        config = generate_config(document, "快速生成")
        
        assert config.meta.name == "快速生成"
        assert len(config.nodes) == 1
    
    def test_generate_config_with_refinement_no_llm(self):
        """测试无LLM时降级为普通生成"""
        document = StructuredDocument(
            nodes=[
                ExtractedNode(node_id="n1", name="节点", type="tool")
            ],
            edges=[],
            states=[],
            raw_text="测试"
        )
        
        config = generate_config_with_refinement(document, None)
        
        assert isinstance(config, WorkflowConfig)


class TestIntegration:
    """集成测试"""
    
    def test_extractor_to_config_pipeline(self):
        """测试从抽取到配置的完整流程"""
        # 1. 模拟抽取
        document = extract_structure(
            "首先获取数据，然后分析数据，最后生成报告",
            llm=MagicMock()
        )
        
        # 2. 生成配置
        config = generate_config(document, "数据分析工作流")
        
        # 3. 验证结果
        assert isinstance(config, WorkflowConfig)
        assert config.meta.name == "数据分析工作流"
        assert len(config.nodes) >= 1
        assert config.meta.workflow_id.startswith("wf_")
        assert config.meta.version == "0.1.0"
        # 时间戳应该是有效的ISO格式
        assert "T" in config.meta.created_at
    
    def test_config_roundtrip(self):
        """测试配置序列化"""
        from pdca.core.config import Config
        
        # 生成配置
        generator = ConfigGenerator()
        document = StructuredDocument(
            nodes=[
                ExtractedNode(node_id="n1", name="开始", type="control"),
                ExtractedNode(node_id="n2", name="处理", type="tool"),
                ExtractedNode(node_id="n3", name="结束", type="control")
            ],
            edges=[
                ExtractedEdge(source="n1", target="n2"),
                ExtractedEdge(source="n2", target="n3")
            ],
            states=[
                ExtractedState(field_name="result", type="string", required=True)
            ],
            raw_text="测试流程"
        )
        
        config = generator.generate(document, "测试流程")
        
        # 序列化为字典
        config_dict = config.model_dump()
        assert "meta" in config_dict
        assert "nodes" in config_dict
        assert "edges" in config_dict
        assert "state" in config_dict
        
        # 反序列化
        restored = WorkflowConfig(**config_dict)
        assert restored.meta.name == config.meta.name
        assert len(restored.nodes) == len(config.nodes)
