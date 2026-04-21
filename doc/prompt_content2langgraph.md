# LangGraph SOP 配置生成提示词机制

> **版本**: V1.0  
> **用途**: Plan阶段 - 将不规范的语音输入转换为标准化的LangGraph配置文件  
> **输出格式**: 结构化JSON（可直接被代码解析和使用）

---

## 目录

1. [核心设计理念](#1-核心设计理念)
2. [系统提示词模板](#2-系统提示词模板)
3. [输入分析规则](#3-输入分析规则)
4. [节点识别与分类规则](#4-节点识别与分类规则)
5. [边关系识别规则](#5-边关系识别规则)
6. [状态定义规则](#6-状态定义规则)
7. [配置输出规范](#7-配置输出规范)
8. [完整示例演示](#8-完整示例演示)
9. [异常处理机制](#9-异常处理机制)
10. [质量检查清单](#10-质量检查清单)

---

## 1. 核心设计理念

### 1.1 转换目标

将用户的**自然语言描述**（口语化、碎片化、非结构化）转换为**机器可执行的配置文件**（标准化、结构化、可验证）。

```
┌─────────────────────────────────────────────────────────────────┐
│                        转换流程                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   用户语音输入              AI分析处理              结构化输出   │
│   ┌──────────┐            ┌──────────┐           ┌──────────┐  │
│   │ 口语化   │    ───▶    │ 规则引擎 │    ───▶   │ JSON配置 │  │
│   │ 碎片化   │            │ 推理推断 │           │ 可验证   │  │
│   │ 非结构化 │            │ 补全修正 │           │ 可执行   │  │
│   └──────────┘            └──────────┘           └──────────┘  │
│                                                                 │
│   "先搜索一下，然后           识别节点类型          {           │
│    整理成报告，如果           推断边关系            "nodes": [ │
│    不行就重新搜"             定义状态字段            ...       │
│                                                    ],          │
│                                                    "edges": [  │
│                                                      ...       │
│                                                    ]           │
│                                                  }             │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 设计原则

| 原则 | 说明 | 实现方式 |
|------|------|----------|
| **容错性** | 接受不完整、不规范的输入 | 多轮澄清机制 + 默认值填充 |
| **可推断性** | 从上下文推断隐含信息 | 语义分析 + 领域知识库 |
| **可验证性** | 输出必须符合Schema约束 | JSON Schema验证 |
| **可追溯性** | 每个推断都有依据说明 | 推理链记录 |
| **可修正性** | 支持用户干预和修正 | 交互式确认机制 |

---

## 2. 系统提示词模板

### 2.1 主提示词（System Prompt）

```markdown
# 角色定义

你是一个专业的 **LangGraph 工作流配置工程师**。你的任务是将用户的自然语言描述转换为标准化的 LangGraph 配置文件。

## 核心能力

1. **语义理解**：理解用户描述的任务流程、业务逻辑和执行顺序
2. **结构化抽取**：从非结构化描述中提取节点、边、状态三类核心信息
3. **规则推断**：根据领域知识和上下文推断隐含的配置信息
4. **标准化输出**：生成符合 JSON Schema 规范的配置文件

## 工作流程

### 第一步：输入预处理
- 清洗文本：去除口语化表达、重复内容、无关信息
- 分段识别：按任务/步骤/阶段对内容进行分段
- 关键词标注：标注动作词、条件词、实体词

### 第二步：节点识别
- 识别所有任务节点（用户明确提到的动作）
- 推断隐含节点（上下文暗示但未明说的步骤）
- 分类节点类型（工具节点/思维节点/控制节点）
- 定义节点属性（名称、描述、输入输出）

### 第三步：边关系识别
- 识别顺序关系（A完成后执行B）
- 识别条件关系（如果X则A，否则B）
- 识别并行关系（同时执行A和B）
- 识别循环关系（重复执行直到满足条件）

### 第四步：状态定义
- 识别输入状态（工作流启动时需要的数据）
- 识别中间状态（节点之间传递的数据）
- 识别输出状态（工作流结束时产生的数据）
- 定义状态字段类型和约束

### 第五步：配置生成
- 组装完整的配置JSON
- 填充必要的默认值
- 生成配置说明文档

### 第六步：质量检查
- 检查节点完整性（是否有孤立节点）
- 检查边连通性（是否所有节点可达）
- 检查状态一致性（输入输出是否匹配）
- 检查逻辑完整性（条件分支是否完整）

## 输出要求

你必须输出以下两部分内容：

### Part 1: 分析过程（analysis）
```json
{
  "input_summary": "用户输入的摘要",
  "identified_nodes": ["识别出的节点列表及依据"],
  "identified_edges": ["识别出的边关系及依据"],
  "identified_states": ["识别出的状态字段及依据"],
  "inferences": ["做出的推断及理由"],
  "ambiguities": ["发现的歧义点，需要澄清"],
  "assumptions": ["做出的假设及理由"]
}
```

### Part 2: 配置输出（config）
```json
{
  "workflow_id": "唯一标识",
  "workflow_name": "工作流名称",
  "description": "工作流描述",
  "version": "1.0.0",
  "nodes": [...],
  "edges": [...],
  "state_schema": {...},
  "entry_point": "入口节点ID",
  "finish_point": "结束节点ID或条件"
}
```

## 约束条件

1. **必须**输出符合 JSON Schema 的配置
2. **必须**为每个推断提供依据
3. **必须**标注所有歧义点
4. **禁止**猜测无法推断的信息（应标记为需要澄清）
5. **禁止**省略必要的配置字段
```

### 2.2 用户提示词模板（User Prompt Template）

```markdown
# 用户输入

## 原始输入文本
"""
{user_input_text}
"""

## 补充上下文（如有）
"""
{additional_context}
"""

## 已有澄清信息（如有）
"""
{clarification_info}
"""

---

请根据上述输入，按照系统提示词中定义的工作流程，生成 LangGraph 配置文件。

请特别注意：
1. 如果发现信息不完整或有歧义，请在 analysis.ambiguities 中列出
2. 如果需要做出假设，请在 analysis.assumptions 中说明
3. 输出的配置必须可以直接被代码解析使用
```

---

## 3. 输入分析规则

### 3.1 文本预处理规则

#### 3.1.1 清洗规则

| 规则ID | 规则名称 | 匹配模式 | 处理方式 | 示例 |
|--------|----------|----------|----------|------|
| PRE-001 | 去除口语填充词 | "那个"、"然后"、"就是"、"相当于" | 删除 | "然后那个就是先搜索" → "先搜索" |
| PRE-002 | 合并重复表达 | 连续相同的词或短语 | 合并为一个 | "搜索搜索一下" → "搜索一下" |
| PRE-003 | 标准化连接词 | "完了之后"、"弄完以后"、"搞完" | 统一为"完成后" | "搜索完了之后整理" → "搜索完成后整理" |
| PRE-004 | 识别停顿标记 | "呃"、"嗯"、"啊" | 删除 | "先呃搜索一下" → "先搜索一下" |
| PRE-005 | 保留关键标点 | "。"、"，"、"？" | 保留用于分段 | - |

#### 3.1.2 分段识别规则

```python
# 分段识别算法伪代码
def segment_input(text):
    segments = []
    
    # 规则 SEG-001: 按句号分段
    sentences = split_by_period(text)
    
    for sentence in sentences:
        # 规则 SEG-002: 按顺序词分段
        # 顺序词: 首先、然后、接着、最后、第一步、第二步...
        sub_segments = split_by_sequence_words(sentence)
        
        for seg in sub_segments:
            # 规则 SEG-003: 按条件词分段
            # 条件词: 如果、要是、假如、当...时、否则、不然
            conditional_segments = split_by_conditional_words(seg)
            segments.extend(conditional_segments)
    
    return segments
```

**分段词表**：

| 类型 | 词表 |
|------|------|
| 顺序词 | 首先、第一步、一开始、然后、接着、第二步、之后、最后、最终、结束 |
| 条件词 | 如果、要是、假如、若、当...时、一旦、否则、不然、要不然、如果不行 |
| 并行词 | 同时、与此同时、另外、并且、一边...一边、同步 |
| 循环词 | 重复、循环、直到、不断、反复、再来一次、重新 |

#### 3.1.3 关键词标注规则

```json
{
  "action_keywords": {
    "搜索类": ["搜索", "查找", "检索", "查询", "找", "搜"],
    "分析类": ["分析", "评估", "判断", "检查", "审核", "审查"],
    "生成类": ["生成", "创建", "编写", "撰写", "产出", "输出", "制作"],
    "处理类": ["处理", "整理", "归纳", "总结", "提取", "转换"],
    "交互类": ["确认", "询问", "通知", "发送", "等待", "审批"],
    "控制类": ["判断", "分支", "循环", "跳转", "终止", "暂停"]
  },
  
  "object_keywords": {
    "文档类": ["文档", "报告", "文章", "方案", "总结", "邮件"],
    "数据类": ["数据", "信息", "内容", "结果", "记录"],
    "资源类": ["文件", "图片", "链接", "资源"]
  },
  
  "condition_keywords": {
    "成功条件": ["成功", "完成", "通过", "符合", "满足"],
    "失败条件": ["失败", "错误", "不通过", "不符合", "异常"],
    "数量条件": ["大于", "小于", "等于", "超过", "不足"],
    "状态条件": ["存在", "不存在", "为空", "非空"]
  },
  
  "modifier_keywords": {
    "时间修饰": ["先", "后", "最后", "首先", "立即", "延迟"],
    "频率修饰": ["一次", "多次", "重复", "循环", "定期"],
    "程度修饰": ["完整", "部分", "详细", "简要", "快速"]
  }
}
```

### 3.2 语义理解规则

#### 3.2.1 意图识别规则

| 规则ID | 意图类型 | 匹配模式 | 提取信息 | 示例 |
|--------|----------|----------|----------|------|
| INT-001 | 任务执行 | "动词 + 宾语" | 动作、对象 | "搜索资料" → 动作:搜索, 对象:资料 |
| INT-002 | 条件分支 | "如果...则...否则..." | 条件、真分支、假分支 | "如果找到则整理，否则重搜" |
| INT-003 | 并行执行 | "同时...和..." | 并行动作列表 | "同时搜索和整理" |
| INT-004 | 循环执行 | "重复...直到..." | 循环体、终止条件 | "重复搜索直到找到" |
| INT-005 | 顺序执行 | "先...然后...最后..." | 顺序动作列表 | "先搜索，然后整理，最后输出" |
| INT-006 | 异常处理 | "如果失败/出错...则..." | 异常条件、处理动作 | "如果失败则通知管理员" |

#### 3.2.2 隐含信息推断规则

| 规则ID | 推断类型 | 触发条件 | 推断结果 | 置信度 |
|--------|----------|----------|----------|--------|
| INF-001 | 输入推断 | 提到"搜索"动作 | 需要搜索关键词作为输入 | 高 |
| INF-002 | 输出推断 | 提到"生成报告" | 产出报告文档 | 高 |
| INF-003 | 条件补全 | "如果成功则继续" | 隐含"否则停止或重试" | 中 |
| INF-004 | 顺序补全 | "搜索后整理" | 搜索结果作为整理的输入 | 高 |
| INF-005 | 并行合并 | "同时A和B" | 需要合并A和B的结果 | 中 |
| INF-006 | 循环上限 | "重复直到成功" | 需要设置最大重试次数 | 中 |
| INF-007 | 错误处理 | 任何外部调用 | 需要错误处理机制 | 高 |

#### 3.2.3 歧义检测规则

| 规则ID | 歧义类型 | 检测模式 | 澄清问题模板 |
|--------|----------|----------|--------------|
| AMB-001 | 代词指代不明 | "它"、"这个"、"那个" | "您提到的'{代词}'具体指什么？" |
| AMB-002 | 动作对象不明 | 动词后无明确宾语 | "您要'{动作}'的对象是什么？" |
| AMB-003 | 条件不完整 | "如果X"后无"否则" | "如果'{条件}'不满足，应该怎么处理？" |
| AMB-004 | 顺序不明确 | 多个动作无明确顺序词 | "这些步骤的执行顺序是什么？" |
| AMB-005 | 数据来源不明 | 提到数据但无来源 | "'{数据}'从哪里获取？" |
| AMB-006 | 输出格式不明 | 提到输出但无格式 | "输出结果需要什么格式？" |

---

## 4. 节点识别与分类规则

### 4.1 节点识别规则

#### 4.1.1 显式节点识别

**规则定义**：

```yaml
# 显式节点识别规则
explicit_node_rules:
  
  # 规则 NODE-EXP-001: 动作短语识别
  - rule_id: NODE-EXP-001
    rule_name: 动作短语识别
    pattern: "{动作词} + {对象词}?"
    extraction:
      node_name: "{对象词}_{动作词}" 或 "{动作词}"
      node_type: 根据动作词分类
    examples:
      - input: "搜索相关资料"
        output:
          node_name: "资料搜索"
          node_type: "tool_node"
          action: "search"
      
      - input: "整理成报告"
        output:
          node_name: "报告整理"
          node_type: "thinking_node"
          action: "organize"
      
      - input: "发送邮件通知"
        output:
          node_name: "邮件发送"
          node_type: "tool_node"
          action: "send_email"
  
  # 规则 NODE-EXP-002: 任务描述识别
  - rule_id: NODE-EXP-002
    rule_name: 任务描述识别
    pattern: "需要/要/得 + {动作短语}"
    extraction:
      node_name: "{动作短语}"
      node_type: 根据动作性质分类
    examples:
      - input: "需要分析一下数据"
        output:
          node_name: "数据分析"
          node_type: "thinking_node"
  
  # 规则 NODE-EXP-003: 步骤标记识别
  - rule_id: NODE-EXP-003
    rule_name: 步骤标记识别
    pattern: "第{数字}步/{数字}、/步骤{数字}"
    extraction:
      node_name: 该步骤后的动作描述
      node_order: 数字顺序
    examples:
      - input: "第一步，搜索资料"
        output:
          node_name: "资料搜索"
          node_order: 1
```

#### 4.1.2 隐式节点推断

**规则定义**：

```yaml
# 隐式节点推断规则
implicit_node_rules:
  
  # 规则 NODE-IMP-001: 输入准备节点
  - rule_id: NODE-IMP-001
    rule_name: 输入准备节点推断
    trigger: 工作流需要外部输入数据
    inference:
      node_name: "输入准备"
      node_type: "control_node"
      node_subtype: "input_node"
      description: "准备和验证工作流所需的输入数据"
    confidence: 高
    
  # 规则 NODE-IMP-002: 结果输出节点
  - rule_id: NODE-IMP-002
    rule_name: 结果输出节点推断
    trigger: 工作流产生最终结果
    inference:
      node_name: "结果输出"
      node_type: "control_node"
      node_subtype: "output_node"
      description: "格式化并输出最终结果"
    confidence: 高
    
  # 规则 NODE-IMP-003: 错误处理节点
  - rule_id: NODE-IMP-003
    rule_name: 错误处理节点推断
    trigger: 存在外部调用或可能失败的操作
    inference:
      node_name: "错误处理"
      node_type: "control_node"
      node_subtype: "error_handler"
      description: "处理执行过程中的异常情况"
    confidence: 中
    
  # 规则 NODE-IMP-004: 条件判断节点
  - rule_id: NODE-IMP-004
    rule_name: 条件判断节点推断
    trigger: 存在"如果...则...否则..."结构
    inference:
      node_name: "条件判断"
      node_type: "control_node"
      node_subtype: "condition_node"
      description: "根据条件决定执行路径"
    confidence: 高
    
  # 规则 NODE-IMP-005: 循环控制节点
  - rule_id: NODE-IMP-005
    rule_name: 循环控制节点推断
    trigger: 存在"重复...直到..."或"循环"结构
    inference:
      node_name: "循环控制"
      node_type: "control_node"
      node_subtype: "loop_node"
      description: "控制循环的执行和终止"
    confidence: 高
    
  # 规则 NODE-IMP-006: 并行合并节点
  - rule_id: NODE-IMP-006
    rule_name: 并行合并节点推断
    trigger: 存在并行执行的多条路径
    inference:
      node_name: "结果合并"
      node_type: "control_node"
      node_subtype: "merge_node"
      description: "合并多个并行分支的结果"
    confidence: 高
    
  # 规则 NODE-IMP-007: 人工审核节点
  - rule_id: NODE-IMP-007
    rule_name: 人工审核节点推断
    trigger: 提到"审核"、"审批"、"确认"、"人工"等词
    inference:
      node_name: "人工审核"
      node_type: "control_node"
      node_subtype: "human_approval"
      description: "等待人工审核确认"
    confidence: 高
    
  # 规则 NODE-IMP-008: 数据转换节点
  - rule_id: NODE-IMP-008
    rule_name: 数据转换节点推断
    trigger: 前后节点的输入输出格式不匹配
    inference:
      node_name: "数据转换"
      node_type: "tool_node"
      node_subtype: "transformer"
      description: "转换数据格式以适配下游节点"
    confidence: 中
```

### 4.2 节点分类规则

#### 4.2.1 节点类型定义

```json
{
  "node_types": {
    "tool_node": {
      "description": "工具节点 - 执行具体的外部操作",
      "subtypes": {
        "search": {
          "name": "搜索工具",
          "description": "执行搜索查询操作",
          "input_fields": ["query", "options"],
          "output_fields": ["results", "metadata"],
          "config_fields": ["search_engine", "max_results"]
        },
        "api_call": {
          "name": "API调用工具",
          "description": "调用外部API接口",
          "input_fields": ["endpoint", "params", "headers"],
          "output_fields": ["response", "status"],
          "config_fields": ["base_url", "timeout", "retry_count"]
        },
        "file_operation": {
          "name": "文件操作工具",
          "description": "读写文件操作",
          "input_fields": ["file_path", "content", "mode"],
          "output_fields": ["result", "file_info"],
          "config_fields": ["base_dir", "allowed_extensions"]
        },
        "database": {
          "name": "数据库工具",
          "description": "数据库查询和操作",
          "input_fields": ["query", "params"],
          "output_fields": ["rows", "affected_count"],
          "config_fields": ["connection_string", "timeout"]
        },
        "email": {
          "name": "邮件工具",
          "description": "发送邮件通知",
          "input_fields": ["to", "subject", "body", "attachments"],
          "output_fields": ["message_id", "status"],
          "config_fields": ["smtp_server", "from_address"]
        },
        "web_scraper": {
          "name": "网页抓取工具",
          "description": "抓取网页内容",
          "input_fields": ["url", "selectors"],
          "output_fields": ["content", "links"],
          "config_fields": ["user_agent", "timeout"]
        }
      }
    },
    
    "thinking_node": {
      "description": "思维节点 - 使用LLM进行推理和生成",
      "subtypes": {
        "analysis": {
          "name": "分析推理",
          "description": "分析数据并得出结论",
          "input_fields": ["data", "context", "criteria"],
          "output_fields": ["analysis_result", "insights"],
          "prompt_template": "分析以下数据：{data}\n分析维度：{criteria}\n请给出分析结论。"
        },
        "summarization": {
          "name": "内容总结",
          "description": "总结和提炼内容要点",
          "input_fields": ["content", "max_length", "focus_areas"],
          "output_fields": ["summary", "key_points"],
          "prompt_template": "请总结以下内容，不超过{max_length}字：\n{content}"
        },
        "generation": {
          "name": "内容生成",
          "description": "生成新的内容",
          "input_fields": ["topic", "requirements", "context"],
          "output_fields": ["generated_content", "metadata"],
          "prompt_template": "请根据以下要求生成内容：\n主题：{topic}\n要求：{requirements}"
        },
        "evaluation": {
          "name": "质量评估",
          "description": "评估内容质量",
          "input_fields": ["content", "criteria", "reference"],
          "output_fields": ["score", "feedback", "suggestions"],
          "prompt_template": "请评估以下内容的质量：\n{content}\n评估标准：{criteria}"
        },
        "extraction": {
          "name": "信息提取",
          "description": "从内容中提取结构化信息",
          "input_fields": ["content", "schema", "instructions"],
          "output_fields": ["extracted_data", "confidence"],
          "prompt_template": "从以下内容中提取信息：\n{content}\n提取格式：{schema}"
        },
        "decision": {
          "name": "决策判断",
          "description": "基于条件做出决策",
          "input_fields": ["situation", "options", "criteria"],
          "output_fields": ["decision", "reasoning", "confidence"],
          "prompt_template": "根据以下情况做出决策：\n情况：{situation}\n选项：{options}\n标准：{criteria}"
        }
      }
    },
    
    "control_node": {
      "description": "控制节点 - 控制工作流执行流程",
      "subtypes": {
        "input_node": {
          "name": "输入节点",
          "description": "工作流入口，准备输入数据",
          "input_fields": ["raw_input"],
          "output_fields": ["validated_input"]
        },
        "output_node": {
          "name": "输出节点",
          "description": "工作流出口，格式化输出",
          "input_fields": ["result_data"],
          "output_fields": ["formatted_output"]
        },
        "condition_node": {
          "name": "条件节点",
          "description": "根据条件选择执行路径",
          "input_fields": ["condition_data"],
          "output_fields": ["branch_decision"]
        },
        "loop_node": {
          "name": "循环节点",
          "description": "控制循环执行",
          "input_fields": ["loop_body_result"],
          "output_fields": ["continue_loop", "iteration_count"]
        },
        "merge_node": {
          "name": "合并节点",
          "description": "合并多个分支的结果",
          "input_fields": ["branch_results"],
          "output_fields": ["merged_result"]
        },
        "parallel_node": {
          "name": "并行节点",
          "description": "并行执行多个分支",
          "input_fields": ["parallel_input"],
          "output_fields": ["parallel_results"]
        },
        "error_handler": {
          "name": "错误处理节点",
          "description": "处理异常情况",
          "input_fields": ["error_info", "context"],
          "output_fields": ["recovery_action", "should_retry"]
        },
        "human_approval": {
          "name": "人工审核节点",
          "description": "等待人工确认",
          "input_fields": ["approval_request"],
          "output_fields": ["approval_result", "comments"]
        }
      }
    }
  }
}
```

#### 4.2.2 节点分类决策树

```
输入: 动作描述
    │
    ▼
┌─────────────────────────────────────┐
│ 是否涉及外部系统调用？              │
│ (API、数据库、文件、邮件、搜索等)   │
└─────────────────────────────────────┘
    │                    │
   是                   否
    │                    │
    ▼                    ▼
┌──────────────┐  ┌─────────────────────────────────┐
│ tool_node    │  │ 是否需要LLM推理或生成？          │
│ 工具节点     │  │ (分析、总结、生成、评估等)       │
└──────────────┘  └─────────────────────────────────┘
                        │                    │
                       是                   否
                        │                    │
                        ▼                    ▼
                 ┌──────────────┐  ┌─────────────────────────────────┐
                 │ thinking_node│  │ 是否控制执行流程？               │
                 │ 思维节点     │  │ (条件、循环、并行、合并等)       │
                 └──────────────┘  └─────────────────────────────────┘
                                          │                    │
                                         是                   否
                                          │                    │
                                          ▼                    ▼
                                   ┌──────────────┐  ┌──────────────┐
                                   │ control_node │  │ 需要人工判断  │
                                   │ 控制节点     │  │ 或标记为待定  │
                                   └──────────────┘  └──────────────┘
```

### 4.3 节点属性定义规则

```json
{
  "node_attribute_schema": {
    "node_id": {
      "type": "string",
      "required": true,
      "description": "节点唯一标识，格式: node_{type}_{sequence}",
      "example": "node_tool_001, node_thinking_002, node_control_003"
    },
    "node_name": {
      "type": "string",
      "required": true,
      "description": "节点显示名称，简洁描述节点功能",
      "example": "资料搜索, 内容分析, 条件判断"
    },
    "node_type": {
      "type": "string",
      "required": true,
      "enum": ["tool_node", "thinking_node", "control_node"],
      "description": "节点类型"
    },
    "node_subtype": {
      "type": "string",
      "required": false,
      "description": "节点子类型，对应具体功能",
      "example": "search, analysis, condition_node"
    },
    "description": {
      "type": "string",
      "required": true,
      "description": "节点功能的详细描述",
      "min_length": 10,
      "example": "根据关键词搜索相关资料，返回搜索结果列表"
    },
    "input_schema": {
      "type": "object",
      "required": true,
      "description": "输入数据结构定义",
      "properties": {
        "fields": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": {"type": "string"},
              "type": {"type": "string", "enum": ["string", "number", "boolean", "array", "object"]},
              "required": {"type": "boolean"},
              "description": {"type": "string"},
              "default": {"type": ["string", "number", "boolean", "array", "object", "null"]}
            }
          }
        }
      }
    },
    "output_schema": {
      "type": "object",
      "required": true,
      "description": "输出数据结构定义",
      "properties": {
        "fields": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": {"type": "string"},
              "type": {"type": "string", "enum": ["string", "number", "boolean", "array", "object"]},
              "description": {"type": "string"}
            }
          }
        }
      }
    },
    "config": {
      "type": "object",
      "required": false,
      "description": "节点配置参数",
      "example": {
        "max_results": 10,
        "timeout": 30
      }
    },
    "prompt_template": {
      "type": "string",
      "required": false,
      "description": "思维节点的提示词模板（仅thinking_node需要）"
    },
    "tool_config": {
      "type": "object",
      "required": false,
      "description": "工具节点的配置（仅tool_node需要）",
      "properties": {
        "tool_name": {"type": "string"},
        "tool_version": {"type": "string"},
        "parameters": {"type": "object"}
      }
    },
    "retry_policy": {
      "type": "object",
      "required": false,
      "description": "重试策略",
      "properties": {
        "max_retries": {"type": "integer", "default": 3},
        "retry_delay": {"type": "integer", "default": 1000},
        "backoff_multiplier": {"type": "number", "default": 2}
      }
    },
    "timeout": {
      "type": "integer",
      "required": false,
      "description": "超时时间（毫秒）",
      "default": 30000
    },
    "metadata": {
      "type": "object",
      "required": false,
      "description": "元数据信息",
      "properties": {
        "source_text": {"type": "string", "description": "来源文本片段"},
        "confidence": {"type": "number", "description": "识别置信度 0-1"},
        "inference_type": {"type": "string", "enum": ["explicit", "implicit"], "description": "识别类型"}
      }
    }
  }
}
```

---

## 5. 边关系识别规则

### 5.1 边类型定义

```json
{
  "edge_types": {
    "sequential": {
      "name": "顺序边",
      "description": "从源节点顺序执行到目标节点",
      "pattern": "A完成后执行B",
      "keywords": ["然后", "接着", "之后", "再", "完成后"],
      "config": {
        "condition": null
      }
    },
    
    "conditional": {
      "name": "条件边",
      "description": "根据条件选择执行路径",
      "pattern": "如果条件则A，否则B",
      "keywords": ["如果", "要是", "假如", "否则", "不然"],
      "config": {
        "condition": "条件表达式",
        "true_target": "条件为真时的目标节点",
        "false_target": "条件为假时的目标节点"
      }
    },
    
    "parallel": {
      "name": "并行边",
      "description": "同时执行多个目标节点",
      "pattern": "同时执行A和B",
      "keywords": ["同时", "与此同时", "另外", "并且", "同步"],
      "config": {
        "targets": ["并行目标节点列表"]
      }
    },
    
    "loop": {
      "name": "循环边",
      "description": "重复执行直到满足终止条件",
      "pattern": "重复A直到条件",
      "keywords": ["重复", "循环", "直到", "不断", "反复"],
      "config": {
        "loop_body": "循环体节点",
        "exit_condition": "退出条件",
        "max_iterations": "最大迭代次数"
      }
    },
    
    "error": {
      "name": "错误边",
      "description": "发生错误时跳转到错误处理节点",
      "pattern": "如果失败则处理",
      "keywords": ["失败", "错误", "异常", "出错"],
      "config": {
        "error_types": ["错误类型列表"],
        "handler": "错误处理节点"
      }
    }
  }
}
```

### 5.2 边关系识别规则

#### 5.2.1 顺序关系识别

```yaml
# 顺序关系识别规则
sequential_edge_rules:
  
  - rule_id: EDGE-SEQ-001
    rule_name: 顺序词识别
    patterns:
      - "{节点A} 然后 {节点B}"
      - "{节点A} 之后 {节点B}"
      - "{节点A} 接着 {节点B}"
      - "{节点A} 完成(后) {节点B}"
      - "先 {节点A} 再 {节点B}"
    extraction:
      source: 节点A
      target: 节点B
      type: sequential
    examples:
      - input: "搜索资料，然后整理成报告"
        output:
          source: "资料搜索"
          target: "报告整理"
          type: "sequential"
  
  - rule_id: EDGE-SEQ-002
    rule_name: 步骤顺序识别
    patterns:
      - "第一步 {节点A}，第二步 {节点B}"
      - "首先 {节点A}，然后 {节点B}"
      - "1. {节点A} 2. {节点B}"
    extraction:
      source: 前一步节点
      target: 后一步节点
      type: sequential
  
  - rule_id: EDGE-SEQ-003
    rule_name: 隐含顺序推断
    trigger: 两个节点在文本中连续出现，无其他关系词
    inference:
      source: 前一个节点
      target: 后一个节点
      type: sequential
      confidence: 中
    note: 需要结合上下文判断，可能误判
```

#### 5.2.2 条件关系识别

```yaml
# 条件关系识别规则
conditional_edge_rules:
  
  - rule_id: EDGE-COND-001
    rule_name: 标准条件句识别
    patterns:
      - "如果 {条件} 则 {节点A}，否则 {节点B}"
      - "如果 {条件}，{节点A}，不然 {节点B}"
      - "要是 {条件}，就 {节点A}，否则 {节点B}"
    extraction:
      condition_node: 需要插入条件判断节点
      condition: 条件表达式
      true_target: 节点A
      false_target: 节点B
    examples:
      - input: "如果搜索成功则整理，否则重新搜索"
        output:
          condition_node: "搜索结果判断"
          condition: "search_success == true"
          true_target: "报告整理"
          false_target: "资料搜索"
  
  - rule_id: EDGE-COND-002
    rule_name: 简化条件句识别
    patterns:
      - "如果 {条件}，{节点A}"  # 无else分支
      - "{节点A}，如果 {条件}"
    extraction:
      condition_node: 需要插入条件判断节点
      condition: 条件表达式
      true_target: 节点A
      false_target: 需要推断或标记为待定
    inference:
      - 如果上下文暗示失败处理，推断false_target
      - 否则标记为需要澄清
  
  - rule_id: EDGE-COND-003
    rule_name: 多条件分支识别
    patterns:
      - "如果 {条件1} 则 {节点A}，如果 {条件2} 则 {节点B}，否则 {节点C}"
      - "根据 {变量}：是X则 {节点A}，是Y则 {节点B}，其他则 {节点C}"
    extraction:
      type: switch_case
      cases:
        - condition: 条件1
          target: 节点A
        - condition: 条件2
          target: 节点B
        - condition: default
          target: 节点C
  
  - rule_id: EDGE-COND-004
    rule_name: 条件表达式解析
    condition_patterns:
      - "成功/完成/通过": "{result} == true"
      - "失败/错误/异常": "{result} == false"
      - "大于{数字}": "{value} > {数字}"
      - "小于{数字}": "{value} < {数字}"
      - "等于{数字}": "{value} == {数字}"
      - "包含{内容}": "{value} contains '{内容}'"
      - "为空": "{value} == null or {value} == ''"
      - "非空": "{value} != null and {value} != ''"
```

#### 5.2.3 并行关系识别

```yaml
# 并行关系识别规则
parallel_edge_rules:
  
  - rule_id: EDGE-PAR-001
    rule_name: 并行词识别
    patterns:
      - "同时 {节点A} 和 {节点B}"
      - "与此同时，{节点A} 和 {节点B}"
      - "{节点A} 和 {节点B} 同步进行"
      - "一边 {节点A}，一边 {节点B}"
    extraction:
      type: parallel
      source: 前驱节点（如有）
      targets: [节点A, 节点B]
      merge_node: 需要插入合并节点
    examples:
      - input: "同时搜索多个来源，然后合并结果"
        output:
          type: parallel
          targets: ["来源1搜索", "来源2搜索", "来源3搜索"]
          merge_node: "结果合并"
  
  - rule_id: EDGE-PAR-002
    rule_name: 分组并行识别
    patterns:
      - "分别 {动作} {对象列表}"
      - "对每个 {对象} {动作}"
    extraction:
      type: parallel_foreach
      source: 前驱节点
      iteration_target: 动作节点
      merge_node: 需要插入合并节点
    examples:
      - input: "对每个数据源分别进行搜索"
        output:
          type: parallel_foreach
          iteration_target: "数据源搜索"
          merge_node: "搜索结果合并"
```

#### 5.2.4 循环关系识别

```yaml
# 循环关系识别规则
loop_edge_rules:
  
  - rule_id: EDGE-LOOP-001
    rule_name: 标准循环识别
    patterns:
      - "重复 {节点A} 直到 {条件}"
      - "循环 {节点A} 直到 {条件}"
      - "不断 {节点A} 直到 {条件}"
      - "{节点A}，如果不满足 {条件} 就再来一次"
    extraction:
      type: loop
      loop_body: 节点A
      exit_condition: 条件
      max_iterations: 默认值或推断
    examples:
      - input: "重复搜索直到找到满意的结果"
        output:
          type: loop
          loop_body: "资料搜索"
          exit_condition: "result_satisfaction == true"
          max_iterations: 10  # 默认值
  
  - rule_id: EDGE-LOOP-002
    rule_name: 固定次数循环识别
    patterns:
      - "重复 {数字} 次 {节点A}"
      - "{节点A} {数字} 遍"
      - "对每个 {元素} {节点A}"
    extraction:
      type: foreach
      loop_body: 节点A
      iteration_count: 数字 或 列表长度
  
  - rule_id: EDGE-LOOP-003
    rule_name: 重试循环识别
    patterns:
      - "如果失败则重试"
      - "失败后重新 {节点A}"
      - "不行就再来"
    extraction:
      type: retry_loop
      loop_body: 失败的节点
      exit_condition: "success == true"
      max_iterations: 默认3次
```

### 5.3 边属性定义规则

```json
{
  "edge_attribute_schema": {
    "edge_id": {
      "type": "string",
      "required": true,
      "description": "边唯一标识，格式: edge_{source}_{target}_{type}",
      "example": "edge_search_organize_sequential"
    },
    "source": {
      "type": "string",
      "required": true,
      "description": "源节点ID"
    },
    "target": {
      "type": "string",
      "required": true,
      "description": "目标节点ID"
    },
    "edge_type": {
      "type": "string",
      "required": true,
      "enum": ["sequential", "conditional", "parallel", "loop", "error"],
      "description": "边类型"
    },
    "condition": {
      "type": "object",
      "required": false,
      "description": "条件表达式（仅conditional类型需要）",
      "properties": {
        "expression": {"type": "string", "description": "条件表达式"},
        "variables": {"type": "array", "description": "涉及的变量"},
        "operator": {"type": "string", "description": "比较运算符"}
      }
    },
    "priority": {
      "type": "integer",
      "required": false,
      "description": "边的优先级（多条件分支时使用）",
      "default": 0
    },
    "metadata": {
      "type": "object",
      "required": false,
      "description": "元数据信息",
      "properties": {
        "source_text": {"type": "string"},
        "confidence": {"type": "number"},
        "inference_type": {"type": "string", "enum": ["explicit", "implicit"]}
      }
    }
  }
}
```

---

## 6. 状态定义规则

### 6.1 状态类型定义

```json
{
  "state_types": {
    "input_state": {
      "name": "输入状态",
      "description": "工作流启动时需要的外部输入数据",
      "source": "外部调用者提供",
      "required": true,
      "examples": ["query", "user_id", "config"]
    },
    
    "intermediate_state": {
      "name": "中间状态",
      "description": "节点之间传递的数据",
      "source": "上游节点输出",
      "required": false,
      "examples": ["search_results", "analysis_result", "draft_content"]
    },
    
    "output_state": {
      "name": "输出状态",
      "description": "工作流最终产出的结果",
      "source": "最后一个节点输出",
      "required": true,
      "examples": ["final_report", "processed_data", "notification_sent"]
    },
    
    "control_state": {
      "name": "控制状态",
      "description": "控制工作流执行的状态变量",
      "source": "系统自动维护",
      "required": false,
      "examples": ["iteration_count", "error_flag", "approval_status"]
    }
  }
}
```

### 6.2 状态推断规则

```yaml
# 状态推断规则
state_inference_rules:
  
  # 规则 STATE-001: 输入状态推断
  - rule_id: STATE-001
    rule_name: 输入状态推断
    trigger: 第一个节点需要的数据
    inference:
      - 检查第一个节点的input_schema
      - 推断哪些字段需要外部提供
      - 标记为input_state
    examples:
      - first_node: "资料搜索"
        input_schema: {"query": "string", "max_results": "number"}
        inference:
          input_state:
            query: 
              type: "string"
              required: true
              description: "搜索关键词"
            max_results:
              type: "number"
              required: false
              default: 10
              description: "最大结果数"
  
  # 规则 STATE-002: 中间状态推断
  - rule_id: STATE-002
    rule_name: 中间状态推断
    trigger: 节点之间的数据传递
    inference:
      - 检查每条边的source和target节点
      - 匹配source的output_schema和target的input_schema
      - 推断需要传递的字段
    examples:
      - edge: "资料搜索 → 报告整理"
        source_output: {"results": "array", "metadata": "object"}
        target_input: {"content": "string", "source_info": "object"}
        inference:
          intermediate_state:
            search_results:
              type: "array"
              source: "资料搜索.results"
              description: "搜索结果列表"
  
  # 规则 STATE-003: 输出状态推断
  - rule_id: STATE-003
    rule_name: 输出状态推断
    trigger: 最后一个节点的输出
    inference:
      - 检查最后一个节点的output_schema
      - 标记为output_state
    examples:
      - last_node: "报告生成"
        output_schema: {"report": "string", "format": "string"}
        inference:
          output_state:
            final_report:
              type: "string"
              description: "最终生成的报告内容"
            report_format:
              type: "string"
              description: "报告格式"
  
  # 规则 STATE-004: 控制状态推断
  - rule_id: STATE-004
    rule_name: 控制状态推断
    trigger: 存在循环、条件分支等控制结构
    inference:
      - 循环结构 → 推断iteration_count
      - 条件分支 → 推断branch_decision
      - 错误处理 → 推断error_flag
    examples:
      - loop_detected: true
        inference:
          control_state:
            iteration_count:
              type: "number"
              initial_value: 0
              description: "当前迭代次数"
            max_iterations:
              type: "number"
              value: 10
              description: "最大迭代次数"
```

### 6.3 状态字段定义规范

```json
{
  "state_field_schema": {
    "field_name": {
      "type": "string",
      "required": true,
      "description": "字段名称，使用snake_case命名",
      "pattern": "^[a-z][a-z0-9_]*$"
    },
    "field_type": {
      "type": "string",
      "required": true,
      "enum": ["string", "number", "boolean", "array", "object", "any"],
      "description": "字段数据类型"
    },
    "required": {
      "type": "boolean",
      "required": true,
      "description": "是否必填"
    },
    "default": {
      "type": ["string", "number", "boolean", "array", "object", "null"],
      "required": false,
      "description": "默认值"
    },
    "description": {
      "type": "string",
      "required": true,
      "description": "字段描述，至少10个字符"
    },
    "source": {
      "type": "string",
      "required": false,
      "description": "数据来源，格式: {node_id}.{field_name}"
    },
    "validation": {
      "type": "object",
      "required": false,
      "description": "验证规则",
      "properties": {
        "min_length": {"type": "number"},
        "max_length": {"type": "number"},
        "min_value": {"type": "number"},
        "max_value": {"type": "number"},
        "pattern": {"type": "string"},
        "enum": {"type": "array"}
      }
    }
  }
}
```

---

## 7. 配置输出规范

### 7.1 完整配置JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LangGraph Workflow Configuration",
  "description": "LangGraph工作流配置文件Schema",
  "type": "object",
  "required": ["workflow_id", "workflow_name", "version", "nodes", "edges", "state_schema", "entry_point"],
  "properties": {
    "workflow_id": {
      "type": "string",
      "description": "工作流唯一标识",
      "pattern": "^wf_[a-z][a-z0-9_]*$"
    },
    "workflow_name": {
      "type": "string",
      "description": "工作流名称",
      "minLength": 2,
      "maxLength": 100
    },
    "description": {
      "type": "string",
      "description": "工作流详细描述",
      "minLength": 20
    },
    "version": {
      "type": "string",
      "description": "版本号，遵循语义化版本",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "metadata": {
      "type": "object",
      "description": "元数据信息",
      "properties": {
        "author": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "source_input": {"type": "string", "description": "原始输入文本"}
      }
    },
    "nodes": {
      "type": "array",
      "description": "节点列表",
      "minItems": 1,
      "items": {
        "$ref": "#/definitions/Node"
      }
    },
    "edges": {
      "type": "array",
      "description": "边列表",
      "items": {
        "$ref": "#/definitions/Edge"
      }
    },
    "state_schema": {
      "$ref": "#/definitions/StateSchema"
    },
    "entry_point": {
      "type": "string",
      "description": "入口节点ID"
    },
    "finish_point": {
      "type": ["string", "array"],
      "description": "结束节点ID或结束条件"
    },
    "config": {
      "type": "object",
      "description": "全局配置",
      "properties": {
        "timeout": {"type": "integer", "default": 300000},
        "max_retries": {"type": "integer", "default": 3},
        "enable_checkpoint": {"type": "boolean", "default": true},
        "enable_logging": {"type": "boolean", "default": true}
      }
    }
  },
  "definitions": {
    "Node": {
      "type": "object",
      "required": ["node_id", "node_name", "node_type", "description", "input_schema", "output_schema"],
      "properties": {
        "node_id": {"type": "string", "pattern": "^node_[a-z][a-z0-9_]*$"},
        "node_name": {"type": "string", "minLength": 2},
        "node_type": {"type": "string", "enum": ["tool_node", "thinking_node", "control_node"]},
        "node_subtype": {"type": "string"},
        "description": {"type": "string", "minLength": 10},
        "input_schema": {"$ref": "#/definitions/Schema"},
        "output_schema": {"$ref": "#/definitions/Schema"},
        "config": {"type": "object"},
        "prompt_template": {"type": "string"},
        "tool_config": {"type": "object"},
        "retry_policy": {
          "type": "object",
          "properties": {
            "max_retries": {"type": "integer"},
            "retry_delay": {"type": "integer"},
            "backoff_multiplier": {"type": "number"}
          }
        },
        "timeout": {"type": "integer"},
        "metadata": {
          "type": "object",
          "properties": {
            "source_text": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "inference_type": {"type": "string", "enum": ["explicit", "implicit"]}
          }
        }
      }
    },
    "Edge": {
      "type": "object",
      "required": ["edge_id", "source", "target", "edge_type"],
      "properties": {
        "edge_id": {"type": "string"},
        "source": {"type": "string"},
        "target": {"type": "string"},
        "edge_type": {"type": "string", "enum": ["sequential", "conditional", "parallel", "loop", "error"]},
        "condition": {
          "type": "object",
          "properties": {
            "expression": {"type": "string"},
            "variables": {"type": "array", "items": {"type": "string"}},
            "operator": {"type": "string"}
          }
        },
        "priority": {"type": "integer"},
        "metadata": {
          "type": "object",
          "properties": {
            "source_text": {"type": "string"},
            "confidence": {"type": "number"}
          }
        }
      }
    },
    "StateSchema": {
      "type": "object",
      "required": ["fields"],
      "properties": {
        "fields": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name", "type", "required", "description"],
            "properties": {
              "name": {"type": "string"},
              "type": {"type": "string", "enum": ["string", "number", "boolean", "array", "object", "any"]},
              "required": {"type": "boolean"},
              "default": {},
              "description": {"type": "string"},
              "source": {"type": "string"},
              "state_type": {"type": "string", "enum": ["input", "intermediate", "output", "control"]},
              "validation": {"type": "object"}
            }
          }
        }
      }
    },
    "Schema": {
      "type": "object",
      "required": ["fields"],
      "properties": {
        "fields": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name", "type"],
            "properties": {
              "name": {"type": "string"},
              "type": {"type": "string", "enum": ["string", "number", "boolean", "array", "object", "any"]},
              "required": {"type": "boolean"},
              "description": {"type": "string"},
              "default": {}
            }
          }
        }
      }
    }
  }
}
```

### 7.2 输出格式模板

```json
{
  "analysis": {
    "input_summary": "用户输入的摘要，不超过200字",
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
        "source_node": "源节点名称",
        "target_node": "目标节点名称",
        "confidence": 0.9,
        "reasoning": "识别依据说明"
      }
    ],
    "identified_states": [
      {
        "field_name": "字段名称",
        "state_type": "input|intermediate|output|control",
        "source_text": "来源文本片段",
        "confidence": 0.85,
        "reasoning": "推断依据说明"
      }
    ],
    "inferences": [
      {
        "inference_type": "隐含节点|条件补全|状态推断|默认值填充",
        "content": "推断内容",
        "reasoning": "推断理由",
        "confidence": 0.8
      }
    ],
    "ambiguities": [
      {
        "type": "代词指代不明|动作对象不明|条件不完整|顺序不明确|数据来源不明|输出格式不明",
        "source_text": "歧义文本片段",
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
  },
  
  "config": {
    "workflow_id": "wf_xxx_xxx",
    "workflow_name": "工作流名称",
    "description": "工作流详细描述",
    "version": "1.0.0",
    "metadata": {
      "author": "AI Assistant",
      "created_at": "2024-01-01T00:00:00Z",
      "source_input": "原始输入文本"
    },
    "nodes": [
      {
        "node_id": "node_control_001",
        "node_name": "输入准备",
        "node_type": "control_node",
        "node_subtype": "input_node",
        "description": "准备和验证工作流所需的输入数据",
        "input_schema": {
          "fields": [
            {"name": "raw_input", "type": "object", "required": true, "description": "原始输入数据"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "validated_input", "type": "object", "required": true, "description": "验证后的输入数据"}
          ]
        },
        "metadata": {
          "inference_type": "implicit",
          "confidence": 0.9
        }
      }
    ],
    "edges": [
      {
        "edge_id": "edge_input_xxx_sequential",
        "source": "node_control_001",
        "target": "node_tool_001",
        "edge_type": "sequential",
        "metadata": {
          "inference_type": "implicit",
          "confidence": 0.95
        }
      }
    ],
    "state_schema": {
      "fields": [
        {
          "name": "query",
          "type": "string",
          "required": true,
          "description": "搜索关键词",
          "state_type": "input"
        }
      ]
    },
    "entry_point": "node_control_001",
    "finish_point": "node_control_002",
    "config": {
      "timeout": 300000,
      "max_retries": 3,
      "enable_checkpoint": true,
      "enable_logging": true
    }
  }
}
```

---

## 8. 完整示例演示

### 8.1 示例输入

```
用户语音输入（转录文本）：

"那个，我想做一个自动写报告的流程。首先呢，用户输入一个主题，
然后系统去搜索相关的资料，搜索的时候要从多个来源搜，比如网页、
数据库、文档库这些。搜完之后呢，把结果整理一下，去重、排序、
筛选出最相关的。然后让AI分析这些资料，提取关键信息，生成一个
报告大纲。大纲生成之后，如果用户觉得不满意，可以让AI重新生成，
最多重试3次。大纲确定后，再根据大纲写完整的报告内容。写完之后
要做质量检查，检查报告是否完整、是否有逻辑问题。如果检查通过
就输出最终报告，如果没通过就返回修改，最多修改2次。最后把报告
保存成文件，同时发送邮件通知用户。"
```

### 8.2 分析过程输出

```json
{
  "analysis": {
    "input_summary": "用户需要一个自动报告生成工作流，包含多源搜索、资料整理、大纲生成（支持重试）、内容撰写、质量检查（支持修改）、结果输出和通知等环节。",
    
    "identified_nodes": [
      {
        "node_name": "主题输入",
        "source_text": "用户输入一个主题",
        "inference_type": "explicit",
        "confidence": 0.95,
        "reasoning": "明确提到用户输入主题，是工作流的起点"
      },
      {
        "node_name": "多源搜索",
        "source_text": "搜索的时候要从多个来源搜，比如网页、数据库、文档库",
        "inference_type": "explicit",
        "confidence": 0.95,
        "reasoning": "明确提到多来源并行搜索"
      },
      {
        "node_name": "结果整理",
        "source_text": "把结果整理一下，去重、排序、筛选出最相关的",
        "inference_type": "explicit",
        "confidence": 0.95,
        "reasoning": "明确描述了整理操作的具体内容"
      },
      {
        "node_name": "大纲生成",
        "source_text": "让AI分析这些资料，提取关键信息，生成一个报告大纲",
        "inference_type": "explicit",
        "confidence": 0.95,
        "reasoning": "明确提到AI生成大纲"
      },
      {
        "node_name": "大纲审核",
        "source_text": "如果用户觉得不满意，可以让AI重新生成",
        "inference_type": "implicit",
        "confidence": 0.85,
        "reasoning": "需要用户审核大纲，隐含人工审核节点"
      },
      {
        "node_name": "内容撰写",
        "source_text": "根据大纲写完整的报告内容",
        "inference_type": "explicit",
        "confidence": 0.95,
        "reasoning": "明确提到撰写报告内容"
      },
      {
        "node_name": "质量检查",
        "source_text": "做质量检查，检查报告是否完整、是否有逻辑问题",
        "inference_type": "explicit",
        "confidence": 0.95,
        "reasoning": "明确提到质量检查"
      },
      {
        "node_name": "报告输出",
        "source_text": "把报告保存成文件",
        "inference_type": "explicit",
        "confidence": 0.95,
        "reasoning": "明确提到保存文件"
      },
      {
        "node_name": "邮件通知",
        "source_text": "发送邮件通知用户",
        "inference_type": "explicit",
        "confidence": 0.95,
        "reasoning": "明确提到发送邮件"
      }
    ],
    
    "identified_edges": [
      {
        "edge_type": "sequential",
        "source_text": "首先呢，用户输入一个主题，然后系统去搜索",
        "source_node": "主题输入",
        "target_node": "多源搜索",
        "confidence": 0.95,
        "reasoning": "明确的顺序关系"
      },
      {
        "edge_type": "parallel",
        "source_text": "从多个来源搜，比如网页、数据库、文档库",
        "source_node": "多源搜索",
        "target_node": ["网页搜索", "数据库搜索", "文档库搜索"],
        "confidence": 0.9,
        "reasoning": "明确提到多个来源同时搜索"
      },
      {
        "edge_type": "sequential",
        "source_text": "搜完之后呢，把结果整理一下",
        "source_node": "多源搜索",
        "target_node": "结果整理",
        "confidence": 0.95,
        "reasoning": "明确的顺序关系"
      },
      {
        "edge_type": "sequential",
        "source_text": "然后让AI分析这些资料",
        "source_node": "结果整理",
        "target_node": "大纲生成",
        "confidence": 0.95,
        "reasoning": "明确的顺序关系"
      },
      {
        "edge_type": "conditional",
        "source_text": "如果用户觉得不满意，可以让AI重新生成，最多重试3次",
        "source_node": "大纲审核",
        "target_node": "大纲生成",
        "condition": "用户不满意 AND 重试次数 < 3",
        "confidence": 0.9,
        "reasoning": "明确的条件循环关系"
      },
      {
        "edge_type": "sequential",
        "source_text": "大纲确定后，再根据大纲写完整的报告内容",
        "source_node": "大纲审核",
        "target_node": "内容撰写",
        "condition": "大纲通过",
        "confidence": 0.95,
        "reasoning": "明确的条件顺序关系"
      },
      {
        "edge_type": "conditional",
        "source_text": "如果检查通过就输出最终报告，如果没通过就返回修改，最多修改2次",
        "source_node": "质量检查",
        "target_node": "内容撰写",
        "condition": "检查不通过 AND 修改次数 < 2",
        "confidence": 0.9,
        "reasoning": "明确的条件循环关系"
      },
      {
        "edge_type": "sequential",
        "source_text": "检查通过就输出最终报告",
        "source_node": "质量检查",
        "target_node": "报告输出",
        "condition": "检查通过",
        "confidence": 0.95,
        "reasoning": "明确的条件顺序关系"
      },
      {
        "edge_type": "parallel",
        "source_text": "把报告保存成文件，同时发送邮件通知用户",
        "source_node": "报告输出",
        "target_node": ["文件保存", "邮件发送"],
        "confidence": 0.95,
        "reasoning": "明确提到'同时'"
      }
    ],
    
    "identified_states": [
      {
        "field_name": "topic",
        "state_type": "input",
        "source_text": "用户输入一个主题",
        "confidence": 0.95,
        "reasoning": "工作流的起始输入"
      },
      {
        "field_name": "search_results",
        "state_type": "intermediate",
        "source_text": "搜索相关资料",
        "confidence": 0.9,
        "reasoning": "搜索节点的输出，整理节点的输入"
      },
      {
        "field_name": "outline",
        "state_type": "intermediate",
        "source_text": "生成一个报告大纲",
        "confidence": 0.9,
        "reasoning": "大纲生成节点的输出"
      },
      {
        "field_name": "outline_retry_count",
        "state_type": "control",
        "source_text": "最多重试3次",
        "confidence": 0.95,
        "reasoning": "控制大纲重试循环"
      },
      {
        "field_name": "report_content",
        "state_type": "intermediate",
        "source_text": "写完整的报告内容",
        "confidence": 0.9,
        "reasoning": "内容撰写节点的输出"
      },
      {
        "field_name": "quality_check_result",
        "state_type": "intermediate",
        "source_text": "质量检查",
        "confidence": 0.9,
        "reasoning": "质量检查节点的输出"
      },
      {
        "field_name": "revision_count",
        "state_type": "control",
        "source_text": "最多修改2次",
        "confidence": 0.95,
        "reasoning": "控制报告修改循环"
      },
      {
        "field_name": "final_report",
        "state_type": "output",
        "source_text": "最终报告",
        "confidence": 0.95,
        "reasoning": "工作流的最终输出"
      }
    ],
    
    "inferences": [
      {
        "inference_type": "隐含节点",
        "content": "需要添加'输入准备'节点作为工作流入口",
        "reasoning": "标准工作流需要明确的入口节点",
        "confidence": 0.9
      },
      {
        "inference_type": "隐含节点",
        "content": "需要添加'结果合并'节点合并多源搜索结果",
        "reasoning": "并行搜索后需要合并结果",
        "confidence": 0.9
      },
      {
        "inference_type": "隐含节点",
        "content": "需要添加'人工审核'节点让用户审核大纲",
        "reasoning": "提到'用户觉得不满意'，需要人工确认",
        "confidence": 0.85
      },
      {
        "inference_type": "默认值填充",
        "content": "搜索结果数量默认为10条",
        "reasoning": "用户未指定，使用合理默认值",
        "confidence": 0.7
      },
      {
        "inference_type": "默认值填充",
        "content": "报告格式默认为Markdown",
        "reasoning": "用户未指定格式，Markdown是常用格式",
        "confidence": 0.7
      }
    ],
    
    "ambiguities": [
      {
        "type": "数据来源不明",
        "source_text": "数据库、文档库",
        "question": "数据库和文档库的具体连接信息是什么？",
        "suggested_options": ["使用预设配置", "运行时动态传入", "跳过这些来源"]
      },
      {
        "type": "输出格式不明",
        "source_text": "保存成文件",
        "question": "报告文件需要保存为什么格式？",
        "suggested_options": ["Markdown (.md)", "Word (.docx)", "PDF (.pdf)", "纯文本 (.txt)"]
      },
      {
        "type": "动作对象不明",
        "source_text": "发送邮件通知用户",
        "question": "邮件接收者的邮箱地址从哪里获取？",
        "suggested_options": ["从输入参数获取", "使用当前登录用户邮箱", "从配置文件读取"]
      }
    ],
    
    "assumptions": [
      {
        "assumption": "用户有权限访问网页、数据库、文档库",
        "reason": "用户提到这些来源，假设已有访问权限",
        "impact": "如果权限不足，搜索节点会失败"
      },
      {
        "assumption": "质量检查使用AI进行自动检查",
        "reason": "用户提到'检查报告是否完整、是否有逻辑问题'，适合用AI检查",
        "impact": "如果需要人工检查，需要添加人工审核节点"
      }
    ]
  }
}
```

### 8.3 配置输出

```json
{
  "config": {
    "workflow_id": "wf_auto_report_generation",
    "workflow_name": "自动报告生成工作流",
    "description": "根据用户输入的主题，自动搜索多源资料、整理分析、生成报告大纲（支持重试）、撰写完整内容、质量检查（支持修改）、最终输出报告并通知用户。",
    "version": "1.0.0",
    "metadata": {
      "author": "AI Assistant",
      "created_at": "2024-01-15T10:30:00Z",
      "source_input": "那个，我想做一个自动写报告的流程...",
      "tags": ["报告生成", "自动化", "多源搜索", "AI写作"]
    },
    
    "nodes": [
      {
        "node_id": "node_control_001",
        "node_name": "输入准备",
        "node_type": "control_node",
        "node_subtype": "input_node",
        "description": "接收并验证用户输入的主题，初始化工作流状态",
        "input_schema": {
          "fields": [
            {"name": "topic", "type": "string", "required": true, "description": "报告主题"},
            {"name": "user_email", "type": "string", "required": false, "description": "用户邮箱地址"},
            {"name": "config", "type": "object", "required": false, "description": "可选配置参数"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "validated_topic", "type": "string", "required": true, "description": "验证后的主题"},
            {"name": "workflow_config", "type": "object", "required": true, "description": "工作流配置"}
          ]
        },
        "metadata": {
          "inference_type": "implicit",
          "confidence": 0.9
        }
      },
      
      {
        "node_id": "node_tool_001",
        "node_name": "网页搜索",
        "node_type": "tool_node",
        "node_subtype": "search",
        "description": "从网页搜索相关资料",
        "input_schema": {
          "fields": [
            {"name": "query", "type": "string", "required": true, "description": "搜索关键词"},
            {"name": "max_results", "type": "number", "required": false, "description": "最大结果数"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "results", "type": "array", "required": true, "description": "搜索结果列表"},
            {"name": "source", "type": "string", "required": true, "description": "来源标识"}
          ]
        },
        "config": {
          "search_engine": "default",
          "max_results": 10
        },
        "metadata": {
          "source_text": "网页",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_tool_002",
        "node_name": "数据库搜索",
        "node_type": "tool_node",
        "node_subtype": "database",
        "description": "从数据库搜索相关资料",
        "input_schema": {
          "fields": [
            {"name": "query", "type": "string", "required": true, "description": "搜索关键词"},
            {"name": "max_results", "type": "number", "required": false, "description": "最大结果数"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "results", "type": "array", "required": true, "description": "搜索结果列表"},
            {"name": "source", "type": "string", "required": true, "description": "来源标识"}
          ]
        },
        "config": {
          "connection_string": "${env.DB_CONNECTION_STRING}",
          "max_results": 10
        },
        "metadata": {
          "source_text": "数据库",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_tool_003",
        "node_name": "文档库搜索",
        "node_type": "tool_node",
        "node_subtype": "search",
        "description": "从文档库搜索相关资料",
        "input_schema": {
          "fields": [
            {"name": "query", "type": "string", "required": true, "description": "搜索关键词"},
            {"name": "max_results", "type": "number", "required": false, "description": "最大结果数"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "results", "type": "array", "required": true, "description": "搜索结果列表"},
            {"name": "source", "type": "string", "required": true, "description": "来源标识"}
          ]
        },
        "config": {
          "doc_library_path": "${env.DOC_LIBRARY_PATH}",
          "max_results": 10
        },
        "metadata": {
          "source_text": "文档库",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_control_002",
        "node_name": "搜索结果合并",
        "node_type": "control_node",
        "node_subtype": "merge_node",
        "description": "合并来自多个来源的搜索结果",
        "input_schema": {
          "fields": [
            {"name": "web_results", "type": "array", "required": true, "description": "网页搜索结果"},
            {"name": "db_results", "type": "array", "required": true, "description": "数据库搜索结果"},
            {"name": "doc_results", "type": "array", "required": true, "description": "文档库搜索结果"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "merged_results", "type": "array", "required": true, "description": "合并后的结果列表"}
          ]
        },
        "metadata": {
          "inference_type": "implicit",
          "confidence": 0.9
        }
      },
      
      {
        "node_id": "node_thinking_001",
        "node_name": "结果整理",
        "node_type": "thinking_node",
        "node_subtype": "extraction",
        "description": "对搜索结果进行去重、排序、筛选，提取最相关的内容",
        "input_schema": {
          "fields": [
            {"name": "results", "type": "array", "required": true, "description": "搜索结果列表"},
            {"name": "topic", "type": "string", "required": true, "description": "主题用于相关性判断"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "organized_results", "type": "array", "required": true, "description": "整理后的结果"},
            {"name": "key_content", "type": "string", "required": true, "description": "提取的关键内容"}
          ]
        },
        "prompt_template": "请对以下搜索结果进行整理：\n主题：{topic}\n结果：{results}\n\n请执行以下操作：\n1. 去除重复内容\n2. 按相关性排序\n3. 筛选出最相关的10条\n4. 提取关键信息",
        "metadata": {
          "source_text": "把结果整理一下，去重、排序、筛选出最相关的",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_thinking_002",
        "node_name": "大纲生成",
        "node_type": "thinking_node",
        "node_subtype": "generation",
        "description": "分析资料并生成报告大纲",
        "input_schema": {
          "fields": [
            {"name": "key_content", "type": "string", "required": true, "description": "关键内容"},
            {"name": "topic", "type": "string", "required": true, "description": "报告主题"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "outline", "type": "object", "required": true, "description": "报告大纲结构"},
            {"name": "outline_text", "type": "string", "required": true, "description": "大纲文本"}
          ]
        },
        "prompt_template": "请根据以下资料生成报告大纲：\n主题：{topic}\n资料：{key_content}\n\n要求：\n1. 结构清晰，层次分明\n2. 包含3-5个主要章节\n3. 每个章节有2-4个子节\n4. 输出JSON格式的大纲结构",
        "metadata": {
          "source_text": "让AI分析这些资料，提取关键信息，生成一个报告大纲",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_control_003",
        "node_name": "大纲审核",
        "node_type": "control_node",
        "node_subtype": "human_approval",
        "description": "等待用户审核大纲，收集反馈",
        "input_schema": {
          "fields": [
            {"name": "outline_text", "type": "string", "required": true, "description": "大纲文本"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "approved", "type": "boolean", "required": true, "description": "是否通过"},
            {"name": "feedback", "type": "string", "required": false, "description": "修改建议"}
          ]
        },
        "config": {
          "timeout": 3600000,
          "notification": true
        },
        "metadata": {
          "source_text": "如果用户觉得不满意",
          "inference_type": "implicit",
          "confidence": 0.85
        }
      },
      
      {
        "node_id": "node_control_004",
        "node_name": "大纲重试判断",
        "node_type": "control_node",
        "node_subtype": "condition_node",
        "description": "判断是否需要重新生成大纲",
        "input_schema": {
          "fields": [
            {"name": "approved", "type": "boolean", "required": true, "description": "是否通过"},
            {"name": "retry_count", "type": "number", "required": true, "description": "当前重试次数"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "should_retry", "type": "boolean", "required": true, "description": "是否重试"},
            {"name": "branch", "type": "string", "required": true, "description": "分支决策"}
          ]
        },
        "config": {
          "max_retries": 3
        },
        "metadata": {
          "source_text": "最多重试3次",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_thinking_003",
        "node_name": "内容撰写",
        "node_type": "thinking_node",
        "node_subtype": "generation",
        "description": "根据大纲撰写完整的报告内容",
        "input_schema": {
          "fields": [
            {"name": "outline", "type": "object", "required": true, "description": "报告大纲"},
            {"name": "key_content", "type": "string", "required": true, "description": "参考资料"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "report_content", "type": "string", "required": true, "description": "报告内容"},
            {"name": "word_count", "type": "number", "required": true, "description": "字数统计"}
          ]
        },
        "prompt_template": "请根据以下大纲撰写完整报告：\n大纲：{outline}\n\n参考资料：{key_content}\n\n要求：\n1. 内容详实，逻辑清晰\n2. 每个章节充分展开\n3. 语言专业、流畅\n4. 总字数控制在2000-5000字",
        "metadata": {
          "source_text": "根据大纲写完整的报告内容",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_thinking_004",
        "node_name": "质量检查",
        "node_type": "thinking_node",
        "node_subtype": "evaluation",
        "description": "检查报告的完整性和逻辑性",
        "input_schema": {
          "fields": [
            {"name": "report_content", "type": "string", "required": true, "description": "报告内容"},
            {"name": "outline", "type": "object", "required": true, "description": "报告大纲"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "passed", "type": "boolean", "required": true, "description": "是否通过"},
            {"name": "score", "type": "number", "required": true, "description": "质量评分"},
            {"name": "issues", "type": "array", "required": false, "description": "问题列表"},
            {"name": "suggestions", "type": "string", "required": false, "description": "修改建议"}
          ]
        },
        "prompt_template": "请检查以下报告的质量：\n报告内容：{report_content}\n\n检查维度：\n1. 完整性：是否覆盖大纲所有章节\n2. 逻辑性：论述是否连贯、有逻辑\n3. 专业性：语言是否专业、准确\n4. 可读性：结构是否清晰、易读\n\n请给出评分（0-100）和具体问题。",
        "metadata": {
          "source_text": "做质量检查，检查报告是否完整、是否有逻辑问题",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_control_005",
        "node_name": "质量检查判断",
        "node_type": "control_node",
        "node_subtype": "condition_node",
        "description": "判断质量检查结果，决定是否需要修改",
        "input_schema": {
          "fields": [
            {"name": "passed", "type": "boolean", "required": true, "description": "是否通过"},
            {"name": "revision_count", "type": "number", "required": true, "description": "当前修改次数"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "need_revision", "type": "boolean", "required": true, "description": "是否需要修改"},
            {"name": "branch", "type": "string", "required": true, "description": "分支决策"}
          ]
        },
        "config": {
          "max_revisions": 2
        },
        "metadata": {
          "source_text": "如果没通过就返回修改，最多修改2次",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_tool_004",
        "node_name": "文件保存",
        "node_type": "tool_node",
        "node_subtype": "file_operation",
        "description": "将报告保存为文件",
        "input_schema": {
          "fields": [
            {"name": "content", "type": "string", "required": true, "description": "报告内容"},
            {"name": "filename", "type": "string", "required": true, "description": "文件名"},
            {"name": "format", "type": "string", "required": false, "description": "文件格式"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "file_path", "type": "string", "required": true, "description": "保存路径"},
            {"name": "file_size", "type": "number", "required": true, "description": "文件大小"}
          ]
        },
        "config": {
          "output_dir": "${env.OUTPUT_DIR}",
          "default_format": "markdown"
        },
        "metadata": {
          "source_text": "把报告保存成文件",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_tool_005",
        "node_name": "邮件发送",
        "node_type": "tool_node",
        "node_subtype": "email",
        "description": "发送邮件通知用户",
        "input_schema": {
          "fields": [
            {"name": "to", "type": "string", "required": true, "description": "收件人邮箱"},
            {"name": "subject", "type": "string", "required": true, "description": "邮件主题"},
            {"name": "body", "type": "string", "required": true, "description": "邮件正文"},
            {"name": "attachment", "type": "string", "required": false, "description": "附件路径"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "message_id", "type": "string", "required": true, "description": "邮件ID"},
            {"name": "status", "type": "string", "required": true, "description": "发送状态"}
          ]
        },
        "config": {
          "smtp_server": "${env.SMTP_SERVER}",
          "from_address": "${env.FROM_EMAIL}"
        },
        "metadata": {
          "source_text": "发送邮件通知用户",
          "inference_type": "explicit",
          "confidence": 0.95
        }
      },
      
      {
        "node_id": "node_control_006",
        "node_name": "结果输出",
        "node_type": "control_node",
        "node_subtype": "output_node",
        "description": "汇总并输出工作流最终结果",
        "input_schema": {
          "fields": [
            {"name": "file_path", "type": "string", "required": true, "description": "报告文件路径"},
            {"name": "email_status", "type": "string", "required": true, "description": "邮件发送状态"}
          ]
        },
        "output_schema": {
          "fields": [
            {"name": "final_result", "type": "object", "required": true, "description": "最终结果"}
          ]
        },
        "metadata": {
          "inference_type": "implicit",
          "confidence": 0.9
        }
      }
    ],
    
    "edges": [
      {
        "edge_id": "edge_input_web_sequential",
        "source": "node_control_001",
        "target": "node_tool_001",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_input_db_sequential",
        "source": "node_control_001",
        "target": "node_tool_002",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_input_doc_sequential",
        "source": "node_control_001",
        "target": "node_tool_003",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_web_merge_sequential",
        "source": "node_tool_001",
        "target": "node_control_002",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_db_merge_sequential",
        "source": "node_tool_002",
        "target": "node_control_002",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_doc_merge_sequential",
        "source": "node_tool_003",
        "target": "node_control_002",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_merge_organize_sequential",
        "source": "node_control_002",
        "target": "node_thinking_001",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_organize_outline_sequential",
        "source": "node_thinking_001",
        "target": "node_thinking_002",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_outline_review_sequential",
        "source": "node_thinking_002",
        "target": "node_control_003",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_review_retry_conditional",
        "source": "node_control_003",
        "target": "node_control_004",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_retry_outline_conditional",
        "source": "node_control_004",
        "target": "node_thinking_002",
        "edge_type": "conditional",
        "condition": {
          "expression": "approved == false AND retry_count < 3",
          "variables": ["approved", "retry_count"],
          "operator": "and"
        }
      },
      {
        "edge_id": "edge_retry_content_conditional",
        "source": "node_control_004",
        "target": "node_thinking_003",
        "edge_type": "conditional",
        "condition": {
          "expression": "approved == true",
          "variables": ["approved"],
          "operator": "eq"
        }
      },
      {
        "edge_id": "edge_content_quality_sequential",
        "source": "node_thinking_003",
        "target": "node_thinking_004",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_quality_check_sequential",
        "source": "node_thinking_004",
        "target": "node_control_005",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_check_revision_conditional",
        "source": "node_control_005",
        "target": "node_thinking_003",
        "edge_type": "conditional",
        "condition": {
          "expression": "passed == false AND revision_count < 2",
          "variables": ["passed", "revision_count"],
          "operator": "and"
        }
      },
      {
        "edge_id": "edge_check_output_conditional",
        "source": "node_control_005",
        "target": "node_tool_004",
        "edge_type": "conditional",
        "condition": {
          "expression": "passed == true",
          "variables": ["passed"],
          "operator": "eq"
        }
      },
      {
        "edge_id": "edge_file_final_sequential",
        "source": "node_tool_004",
        "target": "node_control_006",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_email_final_sequential",
        "source": "node_tool_005",
        "target": "node_control_006",
        "edge_type": "sequential"
      },
      {
        "edge_id": "edge_file_email_parallel",
        "source": "node_tool_004",
        "target": "node_tool_005",
        "edge_type": "parallel"
      }
    ],
    
    "state_schema": {
      "fields": [
        {
          "name": "topic",
          "type": "string",
          "required": true,
          "description": "报告主题",
          "state_type": "input"
        },
        {
          "name": "user_email",
          "type": "string",
          "required": false,
          "description": "用户邮箱地址",
          "state_type": "input"
        },
        {
          "name": "search_results",
          "type": "array",
          "required": false,
          "description": "搜索结果列表",
          "state_type": "intermediate"
        },
        {
          "name": "organized_content",
          "type": "string",
          "required": false,
          "description": "整理后的关键内容",
          "state_type": "intermediate"
        },
        {
          "name": "outline",
          "type": "object",
          "required": false,
          "description": "报告大纲",
          "state_type": "intermediate"
        },
        {
          "name": "outline_retry_count",
          "type": "number",
          "required": false,
          "default": 0,
          "description": "大纲重试次数",
          "state_type": "control"
        },
        {
          "name": "report_content",
          "type": "string",
          "required": false,
          "description": "报告内容",
          "state_type": "intermediate"
        },
        {
          "name": "quality_score",
          "type": "number",
          "required": false,
          "description": "质量评分",
          "state_type": "intermediate"
        },
        {
          "name": "revision_count",
          "type": "number",
          "required": false,
          "default": 0,
          "description": "内容修改次数",
          "state_type": "control"
        },
        {
          "name": "final_report_path",
          "type": "string",
          "required": false,
          "description": "最终报告文件路径",
          "state_type": "output"
        },
        {
          "name": "email_sent",
          "type": "boolean",
          "required": false,
          "default": false,
          "description": "邮件是否已发送",
          "state_type": "output"
        }
      ]
    },
    
    "entry_point": "node_control_001",
    "finish_point": "node_control_006",
    
    "config": {
      "timeout": 600000,
      "max_retries": 3,
      "enable_checkpoint": true,
      "enable_logging": true
    }
  }
}
```

---

## 9. 异常处理机制

### 9.1 输入异常处理

| 异常类型 | 检测条件 | 处理策略 |
|----------|----------|----------|
| 输入为空 | 输入文本长度为0 | 返回错误，提示用户输入内容 |
| 输入过短 | 输入文本长度 < 10 | 提示用户补充更多细节 |
| 输入模糊 | 无法识别任何有效节点 | 启动澄清模式，引导用户描述 |
| 输入矛盾 | 存在逻辑矛盾的描述 | 标注矛盾点，请求用户澄清 |

### 9.2 解析异常处理

| 异常类型 | 检测条件 | 处理策略 |
|----------|----------|----------|
| 节点识别失败 | 无法识别任何节点 | 返回错误，建议用户重新描述 |
| 边关系不完整 | 存在孤立节点 | 推断可能的连接关系，标注为假设 |
| 状态推断失败 | 无法推断必要状态 | 使用默认值，标注为待确认 |
| Schema验证失败 | 输出不符合Schema | 尝试修复，或返回错误 |

### 9.3 澄清机制

```json
{
  "clarification_mechanism": {
    "trigger_conditions": [
      "ambiguities.length > 0",
      "confidence < 0.7",
      "required_fields_missing"
    ],
    
    "clarification_flow": [
      {
        "step": 1,
        "action": "生成澄清问题列表",
        "output": "questions array"
      },
      {
        "step": 2,
        "action": "等待用户回答",
        "timeout": "可配置"
      },
      {
        "step": 3,
        "action": "合并回答到原始输入",
        "output": "updated input"
      },
      {
        "step": 4,
        "action": "重新执行解析流程",
        "max_iterations": 3
      }
    ],
    
    "question_template": {
      "type": "single_choice|multiple_choice|text_input",
      "question": "问题内容",
      "context": "相关上下文",
      "options": ["选项列表"],
      "default": "默认值"
    }
  }
}
```

---

## 10. 质量检查清单

### 10.1 输入分析检查

- [ ] 是否正确识别了所有显式节点？
- [ ] 是否推断出必要的隐式节点？
- [ ] 是否识别了所有边关系？
- [ ] 是否正确分类了节点类型？
- [ ] 是否检测到所有歧义点？
- [ ] 是否为每个推断提供了依据？

### 10.2 配置完整性检查

- [ ] 所有节点是否有唯一ID？
- [ ] 所有边是否有有效的source和target？
- [ ] 是否存在孤立节点（无入边或无出边）？
- [ ] 入口节点是否正确设置？
- [ ] 结束节点/条件是否明确？
- [ ] 状态字段是否覆盖所有必要数据？

### 10.3 配置一致性检查

- [ ] 边的source和target是否都是有效节点ID？
- [ ] 节点的input_schema是否与上游output_schema匹配？
- [ ] 条件边是否都有对应的条件表达式？
- [ ] 循环边是否都有终止条件？
- [ ] 并行边是否都有合并节点？

### 10.4 配置可执行性检查

- [ ] 所有工具节点是否有可用的工具实现？
- [ ] 所有思维节点是否有有效的prompt_template？
- [ ] 所有控制节点是否有正确的配置？
- [ ] 状态字段类型是否正确？
- [ ] 必填字段是否都有默认值或来源？

---

## 附录A: 关键词词典

### A.1 动作关键词

| 类别 | 关键词 |
|------|--------|
| 搜索 | 搜索、查找、检索、查询、找、搜、seek、search、query |
| 分析 | 分析、评估、判断、检查、审核、审查、analyze、evaluate |
| 生成 | 生成、创建、编写、撰写、产出、输出、制作、generate、create |
| 处理 | 处理、整理、归纳、总结、提取、转换、process、transform |
| 交互 | 确认、询问、通知、发送、等待、审批、confirm、notify |
| 控制 | 判断、分支、循环、跳转、终止、暂停、if、loop、break |

### A.2 条件关键词

| 类别 | 关键词 |
|------|--------|
| 成功 | 成功、完成、通过、符合、满足、success、pass |
| 失败 | 失败、错误、不通过、不符合、异常、fail、error |
| 比较 | 大于、小于、等于、超过、不足、gt、lt、eq |
| 状态 | 存在、不存在、为空、非空、exist、empty |

### A.3 连接关键词

| 类别 | 关键词 |
|------|--------|
| 顺序 | 然后、接着、之后、再、完成后、then、next、after |
| 条件 | 如果、要是、假如、若、当...时、否则、不然、if、else |
| 并行 | 同时、与此同时、另外、并且、同步、parallel、async |
| 循环 | 重复、循环、直到、不断、反复、loop、repeat、until |

---

## 附录B: 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| V1.0 | 2024-01-15 | 初始版本，包含完整的提示词机制和规则定义 |

---

**文档结束**
