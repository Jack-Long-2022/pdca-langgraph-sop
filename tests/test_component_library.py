"""组件库测试模块

测试 ComponentLibrary 的数据模型、关键词匹配、查找/保存操作和集成功能。
"""

import json
import pytest
import yaml
from pathlib import Path
from pdca.core.component_library import (
    NodeTemplate, EdgeTemplate, StateTemplate, PromptTemplate,
    ComponentLibraryIndex, CatalogEntry, ComponentLibrary,
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

        # 验证生成了 YAML 文件
        assert (Path(lib_dir) / "catalog.yaml").exists()
        assert (Path(lib_dir) / "nodes.yaml").exists()

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


# ============== YAML 存储测试 ==============

class TestYAMLStorage:

    def test_saves_as_yaml_files(self, tmp_path):
        lib = ComponentLibrary(library_dir=str(tmp_path / "yaml_test"))
        node = NodeDefinition(node_id="n1", name="获取数据", type="tool")
        lib.save_node(node, "test_workflow")

        lib_dir = tmp_path / "yaml_test"
        assert (lib_dir / "catalog.yaml").exists()
        assert (lib_dir / "nodes.yaml").exists()
        assert (lib_dir / "edges.yaml").exists()
        assert (lib_dir / "states.yaml").exists()
        assert (lib_dir / "prompts.yaml").exists()

    def test_catalog_contains_entries(self, tmp_path):
        lib = ComponentLibrary(library_dir=str(tmp_path / "cat_test"))
        node = NodeDefinition(
            node_id="n1", name="获取数据", type="tool",
            description="从API获取数据",
        )
        lib.save_node(node, "test_workflow")

        with open(tmp_path / "cat_test" / "catalog.yaml", 'r', encoding='utf-8') as f:
            catalog = yaml.safe_load(f)

        assert catalog["total_components"] >= 1
        assert any(c["name"] == "获取数据" for c in catalog["components"])
        assert any(c["category"] == "node" for c in catalog["components"])

    def test_yaml_utf8_encoding(self, tmp_path):
        lib = ComponentLibrary(library_dir=str(tmp_path / "utf8_test"))
        node = NodeDefinition(
            node_id="n1", name="获取数据", type="tool",
            description="包含中文的描述",
        )
        lib.save_node(node, "中文工作流")

        with open(tmp_path / "utf8_test" / "nodes.yaml", 'r', encoding='utf-8') as f:
            content = f.read()
        # 中文不应该被转义为 \uXXXX
        assert "获取数据" in content
        assert "包含中文" in content

    def test_migrate_from_legacy_json(self, tmp_path):
        """测试旧版 index.json 自动迁移到 YAML"""
        lib_dir = tmp_path / "migrate_test"
        lib_dir.mkdir()

        # 创建旧版 index.json
        old_data = {
            "nodes": {
                "nt_1": {
                    "template_id": "nt_1", "name": "测试节点",
                    "name_keywords": ["测试", "节点", "测试节点"], "type": "tool",
                    "description": "", "inputs": [], "outputs": [],
                    "config": {}, "source_workflow": "", "usage_count": 0,
                    "last_used": "", "created_at": "2026-01-01T00:00:00",
                }
            },
            "edges": {}, "states": {}, "prompts": {},
            "saved_at": "2026-01-01T00:00:00",
        }
        with open(lib_dir / "index.json", 'w', encoding='utf-8') as f:
            json.dump(old_data, f, ensure_ascii=False)

        # 加载时应自动迁移
        lib = ComponentLibrary(library_dir=str(lib_dir))
        match = lib.lookup_node("测试节点")
        assert match is not None
        assert match.name == "测试节点"

        # 旧文件应被备份
        assert (lib_dir / "index.json.bak").exists()
        # 新 YAML 文件应存在
        assert (lib_dir / "catalog.yaml").exists()
        assert (lib_dir / "nodes.yaml").exists()

    def test_catalog_entry_model(self):
        entry = CatalogEntry(
            id="nt_abc", category="node", name="获取数据",
            summary="从API获取数据 (tool)", keywords=["获取", "数据"],
        )
        assert entry.category == "node"
        data = entry.model_dump()
        assert data["name"] == "获取数据"


# ============== LLM 匹配测试 ==============

class TestLLMMatching:

    def test_llm_not_used_by_default(self, library):
        """默认不启用 LLM 匹配"""
        # 即使没有 LLM 也应该正常工作（Tier 1 only）
        match = library.lookup_node("完全不相关的查询xyz")
        assert match is None

    def test_llm_lookup_with_mock(self, tmp_path):
        """测试 Mock LLM 语义匹配"""
        lib = ComponentLibrary(library_dir=str(tmp_path / "llm_test"))
        node = NodeDefinition(
            node_id="n1", name="获取API数据", type="tool",
            description="从外部API获取信息",
        )
        lib.save_node(node, "test_workflow")

        # 获取保存的 template_id
        template_id = list(lib._index.nodes.keys())[0]

        # 创建 Mock LLM
        class MockLLM:
            def generate_messages(self, messages, **kwargs):
                return json.dumps({
                    "match_id": template_id,
                    "confidence": 0.85,
                    "reason": "语义匹配：抓取网络接口 ≈ 获取API数据",
                })

        lib._llm = MockLLM()
        lib.enable_llm_matching = True

        # 用 Tier 1 不会匹配的查询触发 LLM
        match = lib.lookup_node("抓取网络接口内容")
        assert match is not None
        assert match.name == "获取API数据"

    def test_llm_returns_null_on_no_match(self, tmp_path):
        """测试 LLM 返回 null 时不匹配"""
        lib = ComponentLibrary(library_dir=str(tmp_path / "llm_null"))
        node = NodeDefinition(node_id="n1", name="获取数据", type="tool")
        lib.save_node(node, "test_workflow")

        class MockLLM:
            def generate_messages(self, messages, **kwargs):
                return json.dumps({
                    "match_id": None,
                    "confidence": 0.0,
                    "reason": "无匹配",
                })

        lib._llm = MockLLM()
        lib.enable_llm_matching = True

        match = lib.lookup_node("完全不相关的查询")
        assert match is None

    def test_use_llm_override(self, tmp_path):
        """测试 use_llm 参数覆盖全局设置"""
        lib = ComponentLibrary(
            library_dir=str(tmp_path / "override_test"),
            enable_llm_matching=False,
        )
        node = NodeDefinition(node_id="n1", name="获取数据", type="tool")
        lib.save_node(node, "test_workflow")

        template_id = list(lib._index.nodes.keys())[0]

        class MockLLM:
            def generate_messages(self, messages, **kwargs):
                return json.dumps({
                    "match_id": template_id,
                    "confidence": 0.9,
                    "reason": "test",
                })

        lib._llm = MockLLM()

        # 全局关闭但调用时启用
        match = lib.lookup_node("完全不相关的查询", use_llm=True)
        assert match is not None

        # 全局关闭且调用时不覆盖 → 不走 LLM
        match = lib.lookup_node("完全不相关的查询xyz", use_llm=False)
        assert match is None


# ============== 批量语义匹配测试 ==============

class TestBatchMatch:

    def _make_mock_llm(self, template_id: str):
        """创建返回固定匹配的 Mock LLM"""
        class MockLLM:
            def generate_messages(self, messages, **kwargs):
                return json.dumps({
                    "matches": [{
                        "query_name": "获取数据",
                        "matched_id": template_id,
                        "confidence": 0.9,
                        "reason": "语义匹配",
                        "enhanced_fields": {
                            "description": "从API获取数据",
                            "inputs": ["url"],
                            "outputs": ["data"],
                        },
                    }]
                })
        return MockLLM()

    def _make_mock_llm_no_match(self):
        """创建返回无匹配的 Mock LLM"""
        class MockLLM:
            def generate_messages(self, messages, **kwargs):
                return json.dumps({"matches": []})
        return MockLLM()

    def test_batch_match_basic(self, tmp_path):
        """基本批量匹配"""
        lib = ComponentLibrary(library_dir=str(tmp_path / "batch_test"))
        node = NodeDefinition(
            node_id="n1", name="获取数据", type="tool",
            description="从API获取数据", inputs=["url"], outputs=["data"],
        )
        lib.save_node(node, "test_workflow")
        template_id = list(lib._index.nodes.keys())[0]

        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf_new", name="new_wf", version="0.1.0",
                created_at="2026-01-01", updated_at="2026-01-01",
            ),
            nodes=[NodeDefinition(node_id="n1", name="获取数据", type="tool")],
            edges=[], state=[],
        )

        llm = self._make_mock_llm(template_id)
        results = lib.batch_match(config, llm=llm)

        assert len(results["nodes"]) == 1
        assert results["nodes"][0]["query_name"] == "获取数据"
        assert results["nodes"][0]["confidence"] == 0.9

    def test_batch_match_no_llm(self, tmp_path):
        """LLM 不可用时返回空结果"""
        lib = ComponentLibrary(library_dir=str(tmp_path / "batch_no_llm"))
        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf1", name="wf1", version="0.1.0",
                created_at="2026-01-01", updated_at="2026-01-01",
            ),
            nodes=[NodeDefinition(node_id="n1", name="test", type="tool")],
            edges=[], state=[],
        )
        results = lib.batch_match(config, llm=None)
        assert results["nodes"] == []

    def test_batch_match_empty_config(self, tmp_path):
        """空配置返回空结果"""
        lib = ComponentLibrary(library_dir=str(tmp_path / "batch_empty"))
        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf1", name="wf1", version="0.1.0",
                created_at="2026-01-01", updated_at="2026-01-01",
            ),
            nodes=[], edges=[], state=[],
        )
        results = lib.batch_match(config, llm=self._make_mock_llm_no_match())
        assert results["nodes"] == []
        assert results["edges"] == []
        assert results["states"] == []

    def test_batch_enhance_fills_missing(self, tmp_path):
        """批量增强填充缺失字段"""
        lib = ComponentLibrary(library_dir=str(tmp_path / "enhance_test"))
        node = NodeDefinition(
            node_id="n1", name="获取数据", type="tool",
            description="从API获取数据", inputs=["url"], outputs=["data"],
        )
        lib.save_node(node, "test_workflow")
        template_id = list(lib._index.nodes.keys())[0]

        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf_new", name="new_wf", version="0.1.0",
                created_at="2026-01-01", updated_at="2026-01-01",
            ),
            nodes=[NodeDefinition(
                node_id="n1", name="获取数据", type="tool",
                description="", inputs=[], outputs=[],
            )],
            edges=[], state=[],
        )

        llm = self._make_mock_llm(template_id)
        enhanced = lib.batch_enhance(config, llm=llm)

        assert enhanced.nodes[0].description == "从API获取数据"
        assert enhanced.nodes[0].inputs == ["url"]
        assert enhanced.nodes[0].outputs == ["data"]

    def test_batch_enhance_does_not_overwrite(self, tmp_path):
        """批量增强不覆盖已有数据"""
        lib = ComponentLibrary(library_dir=str(tmp_path / "enhance_no_overwrite"))
        node = NodeDefinition(
            node_id="n1", name="获取数据", type="tool",
            description="旧描述", inputs=["old_url"], outputs=["old_data"],
        )
        lib.save_node(node, "test_workflow")
        template_id = list(lib._index.nodes.keys())[0]

        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf_new", name="new_wf", version="0.1.0",
                created_at="2026-01-01", updated_at="2026-01-01",
            ),
            nodes=[NodeDefinition(
                node_id="n1", name="获取数据", type="tool",
                description="新描述", inputs=["new_url"], outputs=["new_data"],
            )],
            edges=[], state=[],
        )

        llm = self._make_mock_llm(template_id)
        enhanced = lib.batch_enhance(config, llm=llm)

        # 已有字段不应被覆盖
        assert enhanced.nodes[0].description == "新描述"
        assert enhanced.nodes[0].inputs == ["new_url"]

    def test_batch_match_with_edges(self, tmp_path):
        """批量匹配包含边"""
        lib = ComponentLibrary(library_dir=str(tmp_path / "batch_edges"))
        lib.save_node(NodeDefinition(node_id="n1", name="获取数据", type="tool"), "wf")
        lib.save_node(NodeDefinition(node_id="n2", name="清洗数据", type="tool"), "wf")

        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="wf1", name="wf1", version="0.1.0",
                created_at="2026-01-01", updated_at="2026-01-01",
            ),
            nodes=[
                NodeDefinition(node_id="n1", name="获取数据", type="tool"),
                NodeDefinition(node_id="n2", name="清洗数据", type="tool"),
            ],
            edges=[EdgeDefinition(source="n1", target="n2", type="sequential")],
            state=[],
        )

        class EdgeMockLLM:
            def generate_messages(self, messages, **kwargs):
                return json.dumps({"matches": []})

        results = lib.batch_match(config, llm=EdgeMockLLM())
        assert len(results["edges"]) == 1
        # 无 edge 候选时，query_name 使用原始节点 ID
        assert "n1" in results["edges"][0]["query_name"]


