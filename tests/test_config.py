"""测试配置管理模块"""

import pytest
import tempfile
import json
from pathlib import Path

from pdca.core.config import (
    Config,
    WorkflowMeta,
    NodeDefinition,
    EdgeDefinition,
    StateDefinition,
    WorkflowConfig
)


class TestConfig:
    """Config类测试"""
    
    def test_init_creates_config_dir(self, tmp_path):
        """测试初始化创建配置目录"""
        config = Config(config_dir=tmp_path / "config")
        assert config.config_dir.exists()
    
    def test_save_and_load_json(self, tmp_path):
        """测试JSON保存和加载"""
        config = Config(config_dir=tmp_path)
        test_data = {"key": "value", "number": 42}
        
        config.save_json("test.json", test_data)
        loaded = config.load_json("test.json")
        
        assert loaded == test_data
    
    def test_save_and_load_workflow_config(self, tmp_path):
        """测试工作流配置保存和加载"""
        config = Config(config_dir=tmp_path)
        
        workflow_config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="test-123",
                name="测试工作流",
                created_at="2026-04-20T00:00:00",
                updated_at="2026-04-20T00:00:00"
            ),
            nodes=[
                NodeDefinition(
                    node_id="node1",
                    name="开始节点",
                    type="tool"
                )
            ]
        )
        
        config.save_workflow_config("workflow.json", workflow_config)
        loaded = config.load_workflow_config("workflow.json")
        
        assert loaded.meta.workflow_id == "test-123"
        assert len(loaded.nodes) == 1
        assert loaded.nodes[0].name == "开始节点"


class TestNodeDefinition:
    """NodeDefinition模型测试"""
    
    def test_valid_node_type(self):
        """测试有效的节点类型"""
        node = NodeDefinition(
            node_id="n1",
            name="测试节点",
            type="tool"
        )
        assert node.type == "tool"
    
    def test_invalid_node_type_raises(self):
        """测试无效的节点类型"""
        with pytest.raises(ValueError):
            NodeDefinition(
                node_id="n1",
                name="测试节点",
                type="invalid"
            )
    
    def test_default_values(self):
        """测试默认值"""
        node = NodeDefinition(
            node_id="n1",
            name="测试节点",
            type="thought"
        )
        assert node.inputs == []
        assert node.outputs == []
        assert node.config == {}
        assert node.description is None


class TestEdgeDefinition:
    """EdgeDefinition模型测试"""
    
    def test_sequential_edge(self):
        """测试顺序边"""
        edge = EdgeDefinition(
            source="n1",
            target="n2"
        )
        assert edge.type == "sequential"
        assert edge.condition is None
    
    def test_conditional_edge(self):
        """测试条件边"""
        edge = EdgeDefinition(
            source="n1",
            target="n2",
            condition="x > 0",
            type="conditional"
        )
        assert edge.type == "conditional"
        assert edge.condition == "x > 0"


class TestWorkflowConfig:
    """WorkflowConfig模型测试"""
    
    def test_complete_workflow_config(self):
        """测试完整工作流配置"""
        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf-001",
                name="完整工作流",
                version="1.0.0",
                description="这是一个测试工作流",
                created_at="2026-04-20T00:00:00",
                updated_at="2026-04-20T00:00:00"
            ),
            nodes=[
                NodeDefinition(
                    node_id="start",
                    name="开始",
                    type="control"
                ),
                NodeDefinition(
                    node_id="process",
                    name="处理",
                    type="tool"
                ),
                NodeDefinition(
                    node_id="end",
                    name="结束",
                    type="control"
                )
            ],
            edges=[
                EdgeDefinition(source="start", target="process"),
                EdgeDefinition(source="process", target="end")
            ],
            state=[
                StateDefinition(
                    field_name="result",
                    type="string",
                    description="处理结果"
                )
            ]
        )
        
        assert config.meta.name == "完整工作流"
        assert len(config.nodes) == 3
        assert len(config.edges) == 2
        assert config.state[0].field_name == "result"
