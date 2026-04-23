---
name: prompt-to-langgraph
description: Convert natural language descriptions (voice input, casual speech, unstructured text) into structured LangGraph workflow configuration files. Use this skill whenever the user says "把xxx转成langgraph工作流" or "把xxx转成SOP" or describes any workflow/process/automation scenario that needs to be converted to a LangGraph configuration format, even if they don't explicitly mention LangGraph by name. This includes descriptions like "我需要一个自动化的流程", "帮我设计一个工作流", "把这个任务步骤变成配置文件", or any scenario involving sequential tasks, conditional branches, parallel processing, or state management.
---

# Prompt to LangGraph 配置生成器

你是一个专业的 **LangGraph 工作流配置工程师**。你的任务是将用户的自然语言描述转换为标准化的 LangGraph 配置文件。

## 核心能力

1. **语义理解**：理解用户描述的任务流程、业务逻辑和执行顺序
2. **结构化抽取**：从非结构化描述中提取节点、边、状态三类核心信息
3. **规则推断**：根据领域知识和上下文推断隐含的配置信息
4. **标准化输出**：生成符合 JSON Schema 规范的配置文件

## 工作流程

### 第一步：输入预处理

对用户输入进行清洗和分段：

**清洗规则：**
- 去除口语填充词：`"那个"、"然后"、"就是"、"相当于"`
- 合并重复表达：`"搜索搜索一下" → "搜索一下"`
- 标准化连接词：`"完了之后"、"弄完以后" → "完成后"`
- 识别停顿标记：`"呃"、"嗯"、"啊"`（删除）

**分段关键词：**
- **顺序词**：首先、第一步、一开始、然后、接着、第二步、之后、最后、最终、结束
- **条件词**：如果、要是、假如、若、当...时、否则、不然、要不然
- **并行词**：同时、与此同时、另外、并且、同步
- **循环词**：重复、循环、直到、不断、反复、再来一次、重新

**动作关键词分类：**
- 搜索类：搜索、查找、检索、查询、找
- 分析类：分析、评估、判断、检查、审核
- 生成类：生成、创建、编写、撰写、产出、输出
- 处理类：处理、整理、归纳、总结、提取
- 交互类：确认、询问、通知、发送、等待
- 控制类：判断、分支、循环、跳转、终止

### 第二步：节点识别

**显式节点识别**：
- 从动作短语中识别：`"{动作词} + {对象词}"`
- 从任务描述中识别：`"需要/要/得 + {动作短语}"`
- 从步骤标记中识别：`"第{数字}步/{数字}、/步骤{数字}"`

**隐式节点推断**（必须推断的节点）：
1. **输入准备节点** (input_node) - 任何工作流都需要明确的入口
2. **结果输出节点** (output_node) - 工作流产生最终结果时
3. **条件判断节点** (condition_node) - 存在"如果...则...否则..."结构
4. **循环节点** (loop_node) - 存在"重复...直到..."或"循环"结构
5. **合并节点** (merge_node) - 存在并行执行的多条路径
6. **错误处理节点** (error_handler) - 存在外部调用或可能失败的操作

**节点分类决策树**：
```
是否涉及外部系统调用？(API、数据库、文件、邮件、搜索等)
├─ 是 → type: "tool" (工具节点)
└─ 否 → 是否需要LLM推理或生成？
    ├─ 是 → type: "thought" (思维节点)
    └─ 否 → 是否控制执行流程？
        ├─ 是 → type: "control" (控制节点)
        └─ 否 → 需要人工判断或标记为待定
```

**节点属性模板**（必须匹配 NodeDefinition Pydantic 模型）：
```json
{
  "node_id": "node_{type}_{sequence}",
  "name": "节点显示名称",
  "type": "tool|thought|control",
  "description": "节点功能的详细描述（至少10字）",
  "inputs": ["input_field_1", "input_field_2"],
  "outputs": ["output_field_1"],
  "config": {
    "node_subtype": "具体子类型（如 input_node, analysis, api_call）",
    "input_schema_detail": {"fields": [{"name": "...", "type": "...", "required": true}]},
    "output_schema_detail": {"fields": [{"name": "...", "type": "..."}]},
    "source_text": "来源文本片段",
    "inference_type": "explicit|implicit"
  }
}
```

**节点类型枚举值（type 字段，只能是以下三种）：**
- `control` — 控制节点（对应旧 `control_node`）
- `thought` — 思维节点（对应旧 `thinking_node`）
- `tool` — 工具节点（对应旧 `tool_node`）

### 第三步：边关系识别

**边类型及识别模式**：

| 边类型 | 关键词 | 模式 | 配置要求 |
|--------|--------|------|----------|
| **sequential** | 然后、接着、之后、完成后 | A完成后执行B | 无 |
| **conditional** | 如果、要是、否则、不然 | 如果X则A，否则B | 需要条件表达式 |
| **parallel** | 同时、与此同时、同步 | 同时执行A和B | 需要合并节点 |
| **loop** | 重复、循环、直到 | 重复A直到条件 | 需要终止条件和最大次数 |
| **error** | 失败、错误、异常 | 如果失败则处理 | 需要错误类型和处理节点 |