class TestConfigGeneratorBatchIntegration:

    def test_batch_enhance_used_when_llm_available(self, tmp_path):
        """LLM 可用时使用批量匹配"""
        from pdca.plan.config_generator import ConfigGenerator
        from pdca.plan.extractor import StructuredDocument, ExtractedNode

        lib = ComponentLibrary(library_dir=str(tmp_path / "batch_int"))
        node = NodeDefinition(
            node_id="n1", name="获取数据", type="tool",
            description="从API获取数据", inputs=["url"], outputs=["data"],
        )
        lib.save_node(node, "existing")
        template_id = list(lib._index.nodes.keys())[0]

        class MockLLM:
            def generate_messages(self, messages, **kwargs):
                return json.dumps({
                    "matches": [{
                        "query_name": "获取数据",
                        "matched_id": template_id,
                        "confidence": 0.9,
                        "reason": "test",
                        "enhanced_fields": {
                            "description": "从API获取数据",
                            "inputs": ["url"],
                            "outputs": ["data"],
                        },
                    }]
                })

        lib._llm = MockLLM()

        doc = StructuredDocument(
            nodes=[ExtractedNode(
                node_id="n_new", name="获取数据", type="tool",
                description="", inputs=[], outputs=[], config={},
            )],
            edges=[], states=[], raw_text="获取数据",
        )

        generator = ConfigGenerator(component_library=lib)
        config = generator._enhance_with_library(
            generator.generate(doc), MockLLM(), "new_wf"
        )

        # LLM 批量匹配应填充空字段
        assert config.nodes[0].description == "从API获取数据"

    def test_legacy_fallback_when_no_llm(self, tmp_path):
        """LLM 不可用时回退到关键词匹配"""
        from pdca.plan.config_generator import ConfigGenerator
        from pdca.plan.extractor import StructuredDocument, ExtractedNode

        lib = ComponentLibrary(library_dir=str(tmp_path / "legacy_int"))
        node = NodeDefinition(
            node_id="n1", name="获取数据", type="tool",
            description="从API获取数据", inputs=["url"], outputs=["data"],
        )
        lib.save_node(node, "existing")

        doc = StructuredDocument(
            nodes=[ExtractedNode(
                node_id="n_new", name="获取数据", type="tool",
                description="", inputs=[], outputs=[], config={},
            )],
            edges=[], states=[], raw_text="获取数据",
        )

        generator = ConfigGenerator(component_library=lib)
        config = generator._enhance_with_library(
            generator.generate(doc), llm=None, workflow_name="new_wf"
        )

        # 回退到关键词匹配，也应该能填充
        assert config.nodes[0].description == "从API获取数据"
