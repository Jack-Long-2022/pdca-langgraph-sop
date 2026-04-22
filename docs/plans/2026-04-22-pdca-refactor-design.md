# PDCA-LangGraph-SOP 重构设计文档

> 日期: 2026-04-22
> 状态: 已确认
> 原则: Karpathy Guidelines — Simplicity First, Surgical Changes, Goal-Driven Execution

## 概述

对 PDCA-LangGraph-SOP 项目进行 6 方面优化：
1. LLM 调用合并（15+ → 5 次）
2. MiniMax 模型扩展 + 双模型分工
3. 系统提示词集中管理
4. 记忆机制简化
5. Karpathy 风格代码优化
6. 数据模型统一

## 1. LLM 调用合并

### 现状问题

当前 15+ 个 LLM 调用点分散在 10+ 个类中，Plan 阶段单独调 3 次（Node/Edge/State），ConfigGenerator 调 3 次（优化→细化→生成），这些调用处理的是同一段输入文本。

### 合并方案

| 合并后调用 | 包含的原调用点 | 阶段 |
|---|---|---|
| **Call 1: 结构化抽取** | NodeExtractor + EdgeExtractor + StateExtractor + ClarificationEngine | Plan |
| **Call 2: 配置优化+生成** | ConfigGenerator 的优化+细化+配置生成 (3步→1步) | Plan |
| **Call 3: 代码批量生成** | LLMCodeGenerator (N次→1次) + WorkflowBuilder | Do |
| **Call 4: 测试生成** | CriteriaGenerator + TestCaseGenerator | Check |
| **Call 5: 评估报告** | EvaluationReportGenerator（保留，依赖运行结果） | Check |
| **Call 6: 复盘+优化** | GRRAVPReviewer + OptimizationGenerator | Act |

### 去掉的 LLM 调用

- `LLMLoopDecider.should_continue()` → 改为简单阈值规则判断
- `LLMEnhancedMemory.extract_and_store_experience()` → PDCAMemory 已在做同样的事
- `LLMEnhancedMemory.generate_context_prompt()` → 模板拼接即可

### Call 1 合并后的 Prompt 示例

```python
SYSTEM_PROMPTS["extract"] = "你是工作流架构师。从用户描述中提取结构化工作流定义。输出严格的JSON。"

USER_PROMPT_TEMPLATE = """
从以下描述中提取完整的工作流定义：

{text}

请以JSON格式输出：
{{
    "nodes": [
        {{
            "name": "节点名称",
            "type": "tool|thought|control",
            "description": "节点功能描述",
            "inputs": ["参数列表"],
            "outputs": ["输出列表"]
        }}
    ],
    "edges": [
        {{
            "source": "源节点名称",
            "target": "目标节点名称",
            "type": "sequential|conditional|parallel",
            "condition": "条件表达式（可选）"
        }}
    ],
    "states": [
        {{
            "field_name": "字段名称",
            "type": "string|integer|boolean|array|object",
            "default_value": null,
            "description": "字段描述",
            "required": true|false
        }}
    ],
    "missing_info": ["缺失的信息"]
}}
"""
```

## 2. MiniMax 模型扩展 + 双模型分工

### 架构

```
┌─────────────────────────────────────────┐
│              LLMManager                 │
│                                         │
│  ┌───────────┐    ┌───────────┐        │
│  │ planner   │    │ executor  │        │
│  │ (GLM-4.7) │    │ (MiniMax) │        │
│  └───────────┘    └───────────┘        │
│                                         │
│  get_llm_for_task(task) → 按角色选择    │
└─────────────────────────────────────────┘
```

### 分工表

| 角色 | 模型 | 负责的调用 | 原因 |
|---|---|---|---|
| Planner | GLM-4.7 | 结构化抽取、配置优化、复盘分析 | 需要深度推理 |
| Executor | MiniMax | 代码生成、测试生成、评估报告 | 模板化任务，成本更低 |

### 实现变更

