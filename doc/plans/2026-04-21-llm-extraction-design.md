# LLM 结构化提取改造设计

> 日期: 2026-04-21
> 状态: 已确认

## 背景

当前 `extractor.py` 使用硬编码关键词+正则匹配做结构化抽取，无法处理复杂/模糊的自然语言输入。`prompt-to-langgraph` 技能文件包含了完整的 LLM prompt 模板，但尚未与 Python 代码集成。

## 方案选择

| 方案 | 描述 | 评估 |
|------|------|------|
| **A (选定)** | 技能直接调用 + 输出写入文件 | 最简改动，Dev-time 优先 |
| B | SKILL.md 内容转 LangGraph Subgraph | 架构统一但改动大 |
| C | Claude CLI 命令桥接 | 脆弱不推荐 |

## 数据流

```
用户文本 → /prompt-to-langgraph → JSON文件(analysis+config)
                                        ↓
                  JSONLoader.load() → StructuredDocument → ConfigGenerator → WorkflowConfig
```

## 映射规则

### node_type 映射

```python
TYPE_MAP = {
    "tool_node":     "tool",
    "thinking_node": "thought",
    "control_node":  "control",
}
```

### SKILL JSON → StructuredDocument

- `config.nodes[].node_id` → `ExtractedNode.node_id`
- `config.nodes[].node_name` → `ExtractedNode.name`
- `config.nodes[].node_type` → `ExtractedNode.type` (经 TYPE_MAP 映射)
- `config.nodes[].description` → `ExtractedNode.description`
- `config.nodes[].input_schema.fields[].name` → `ExtractedNode.inputs`
- `config.nodes[].output_schema.fields[].name` → `ExtractedNode.outputs`
- `config.nodes[]` 其余字段 → `ExtractedNode.config`
- `config.edges[].source/target/edge_type` → `ExtractedEdge.source/target/type`
- `config.state_schema.fields[]` → `ExtractedState`
- `analysis.ambiguities` → `StructuredDocument.missing_info`
- `metadata.source_input` → `StructuredDocument.raw_text`

## 改动文件

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `.claude/skills/prompt-to-langgraph/SKILL.md` | 增强 | 末尾追加输出文件指令 |
| `pdca/plan/extractor.py` | 新增类+改造 | 新增 JSONLoader，StructuredExtractor 增加 json_path |
| `config/extractions/` | 新建目录 | 存放技能输出的 JSON 文件 |

## Fallback 策略

- 有 json_path 且文件存在 → JSONLoader 加载
- 无 json_path 或文件不存在 → 原有正则抽取