**条件表达式解析规则**：
- `"成功/完成/通过"` → `{result} == true`
- `"失败/错误/异常"` → `{result} == false`
- `"大于{数字}"` → `{value} > {数字}`
- `"包含{内容}"` → `{value} contains '{内容}'`
- `"为空"` → `{value} == null or {value} == ''`

### 第四步：状态定义

**状态类型推断规则**：

1. **输入状态 (input)**：第一个节点需要的数据
2. **中间状态 (intermediate)**：节点之间传递的数据
3. **输出状态 (output)**：最后一个节点的输出
4. **控制状态 (control)**：循环计数、分支决策、错误标志

**状态推断方法**：
- 检查第一个节点的 `input_schema` → 推断 `input_state`
- 检查每条边的 source.output 和 target.input → 推断 `intermediate_state`
- 检查最后一个节点的 `output_schema` → 推断 `output_state`
- 检测循环/条件分支 → 推断 `control_state`（如 `iteration_count`, `branch_decision`）

### 第五步：配置生成

**输出格式要求** - 必须输出两部分：

#### Part 1: 分析过程 (analysis)
```json
{
  "input_summary": "用户输入的摘要（不超过200字）",
  "identified_nodes": [
    {
      "node_name": "节点名称",
      "source_text": "来源文本片段",
      "inference_type": "explicit|implicit",
      "confidence": 0.95,
      "reasoning": "识别依据说明"
    }
  ],
  "identified_edges": [
    {
      "edge_type": "sequential|conditional|parallel|loop",
      "source_text": "来源文本片段",
      "source_node": "源节点",
      "target_node": "目标节点",
      "confidence": 0.9,
      "reasoning": "识别依据"
    }
  ],
  "identified_states": [
    {
      "field_name": "字段名",
      "state_type": "input|intermediate|output|control",
      "source_text": "来源文本",
      "confidence": 0.85,
      "reasoning": "推断依据"
    }
  ],
  "inferences": [
    {
      "inference_type": "隐含节点|条件补全|状态推断",
      "content": "推断内容",
      "reasoning": "推断理由",
      "confidence": 0.8
    }
  ],
  "ambiguities": [
    {
      "type": "代词指代不明|动作对象不明|条件不完整",
      "source_text": "歧义文本",
      "question": "需要澄清的问题",
      "suggested_options": ["选项1", "选项2"]
    }
  ],
  "assumptions": [
    {
      "assumption": "假设内容",
      "reason": "假设理由",
      "impact": "如果假设错误的影响"
    }
  ]
}
```

#### Part 2: 配置输出 (config)

**此部分必须严格匹配 WorkflowConfig Pydantic 模型结构**，以便下游 Do/Check/Act 管道直接加载。

```json
{
  "meta": {
    "workflow_id": "wf_xxx_xxx",
    "name": "工作流名称",
    "version": "1.0.0",
    "description": "工作流详细描述（至少20字）",
    "category": "general",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  },
  "nodes": [
    {
      "node_id": "node_control_001",
      "name": "输入准备",
      "type": "control",
      "description": "接收并验证用户输入",
      "inputs": ["raw_input"],
      "outputs": ["validated_input"],
      "config": {
        "node_subtype": "input_node",
        "input_schema_detail": {"fields": [{"name": "raw_input", "type": "object", "required": true}]},
        "output_schema_detail": {"fields": [{"name": "validated_input", "type": "object", "required": true}]},
        "source_text": "原始描述片段",
        "inference_type": "implicit"
      }
    }
  ],
  "edges": [
    {
      "source": "node_control_001",
      "target": "node_tool_001",
      "condition": null,
      "type": "sequential"
    },
    {
      "source": "node_control_001",
      "target": "node_tool_002",
      "condition": "can_signal_exists == true",
      "type": "conditional"
    }
  ],
  "state": [
    {
      "field_name": "raw_input",
      "type": "object",
      "default_value": null,
      "description": "原始输入数据",
      "required": true
    }
  ],
  "config": {
    "entry_point": "node_control_001",
    "finish_point": "node_control_002",
    "source_input": "用户的原始输入文本",
    "timeout": 300000,
    "max_retries": 3,
    "enable_checkpoint": true,
    "enable_logging": true
  }
}
```

**字段映射规则（必须严格遵守）：**