**core/llm.py**:
```python
# setup_llm 新增 minimax provider
elif provider == "minimax":
    llm = OpenAILLM(
        model=model,
        api_key=api_key or os.getenv("MINIMAX_API_KEY"),
        base_url=base_url or os.getenv("MINIMAX_BASE_URL"),
        **kwargs,
    )

# 角色路由函数
PLANNER_TASKS = {"extract", "config", "review"}

def get_llm_for_task(task: str) -> BaseLLM:
    role = "planner" if task in PLANNER_TASKS else "executor"
    return get_llm_manager().get_llm(role)
```

**setup 注册**:
```python
setup_llm("planner", provider="zhipu", model="glm-4.7")
setup_llm("executor", provider="minimax", model="MiniMax-Text-01")
```

### 环境变量

```env
# .env 新增
MINIMAX_API_KEY=your_key
MINIMAX_BASE_URL=https://api.minimax.chat/v1
```

## 3. 系统提示词集中管理

### 设计

创建 `core/prompts.py`，集中管理所有系统提示词。

```python
# core/prompts.py

SYSTEM_PROMPTS = {
    "extract": "你是工作流架构师。从用户描述中提取结构化工作流定义。输出严格的JSON，不要有其他内容。",
    "config":  "你是配置工程师。将结构化数据转为完整的LangGraph工作流配置。输出严格的JSON。",
    "code":    "你是Python代码专家。为LangGraph工作流生成可执行代码。只输出Python代码，不要解释。",
    "test":    "你是测试工程师。为工作流生成验收标准和测试用例。输出严格的JSON。",
    "report":  "你是质量分析师。分析测试结果，输出评估报告。输出严格的JSON。",
    "review":  "你是PDCA复盘专家。按GRRAVP方法（目标回顾、结果分析、行动规划、验证规划）进行复盘。输出严格的JSON。",
}

# 用户提示词模板（直接字符串，不用模板引擎）
EXTRACT_PROMPT = """
从以下描述中提取完整的工作流定义：
{text}
...
"""

CONFIG_PROMPT = """
将以下结构化数据转为完整的LangGraph工作流配置：
...
"""
```

### 调用方式变更

```python
# 之前：只有 user message
response = llm.generate(prompt)

# 之后：system + user
messages = [
    {"role": "system", "content": SYSTEM_PROMPTS["extract"]},
    {"role": "user", "content": EXTRACT_PROMPT.format(text=text)},
]
response = llm.generate_messages(messages)
```

## 4. 记忆机制简化

### 删除项

| 类/方法 | 原因 |
|---|---|
| `LLMEnhancedMemory` 整个类 (~130行) | 与 PDCAMemory 功能重复，双重提取 |
| `PDCAMemory._create_memory_page()` | Wiki 页面从未被读取 |
| `PDCAMemory.get_wiki_page()` | 同上 |
| `PDCAMemory.export_all_wiki()` | 同上 |

### 保留项

| 类/方法 | 说明 |
|---|---|
| `PDCAMemory` 类 | 简化后保留 |
| `MemoryEntry` | 统一为 Pydantic BaseModel |
| `MemoryContext` | 保留 |
| `WorkflowMemory` | 保留 |
| `record_iteration_experience()` | 保留，去掉 Wiki 页面写入 |
| `get_context_for_next_iteration()` | 保留，简化提示文本生成 |
| `search_memories()` | 保留，标注 TODO: 向量搜索 |
| `prune_old_memories()` | 保留 |

### 数据模型统一

```python
# 之前: dataclass
@dataclass
class MemoryEntry:
    ...

# 之后: Pydantic
class MemoryEntry(BaseModel):
    memory_id: str
    category: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: str = ""
    iteration: int = 0
    workflow_name: str = ""
    impact: str = "medium"
    usage_count: int = 0
    last_used: str = ""
```

## 5. Karpathy 风格代码优化

### A. 去掉不必要的抽象

