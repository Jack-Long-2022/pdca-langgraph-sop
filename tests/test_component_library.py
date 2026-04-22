"""组件库测试模块

测试 ComponentLibrary 的数据模型、关键词匹配、查找/保存操作和集成功能。
"""

import json
import pytest
from pathlib import Path
from pdca.core.component_library import (
    NodeTemplate, EdgeTemplate, StateTemplate, PromptTemplate,
    ComponentLibraryIndex, ComponentLibrary,
    _extract_keywords, _keyword_match_score,
)
from pdca.core.config import (
    WorkflowConfig, WorkflowMeta, NodeDefinition, EdgeDefinition, StateDefinition,
)


# ============== 测试夹具 ==============

@pytest.fixture
def library(tmp_path):
    """创建临时组件库"""
    return ComponentLibrary(library_dir=str(tmp_path / "test_components"))


@pytest.fixture
def sample_config():
    """创建示例 WorkflowConfig"""
    return WorkflowConfig(
        meta=WorkflowMeta(
            workflow_id="wf_test",
            name="test_workflow",
            version="0.1.0",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        ),
        nodes=[
            NodeDefinition(
                node_id="n1", name="获取数据", type="tool",
                description="从API获取数据", inputs=["url"], outputs=["data"],
            ),
            NodeDefinition(
                node_id="n2", name="分析结果", type="thought",
                description="分析处理结果",
            ),
        ],
        edges=[
            EdgeDefinition(source="n1", target="n2", type="sequential"),
        ],
        state=[
            StateDefinition(field_name="result", type="string", required=True, description="处理结果"),
            StateDefinition(field_name="status", type="string", required=False),
        ],
    )


# ============== 关键词提取测试 ==============

class TestExtractKeywords:

    def test_english_words(self):
        kws = _extract_keywords("fetch API data from endpoint")
        assert "fetch" in kws
        assert "api" in kws
        assert "data" in kws
        assert "endpoint" in kws

    def test_chinese_words(self):
        kws = _extract_keywords("获取API数据并分析结果")
        assert "获取" in kws
        # "分析结果" 或 "分析" 都可以
        assert any("分析" in kw for kw in kws)

    def test_empty_input(self):
        assert _extract_keywords("") == []
        assert _extract_keywords(None) == []

    def test_stop_words_filtered(self):
        kws = _extract_keywords("the data is in the system")
        assert "the" not in kws
        assert "data" in kws
        assert "system" in kws

    def test_mixed_chinese_english(self):
        kws = _extract_keywords("调用call API接口")
        assert "调用" in kws
        assert "call" in kws


class TestKeywordMatchScore:

    def test_perfect_match(self):
        score = _keyword_match_score(["api", "data"], ["api", "data", "fetch"])
        assert score == 1.0

    def test_partial_match(self):
        score = _keyword_match_score(["api", "data"], ["api", "result"])
        assert score == 0.5

    def test_no_match(self):
        score = _keyword_match_score(["api", "data"], ["user", "input"])
        assert score == 0.0

    def test_empty_query(self):
        score = _keyword_match_score([], ["api", "data"])
        assert score == 0.0

    def test_empty_template(self):
        score = _keyword_match_score(["api"], [])
        assert score == 0.0


# ============== 数据模型测试 ==============

class TestDataModels:

    def test_node_template(self):
        t = NodeTemplate(
            template_id="nt_abc123", name="获取数据",
            name_keywords=["获取", "数据"], type="tool",
            description="从API获取数据",
        )
        assert t.name == "获取数据"
        assert t.usage_count == 0

    def test_edge_template(self):
        t = EdgeTemplate(
            template_id="et_abc123",
            source_type="tool", target_type="thought",
            edge_type="sequential",
        )
        assert t.edge_type == "sequential"

    def test_state_template(self):
        t = StateTemplate(
            template_id="st_abc123",
            field_name="result", type="string",
            name_keywords=["result"],
        )
        assert t.field_name == "result"

    def test_prompt_template(self):
        t = PromptTemplate(
            template_id="pt_abc123",
            task_type="extract", name="extract_nodes",
            content="提取节点信息",
        )
        assert t.task_type == "extract"

    def test_library_index_serialization(self):
        index = ComponentLibraryIndex()
        index.nodes["nt_1"] = NodeTemplate(
            template_id="nt_1", name="test", name_keywords=["test"], type="tool",
        )
        data = index.model_dump()
        assert "nodes" in data
        assert "nt_1" in data["nodes"]
        assert data["nodes"]["nt_1"]["name"] == "test"