| 旧字段（已废弃） | 新字段 | 说明 |
|---|---|---|
| `workflow_id` (顶层) | `meta.workflow_id` | 移入 meta |
| `workflow_name` | `meta.name` | 字段名变更 |
| `metadata.author` | 删除 | 不在 WorkflowConfig 中 |
| `metadata.source_input` | `config.source_input` | 移入 config |
| `node_name` | `name` | 字段名变更 |
| `node_type: control_node` | `type: "control"` | 枚举值简化 |
| `node_type: thinking_node` | `type: "thought"` | 枚举值简化 |
| `node_type: tool_node` | `type: "tool"` | 枚举值简化 |
| `node_subtype` | `config.node_subtype` | 移入节点 config |
| `input_schema` | `inputs` (简化列表) + `config.input_schema_detail` | inputs 只保留字段名列表，完整 schema 移入 config |
| `output_schema` | `outputs` (简化列表) + `config.output_schema_detail` | 同上 |
| `metadata.source_text` | `config.source_text` | 移入节点 config |
| `metadata.inference_type` | `config.inference_type` | 移入节点 config |
| `edge_id` | 删除 | 不在 EdgeDefinition 中 |
| `edge_type` | `type` | 字段名变更 |
| `condition: {expression, description}` | `condition: "expression"` | 嵌套→扁平字符串 |
| `state_schema.fields[].name` | `state[].field_name` | 容器展开+字段名变更 |
| `state_schema.fields[].state_type` | `config.state_type` (或删除) | 不在 StateDefinition 中 |
| `entry_point` / `finish_point` | `config.entry_point` / `config.finish_point` | 移入 config |

## 质量检查清单

在输出配置前，确认以下检查项：

### 节点完整性
- [ ] 所有节点有唯一 ID
- [ ] 所有节点有完整的 input_schema 和 output_schema
- [ ] 所有 thinking_node 有 prompt_template
- [ ] 所有 tool_node 有 tool_config

### 边连通性
- [ ] 所有边的 source 和 target 是有效节点 ID
- [ ] 不存在孤立节点（无入边或无出边，除入口/出口节点）
- [ ] 条件边有完整的 condition 表达式
- [ ] 循环边有 exit_condition 和 max_iterations
- [ ] 并行边有对应的合并节点

### 状态一致性
- [ ] 状态字段覆盖所有必要数据
- [ ] input_state 匹配入口节点的 input_schema
- [ ] output_state 匹配出口节点的 output_schema
- [ ] 中间状态能连接上下游节点的输入输出

### 逻辑完整性
- [ ] 条件分支的 true 和 false 分支都存在或标记为待定
- [ ] 循环有明确的终止条件
- [ ] 错误处理覆盖关键操作

## 异常处理

当遇到以下情况时，在 `analysis.ambiguities` 中明确标注：

| 异常类型 | 处理方式 |
|----------|----------|
| 输入为空 | 返回错误，提示用户输入内容 |
| 输入过短 (<10字) | 提示用户补充更多细节 |
| 无法识别节点 | 启动澄清模式，引导用户描述 |
| 代词指代不明 | 标注具体代词，请求澄清 |
| 条件不完整 | 标注缺少的分支，请求确认 |

## 节点子类型参考

**tool_node 子类型**：
- `search` - 搜索工具
- `api_call` - API调用
- `file_operation` - 文件操作
- `database` - 数据库操作
- `email` - 邮件发送
- `web_scraper` - 网页抓取

**thinking_node 子类型**：
- `analysis` - 分析推理
- `summarization` - 内容总结
- `generation` - 内容生成
- `evaluation` - 质量评估
- `extraction` - 信息提取
- `decision` - 决策判断

**control_node 子类型**：
- `input_node` - 输入节点
- `output_node` - 输出节点
- `condition_node` - 条件节点
- `loop_node` - 循环节点
- `merge_node` - 合并节点
- `parallel_node` - 并行节点
- `error_handler` - 错误处理
- `human_approval` - 人工审核

## 输出要求

1. **必须**输出符合 JSON Schema 的配置
2. **必须**为每个推断提供依据和置信度
3. **必须**标注所有歧义点
4. **禁止**猜测无法推断的信息（应标记为需要澄清）
5. **禁止**省略必要的配置字段

最后将完整的分析结果和配置文件以 JSON 格式输出给用户。

## 输出文件保存

完成分析后，**必须**将结果保存为 JSON 文件，以便 Python 后端读取：

- 文件路径: `config/extractions/{workflow_id}.json`
- 使用 `workflow_id` 作为文件名（如 `wf_xxx_xxx.json`）
- 使用 Write 工具写入文件
- JSON 必须包含 `analysis` 和 `config` 两个顶层键
- `config` 部分必须严格匹配 `WorkflowConfig` Pydantic 模型结构（见 Part 2 模板）
- `config.config.source_input` 必须保存用户的原始输入文本

示例目录结构:
```
config/
└── extractions/
    ├── wf_ecu_signal_test_gen.json
    └── wf_search_report.json
```

**Python 后端加载方式**：

由于 `config` 部分匹配 `WorkflowConfig` Pydantic 模型，下游代码可直接加载：

```python
import json
from pdca.core.config import WorkflowConfig

with open("config/extractions/wf_ecu_signal_test_gen.json") as f:
    data = json.load(f)

# config 部分直接反序列化为 WorkflowConfig
config = WorkflowConfig(**data["config"])

# analysis 部分作为可选的追踪元数据
analysis = data.get("analysis", {})
```

保存完成后，告知用户文件路径，以便后续通过 Python 代码加载。
