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

## Q: 生成的产出物（项目）如何使用？

**问题**: 系统生成的项目包含 PDCA workflow 和 nodes 下的 LangGraph 流程图，这些文件是什么关系？如何使用生成的项目？

**答**:

生成的项目是一个**完整的、可执行的 LangGraph 工作流项目**，包含以下核心组件：

### 生成的项目结构

```
examples/output/iteration_X/
├── main.py                          # 【入口】主程序，可直接运行
├── requirements.txt                 # 项目依赖
├── README.md                        # 项目说明
├── 使用指南.md                      # 详细使用文档
│
├── config/                          # 配置文件
│   ├── workflow.json               # 【配置】工作流元数据
│   └── workflow_metadata.json      # 元数据（生成时间、版本等）
│
├── nodes/                          # 【核心】LangGraph 工作流实现
│   ├── __init__.py
│   └── workflow_graph.py           # LangGraph StateGraph 定义
│
├── pdca/                           # 【框架】PDCA 框架代码
│   └── do_/
│       └── workflow_runner.py      # 工作流执行器
│
└── tests/                          # 测试文件
    ├── __init__.py
    └── test_workflow.py            # 自动生成的测试用例
```

### 两个核心组件的关系

| 组件 | 文件位置 | 作用 | 关系 |
|------|---------|------|------|
| **PDCA Workflow** | `pdca/` 目录下的框架代码 | 整个系统的**生成流程**（Plan→Do→Check→Act） | 是**元系统**，负责生成工作流 |
| **LangGraph 流程图** | `nodes/workflow_graph.py` | 用户想要的**具体业务工作流** | 是**生成物**，被 PDCA 系统创建 |

```
┌─────────────────────────────────────────┐
│         PDCA 框架（元系统）               │
│  ├─ Plan:  理解用户需求                  │
│  ├─ Do:    生成工作流代码                │
│  ├─ Check: 生成并运行测试                │
│  └─ Act:   复盘优化                      │
└────────────────┬────────────────────────┘
                 │ 生成
                 ▼
┌─────────────────────────────────────────┐
│      LangGraph 工作流（生成物）            │
│  - nodes/workflow_graph.py              │
│  - 定义具体的业务流程节点和边             │
│  - 可直接运行执行业务任务                 │
└─────────────────────────────────────────┘
```

### 如何使用生成的项目

#### 1️⃣ 运行工作流（最简单）

```bash
# 进入生成的项目目录
cd examples/output/iteration_2

# 安装依赖
pip install -r requirements.txt

# 直接运行
python main.py
```

**执行流程**：
1. `main.py` 导入 `nodes/workflow_graph.py` 中的 LangGraph 图
2. 初始化工作流状态
3. 按照定义的边关系执行各个节点
4. 输出最终结果

#### 2️⃣ 运行测试

```bash
# 运行自动生成的测试用例
pytest tests/

# 查看覆盖率
pytest --cov=nodes --cov-report=term-missing
```

#### 3️⃣ 查看和使用 LangGraph 流程图

`nodes/workflow_graph.py` 包含：

```python
# 1. 定义状态（TypedDict）
class WorkflowState(TypedDict):
    raw_sales_data: dict
    cleaned_data: dict
    # ... 其他状态字段

# 2. 定义节点函数
def node_fetch_sales_data(state: WorkflowState) -> dict:
    # 节点逻辑
    return {"raw_sales_data": {...}}

# 3. 构建状态图
graph = StateGraph(WorkflowState)
graph.add_node("FetchSalesData", node_fetch_sales_data)
# ... 添加其他节点

# 4. 添加边关系
graph.add_edge("Start", "FetchSalesData")
graph.add_conditional_edges("FetchSalesData", route_function)
# ... 添加其他边

# 5. 编译并执行
app = graph.compile()
result = app.invoke(initial_state)
```

#### 4️⃣ 自定义修改

**修改节点逻辑**：
```python
# 编辑 nodes/workflow_graph.py
def node_fetch_sales_data(state: WorkflowState) -> dict:
    # 修改这里的逻辑
    return {"raw_sales_data": your_custom_data}
```

**修改工作流结构**：
```python
# 在图中添加新节点
graph.add_node("MyNewNode", my_new_function)
graph.add_edge("ExistingNode", "MyNewNode")
```

### 完整使用示例

```bash
# 1. 生成新项目（从用户描述）
python run.py --input "我要创建一个数据分析工作流..."

# 2. 进入生成的项目
cd examples/output/iteration_3

# 3. 查看使用指南
cat 使用指南.md

# 4. 运行工作流
python main.py --input data.json --output result.json

# 5. 运行测试
pytest tests/ -v

# 6. 查看评估报告
cat evaluation_report.json
```

### 常见使用场景

| 场景 | 操作 |
|------|------|
| **快速验证想法** | 直接运行 `python main.py` |
| **调试节点逻辑** | 在 `workflow_graph.py` 中添加断点，使用 `--verbose` 模式 |
| **集成到现有系统** | 导入 `create_workflow_graph()` 函数，获取编译后的 app |
| **持续优化** | 查看 `evaluation_report.json` 和 `review_result.json`，运行下一轮 PDCA |

---

## 生成物的生命周期

```
用户输入
    ↓
【Plan 阶段】理解需求 → 生成配置
    ↓
【Do 阶段】生成代码 → 创建项目
    ↓
【Check 阶段】生成测试 → 评估质量
    ↓
【Act 阶段】复盘优化 → 生成改进方案
    ↓
  (回到 Plan，持续迭代)
```

---

*最后更新：2026-04-23*