# ============== ComponentLibrary 测试 ==============

class TestComponentLibrary:

    def test_init_creates_directory(self, tmp_path):
        lib_dir = tmp_path / "my_components"
        lib = ComponentLibrary(library_dir=str(lib_dir))
        assert lib_dir.exists()

    def test_save_and_lookup_node(self, library):
        node = NodeDefinition(
            node_id="n1", name="获取API数据", type="tool",
            description="从外部API获取数据",
            inputs=["url"], outputs=["data"],
        )
        library.save_node(node, "test_workflow")

        # 查找相似节点
        match = library.lookup_node("获取API数据", "从外部API获取数据")
        assert match is not None
        assert match.name == "获取API数据"
        assert match.inputs == ["url"]

    def test_lookup_node_no_match(self, library):
        match = library.lookup_node("完全不相关的查询", "没有匹配")
        assert match is None

    def test_lookup_node_with_type_filter(self, library):
        node = NodeDefinition(
            node_id="n1", name="分析数据", type="thought",
        )
        library.save_node(node, "test_workflow")

        # 类型匹配
        match = library.lookup_node("分析数据", node_type="thought")
        assert match is not None

        # 类型不匹配
        match = library.lookup_node("分析数据", node_type="tool")
        assert match is None

    def test_save_and_lookup_state(self, library):
        state = StateDefinition(
            field_name="result", type="string",
            description="处理结果", required=True,
        )
        library.save_state(state, "test_workflow")

        match = library.lookup_state("result", "string")
        assert match is not None
        assert match.field_name == "result"

    def test_save_and_lookup_prompt(self, library):
        library.save_prompt("extract", "extract_nodes", "提取节点信息", "test_workflow")

        match = library.lookup_prompt("extract", "extract_nodes")
        assert match is not None
        assert match.content == "提取节点信息"

    def test_save_deduplicates(self, library):
        node = NodeDefinition(node_id="n1", name="获取数据", type="tool")
        library.save_node(node, "wf1")
        library.save_node(node, "wf2")

        # 不应该创建重复模板
        assert len(library._index.nodes) == 1

    def test_save_workflow_config(self, library, sample_config):
        library.save_workflow_config(sample_config, "test_workflow")

        assert len(library._index.nodes) == 2
        assert len(library._index.edges) == 1
        assert len(library._index.states) == 2

    def test_usage_count_increments(self, library):
        node = NodeDefinition(node_id="n1", name="获取数据", type="tool")
        library.save_node(node, "test_workflow")
        assert library._index.nodes[list(library._index.nodes.keys())[0]].usage_count == 0

        # lookup 会增加 usage_count
        match = library.lookup_node("获取数据")
        assert match is not None
        assert match.usage_count >= 1

    def test_persistence_save_and_reload(self, tmp_path):
        lib_dir = str(tmp_path / "persist_test")

        # 保存
        lib1 = ComponentLibrary(library_dir=lib_dir)
        node = NodeDefinition(node_id="n1", name="获取数据", type="tool")
        lib1.save_node(node, "test_workflow")

        # 重新加载
        lib2 = ComponentLibrary(library_dir=lib_dir)
        match = lib2.lookup_node("获取数据")
        assert match is not None
        assert match.name == "获取数据"

    def test_get_statistics(self, library):
        node = NodeDefinition(node_id="n1", name="test", type="tool")
        library.save_node(node, "test_workflow")

        stats = library.get_statistics()
        assert stats["total_templates"] == 1
        assert stats["node_templates"] == 1

    def test_prune_unused(self, library):
        # 创建多个模板
        for i in range(5):
            node = NodeDefinition(node_id=f"n{i}", name=f"节点{i}", type="tool")
            library.save_node(node, "test_workflow")

        pruned = library.prune_unused(keep_recent=2)
        assert pruned == 3
        assert len(library._index.nodes) == 2

    def test_list_templates(self, library, sample_config):
        library.save_workflow_config(sample_config, "test_workflow")

        all_templates = library.list_templates()
        assert len(all_templates) == 5  # 2 nodes + 1 edge + 2 states

        node_templates = library.list_templates(category="node")
        assert len(node_templates) == 2


