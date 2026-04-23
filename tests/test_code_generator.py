"""测试代码生成模块"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import os
from pdca.do_.code_generator import (
    ProjectTemplate,
    NodeCodeGenerator,
    CodeGenerator,
    WorkflowBuilder,
    generate_code,
    build_langgraph_code
)
from pdca.core.config import (
    WorkflowConfig,
    WorkflowMeta,
    NodeDefinition,
    EdgeDefinition,
    StateDefinition
)


class TestProjectTemplate:
    """ProjectTemplate测试"""
    
    def test_get_main_template(self):
        """测试主程序模板"""
        template = ProjectTemplate.get_main_template(
            workflow_name="测试工作流",
            version="1.0.0"
        )
        
        assert "测试工作流" in template
        assert "1.0.0" in template
        assert "def main()" in template
    
    def test_get_node_handler_template(self):
        """测试节点处理模板"""
        template = ProjectTemplate.get_node_handler_template(
            node_id="node_001",
            node_name="测试节点",
            node_type="tool",
            description="测试描述",
            inputs=["input1"],
            outputs=["output1"]
        )
        
        assert "node_001" in template
        assert "测试节点" in template
        assert "tool" in template
        assert "handle_node_001" in template
    
    def test_get_tool_template(self):
        """测试工具模板"""
        template = ProjectTemplate.get_tool_template()
        
        assert "ToolRegistry" in template
        assert "http_request" in template
        assert "json_parser" in template
    

class TestNodeCodeGenerator:
    """NodeCodeGenerator测试"""
    
    def test_generate_node_code(self):
        """测试生成节点代码"""
        generator = NodeCodeGenerator()
        
        node = NodeDefinition(
            node_id="test_node",
            name="测试节点",
            type="tool",
            description="测试描述",
            inputs=["input1", "input2"],
            outputs=["output1"]
        )
        
        code = generator.generate(node)
        
        assert "handle_test_node" in code
        assert "测试节点" in code
        assert "tool" in code
        assert "input1" in code
        assert "output1" in code
    
    def test_generate_all_nodes(self):
        """测试批量生成节点"""
        generator = NodeCodeGenerator()
        
        nodes = [
            NodeDefinition(node_id="n1", name="节点1", type="tool"),
            NodeDefinition(node_id="n2", name="节点2", type="thought"),
        ]
        
        result = generator.generate_all(nodes)
        
        assert len(result) == 2
        assert "n1" in result
        assert "n2" in result
        assert "handle_n1" in result["n1"]
        assert "handle_n2" in result["n2"]


class TestCodeGenerator:
    """CodeGenerator测试"""
    
    @pytest.fixture
    def sample_config(self):
        """创建示例配置"""
        return WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf_test",
                name="测试工作流",
                version="1.0.0",
                description="这是一个测试工作流",
                created_at="2026-04-20T00:00:00Z",
                updated_at="2026-04-20T00:00:00Z"
            ),
            nodes=[
                NodeDefinition(
                    node_id="start",
                    name="开始",
                    type="control",
                    description="工作流入口"
                ),
                NodeDefinition(
                    node_id="process",
                    name="处理",
                    type="tool",
                    description="数据处理"
                ),
                NodeDefinition(
                    node_id="end",
                    name="结束",
                    type="control",
                    description="工作流出口"
                )
            ],
            edges=[
                EdgeDefinition(source="start", target="process"),
                EdgeDefinition(source="process", target="end")
            ],
            state=[
                StateDefinition(field_name="input_data", type="string"),
                StateDefinition(field_name="result", type="any")
            ]
        )
    
    def test_create_directories(self, tmp_path):
        """测试目录创建"""
        generator = CodeGenerator()

        test_dir = tmp_path / "test_project"
        generator._create_directories(test_dir)

        assert test_dir.exists()
        assert (test_dir / "nodes").exists()
        assert (test_dir / "config").exists()
    
    def test_write_file(self, tmp_path):
        """测试文件写入"""
        generator = CodeGenerator()
        
        test_file = tmp_path / "test.txt"
        generator._write_file(test_file, "test content")
        
        assert test_file.exists()
        assert test_file.read_text() == "test content"
    
    def test_generate_project(self, sample_config, tmp_path):
        """测试项目生成"""
        generator = CodeGenerator()

        output_dir = tmp_path / "generated_project"
        result = generator.generate_project(sample_config, output_dir)

        # 验证生成的核心文件（3样东西）
        assert len(result) == 3
        assert (output_dir / "main.py").exists()
        assert (output_dir / "config" / "workflow.json").exists()
        assert (output_dir / "nodes" / "workflow_graph.py").exists()

        # 验证不生成多余文件
        assert not (output_dir / "README.md").exists()
        assert not (output_dir / "requirements.txt").exists()
        assert not (output_dir / "pdca").exists()
        assert not (output_dir / "tests").exists()
    
    def test_generate_project_creates_valid_files(self, sample_config, tmp_path):
        """测试生成有效文件"""
        generator = CodeGenerator()

        output_dir = tmp_path / "generated_project"
        generator.generate_project(sample_config, output_dir)

        # 验证main.py可以编译
        main_file = output_dir / "main.py"
        compile(main_file.read_text(), str(main_file), 'exec')

        # 验证workflow_graph.py包含节点函数
        graph_code = (output_dir / "nodes" / "workflow_graph.py").read_text()
        assert "WorkflowState" in graph_code


class TestWorkflowBuilder:
    """WorkflowBuilder测试"""
    
    def test_python_type_conversion(self):
        """测试Python类型转换"""
        builder = WorkflowBuilder()
        
        assert builder._python_type("string") == "str"
        assert builder._python_type("integer") == "int"
        assert builder._python_type("boolean") == "bool"
        assert builder._python_type("array") == "list"
        assert builder._python_type("any") == "Any"
    
    def test_generate_node_function(self):
        """测试节点函数生成"""
        builder = WorkflowBuilder()
        
        node = NodeDefinition(
            node_id="test_node",
            name="测试节点",
            type="tool",
            description="测试描述"
        )
        
        code = builder._generate_node_function(node)
        
        assert "def test_node_handler" in code
        assert "测试节点" in code
        assert "tool" in code
    
    def test_build_state_graph_code(self):
        """测试StateGraph代码生成"""
        builder = WorkflowBuilder()
        
        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf_test",
                name="测试",
                created_at="2026-04-20T00:00:00Z",
                updated_at="2026-04-20T00:00:00Z"
            ),
            nodes=[
                NodeDefinition(node_id="n1", name="节点1", type="tool"),
                NodeDefinition(node_id="n2", name="节点2", type="thought")
            ],
            edges=[
                EdgeDefinition(source="n1", target="n2")
            ],
            state=[
                StateDefinition(field_name="data", type="string")
            ]
        )
        
        code = builder.build_state_graph_code(config)
        
        assert "class WorkflowState" in code
        assert "TypedDict" in code
        assert "StateGraph" in code
        assert "def n1_handler" in code
        assert "def n2_handler" in code
        assert 'graph.add_edge("n1", "n2")' in code


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_generate_code(self, tmp_path):
        """测试快速生成代码"""
        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf_quick",
                name="快速生成",
                created_at="2026-04-20T00:00:00Z",
                updated_at="2026-04-20T00:00:00Z"
            ),
            nodes=[
                NodeDefinition(node_id="n1", name="节点1", type="tool")
            ],
            edges=[],
            state=[]
        )
        
        output_dir = tmp_path / "quick_project"
        result = generate_code(config, output_dir)
        
        assert len(result) > 0
        assert (output_dir / "main.py").exists()
    
    def test_build_langgraph_code(self):
        """测试快速构建LangGraph"""
        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf_langgraph",
                name="LangGraph测试",
                created_at="2026-04-20T00:00:00Z",
                updated_at="2026-04-20T00:00:00Z"
            ),
            nodes=[
                NodeDefinition(node_id="start", name="开始", type="control"),
                NodeDefinition(node_id="process", name="处理", type="tool")
            ],
            edges=[
                EdgeDefinition(source="start", target="process")
            ],
            state=[]
        )
        
        code = build_langgraph_code(config)
        
        assert "WorkflowState" in code
        assert "start_handler" in code
        assert "process_handler" in code


class TestIntegration:
    """集成测试"""
    
    def test_full_generation_pipeline(self, tmp_path):
        """测试完整生成流程"""
        # 创建配置
        from pdca.plan.config_generator import generate_config
        from pdca.plan.extractor import extract_structure
        
        # 1. 抽取结构
        document = extract_structure(
            "首先获取数据，然后分析数据，最后生成报告",
            llm=MagicMock()
        )
        
        # 2. 生成配置
        config = generate_config(document, "数据分析工作流")
        
        # 3. 生成代码
        output_dir = tmp_path / "workflow_project"
        files = generate_code(config, output_dir)
        
        # 4. 验证
        assert len(files) > 0
        assert (output_dir / "main.py").exists()
        
        # 验证代码语法
        main_code = (output_dir / "main.py").read_text()
        compile(main_code, "main.py", 'exec')
        
        # 验证配置文件有效
        import json
        config_data = json.loads((output_dir / "config" / "workflow.json").read_text())
        assert config_data["meta"]["name"] == "数据分析工作流"
