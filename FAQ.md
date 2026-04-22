# FAQ - 常见问题

本文档记录项目使用过程中的常见问题及解答。

---

## Q: `config\extractions\wf_data_analysis.json` 是怎么生成的？

**问题**: 请解释一下 `config\extractions\wf_data_analysis.json` 这个文件是如何生成的。是用户使用外部的大模型生成好了放在这里的，还是有步骤可以把用户的语言直接转成这种形式？

**答**:

该文件有**两种生成途径**：

### 方式 A：外部技能生成（开发时/手动）

```
用户描述 → /prompt-to-langgraph 技能 → JSON 文件
```

当你（或用户）使用 Claude Code 并调用 `prompt-to-langgraph` 技能时：

1. **输入**：用户用自然语言描述工作流（如："我想创建一个自动化的数据分析工作流..."）
2. **技能处理**：`prompt-to-langgraph` 技能使用其内置的详细 prompt 模板进行分析
3. **输出**：生成包含 `analysis` 和 `config` 两部分的 JSON 文件
4. **保存**：自动保存到 `config/extractions/{workflow_id}.json`

### 方式 B：内部 LLM 生成（运行时/自动）

```python
# pdca/plan/extractor.py
StructuredExtractor(llm=your_llm).extract(text)
```

当没有提供 `json_path` 或文件不存在时：
1. **输入**：用户描述文本
2. **LLM 调用**：使用 `EXTRACT_PROMPT` 进行结构化抽取
3. **Fallback**：LLM 失败时使用正则表达式回退方案

---

## 完整的数据流管道

```
┌─────────────────┐
│  用户输入文本    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  prompt-to-langgraph 技能            │
│  (或 StructuredExtractor)            │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  JSON 文件                           │
│  config/extractions/wf_*.json       │
│  {                                   │
│    "analysis": {...},  # 分析过程    │
│    "config": {...}    # 工作流配置   │
│  }                                   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  JSONLoader.load()                  │
│  ↓                                   │
│  StructuredDocument                 │
│  - nodes: ExtractedNode[]           │
│  - edges: ExtractedEdge[]           │
│  - states: ExtractedState[]         │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  ConfigGenerator.generate()         │
│  ↓                                   │
│  WorkflowConfig                     │
│  - meta: WorkflowMeta               │
│  - nodes: NodeDefinition[]          │
│  - edges: EdgeDefinition[]          │
│  - state: StateDefinition[]         │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  CodeGenerator.generate_project()   │
│  ↓                                   │
│  可执行的 Python 项目               │
│  - main.py                           │
│  - nodes/                            │
│  - config/                           │
│  - tests/                            │
└─────────────────────────────────────┘
```

---

## 代码实现位置

| 组件 | 文件路径 | 作用 |
|------|---------|------|
| **技能定义** | `.claude/skills/prompt-to-langgraph/SKILL.md` | 定义 prompt 模板和输出规范 |
| **JSON 加载器** | `pdca/plan/extractor.py:JSONLoader` | 读取技能生成的 JSON 文件 |
| **结构化抽取器** | `pdca/plan/extractor.py:StructuredExtractor` | 支持从 JSON 或 LLM 生成 |
| **配置生成器** | `pdca/plan/config_generator.py:ConfigGenerator` | 转换为 WorkflowConfig |
| **代码生成器** | `pdca/do_/code_generator.py:CodeGenerator` | 生成 Python 项目 |

---

## 关键代码片段

```python
# pdca/plan/extractor.py 第 272-277 行
def extract(self, text: str) -> StructuredDocument:
    # Dev-time: 从JSON文件加载
    if self.json_path and self.json_path.exists():
        logger.info("structured_extraction_from_json", path=str(self.json_path))
        return JSONLoader().load(self.json_path)

    # Runtime: 使用LLM抽取
    # ...
```

---

## 实际使用示例

```bash
# 1. 使用技能生成 JSON（手动）
# 在 Claude Code 中执行：
/prompt-to-langgraph 把用户描述转成工作流...

# 2. 使用 Python 加载并生成代码（自动）
python examples/demo_load_and_generate.py

# 3. 运行生成的项目
python examples/demo_run_workflow.py
```

---

## 设计哲学

这个架构巧妙地将**"理解用户意图"**（交给专用的 prompt-to-langgraph 技能）和**"生成可执行代码"**（交给 Python 后端）分离，使得每个阶段都能使用最适合的工具和技术。

**双模混合架构**：开发时使用外部技能生成高质量配置，运行时使用内部 LLM 处理用户输入。这种设计既保证了配置质量，又提供了自动化能力。

---

*最后更新：2026-04-23*