# ============== 集成测试 ==============

class TestDiscoverReusableComponents:

    def test_discover_from_review_result(self, library, sample_config):
        """测试从复盘结果中发现可复用组件"""
        # 模拟 GRBARPReviewResult
        class MockReviewResult:
            result_analysis = {
                "success_factors": ["获取数据节点执行成功"],
                "failure_factors": [],
            }
            action_planning = {
                "actions": [
                    {"action": "优化分析结果节点", "priority": "high", "steps": ["增加日志"]},
                ]
            }
            goal_review = {}

        review = MockReviewResult()
        discoveries = library.discover_reusable_components(review, sample_config, "test_workflow")

        # 应该发现：1个节点 + 1个必需状态 + 1个提示
        assert len(discoveries) >= 2

        categories = [d["category"] for d in discoveries]
        assert "state" in categories  # result 字段是 required=True

    def test_discover_saves_to_library(self, library, sample_config):
        """测试发现结果自动保存到库"""
        class MockReviewResult:
            result_analysis = {"success_factors": [], "failure_factors": []}
            action_planning = {"actions": []}
            goal_review = {}

        review = MockReviewResult()
        library.discover_reusable_components(review, sample_config, "test_workflow")

        # 必需状态应该被保存
        assert len(library._index.states) >= 1


class TestConfigGeneratorIntegration:

    def test_enhance_with_library_fills_missing(self, library):
        """测试组件库增强填充缺失字段"""
        from pdca.plan.config_generator import ConfigGenerator
        from pdca.plan.extractor import StructuredDocument, ExtractedNode

        # 先保存一个完整模板到库
        node = NodeDefinition(
            node_id="n1", name="获取数据", type="tool",
            description="从API获取数据",
            inputs=["url"], outputs=["data"],
            config={"timeout": 30},
        )
        library.save_node(node, "existing_workflow")

        # 创建一个缺失字段的新文档
        doc = StructuredDocument(
            nodes=[ExtractedNode(
                node_id="n_new", name="获取数据", type="tool",
                description="", inputs=[], outputs=[], config={},
            )],
            edges=[], states=[],
            raw_text="获取数据",
        )

        # generate_with_refinement 会触发 _enhance_with_library
        generator = ConfigGenerator(component_library=library)
        config = generator.generate_with_refinement(doc, llm=None, workflow_name="new_workflow")

        # 增强后应填充缺失字段
        assert config.nodes[0].description == "从API获取数据"
        assert config.nodes[0].inputs == ["url"]

    def test_enhance_does_not_overwrite(self, library):
        """测试组件库增强不覆盖已有数据"""
        from pdca.plan.config_generator import ConfigGenerator
        from pdca.plan.extractor import StructuredDocument, ExtractedNode

        # 保存模板
        node = NodeDefinition(
            node_id="n1", name="获取数据", type="tool",
            description="旧描述",
            inputs=["old_url"], outputs=["old_data"],
        )
        library.save_node(node, "existing_workflow")

        # 创建已有字段的新配置
        doc = StructuredDocument(
            nodes=[ExtractedNode(
                node_id="n_new", name="获取数据", type="tool",
                description="新描述", inputs=["new_url"], outputs=["new_data"], config={},
            )],
            edges=[], states=[],
            raw_text="获取数据",
        )

        generator = ConfigGenerator(component_library=library)
        config = generator.generate(doc)

        # 不应该被覆盖
        assert config.nodes[0].description == "新描述"
        assert config.nodes[0].inputs == ["new_url"]

    def test_no_library_is_unchanged(self):
        """测试不传 component_library 时行为不变"""
        from pdca.plan.config_generator import ConfigGenerator
        from pdca.plan.extractor import StructuredDocument, ExtractedNode

        doc = StructuredDocument(
            nodes=[ExtractedNode(
                node_id="n1", name="测试", type="tool",
                description="测试节点", inputs=[], outputs=[], config={},
            )],
            edges=[], states=[],
            raw_text="测试",
        )

        generator = ConfigGenerator()  # 不传 component_library
        config = generator.generate(doc)
        assert config.nodes[0].name == "测试"