| 当前 | 问题 | 操作 |
|---|---|---|
| `BaseLLM` ABC | 只有 `OpenAILLM` 一个实现 | 删掉 ABC，直接用 `OpenAILLM` |
| `PromptTemplates` 类 | 纯静态方法，不需实例化 | 改为 `prompts.py` 模块级常量 |
| 每个 Extractor 的 `_fallback_extract()` | 复杂但极少触发 | 简化为一层 try/except + 空结果 |

### B. 消除代码重复

提取公共工具函数到 `core/utils.py`：

```python
def parse_json_response(response: str) -> dict | None:
    """从LLM响应中提取JSON"""
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            return None
    return None
```

### C. 简化 plan/extractor.py

当前：`NodeExtractor` + `EdgeExtractor` + `StateExtractor` + `StructuredExtractor` + `ClarificationEngine` + `JSONLoader` = ~850 行

合并后：

```python
def extract_structure(text: str, llm: BaseLLM) -> StructuredDocument:
    """一次LLM调用完成全部抽取"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["extract"]},
        {"role": "user", "content": EXTRACT_PROMPT.format(text=text)},
    ]
    response = llm.generate_messages(messages)
    data = parse_json_response(response)
    if not data:
        return _fallback_extract(text)
    return _build_document(text, data)
```

预计 ~200 行。

### D. 简化 plan/config_generator.py

当前 `generate_with_refinement()` 三步 LLM 调用合并为一步：

```python
def generate_config(document: StructuredDocument, llm: BaseLLM) -> WorkflowConfig:
    """基础转换 + LLM优化，一次调用"""
    base_config = _basic_convert(document)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["config"]},
        {"role": "user", "content": CONFIG_PROMPT.format(
            nodes=base_config.nodes,
            edges=base_config.edges,
            states=base_config.state
        )},
    ]
    response = llm.generate_messages(messages)
    data = parse_json_response(response)
    if data:
        base_config = _merge_llm_config(base_config, data)

    return base_config
```

## 6. 改动范围汇总

### 文件级变更

| 文件 | 动作 | 行数变化 |
|---|---|---|
| `core/llm.py` | 加 minimax provider + 角色路由 | +30 |
| `core/prompts.py` | **新建**: 集中提示词 | +100 |
| `core/utils.py` | **新建**: 公共工具函数 | +30 |
| `core/memory.py` | 删 LLMEnhancedMemory + 简化 | -150 |
| `core/config.py` | 无变更 | 0 |
| `plan/extractor.py` | 合并 3 个 Extractor | -400 |
| `plan/config_generator.py` | 合并 3 步为 1 步 | -200 |
| `do_/code_generator.py` | 合并代码生成 | -80 |
| `check/evaluator.py` | 合并测试生成 | -60 |
| `act/reviewer.py` | 合并复盘+优化 | -40 |
| `act/loop_controller.py` | 去掉 LLM 判断，改规则 | -30 |
| `run_pdca.py` | 适配新接口 | ~50 |
| `run_pdca_with_memory.py` | 适配新接口 | ~30 |
| `tests/` | 重写测试 | ~200 |

**净效果**: 约减少 550-700 行代码，同时增加模型扩展、提示词管理、双模型路由能力。

### 实施顺序

1. **Phase 1**: `core/utils.py` + `core/prompts.py` — 公共基础设施
2. **Phase 2**: `core/llm.py` — MiniMax + 角色路由
3. **Phase 3**: `plan/extractor.py` + `plan/config_generator.py` — 合并 Plan 阶段
4. **Phase 4**: `do_/code_generator.py` — 合并 Do 阶段
5. **Phase 5**: `check/evaluator.py` — 合并 Check 阶段
6. **Phase 6**: `act/reviewer.py` + `act/loop_controller.py` — 合并 Act 阶段
7. **Phase 7**: `core/memory.py` — 简化记忆系统
8. **Phase 8**: 集成测试 + `run_pdca.py` 适配

### 验证标准

每个 Phase 完成后：
- 现有测试通过（或重写后通过）
- LLM 调用次数减少且合并正确
- 输出质量不低于重构前（人工抽检）
