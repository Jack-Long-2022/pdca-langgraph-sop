# 结构化抽取工作原理 - 简明版

## 核心机制

**不是直接调用LLM，而是使用正则表达式 + 关键词匹配！**

```
输入文本 → 正则提取短语 → 关键词分类 → 结构化输出
```

## 三大提取器

### 1️⃣ NodeExtractor (节点提取器)

**工作方式**: 正则表达式 + 关键词匹配

```python
# 第一步: 正则提取动词短语
patterns = [
    r'(?:首先|先|第一|接着|然后)([^\n，。！？]+)',
    r'([^\n，。！？]+(?:调用|执行|运行|使用|获取))',
]
phrases = re.findall(patterns, text)

# 第二步: 关键词分类
if '调用' in phrase: → type = 'tool'
elif '分析' in phrase: → type = 'thought'
elif '如果' in phrase: → type = 'control'
```

**示例**:
```
输入: "首先调用API，然后分析数据"
提取: ["调用API", "分析数据"]
分类: ["tool", "thought"]
```

### 2️⃣ EdgeExtractor (边提取器)

**工作方式**: 连接词匹配

```python
# 查找连接词
SEQUENTIAL_WORDS = ['然后', '接着', '之后', '随后']
CONDITIONAL_WORDS = ['如果', '当', '只要']

# 根据连接词确定边类型
if '然后' in text: → edge_type = 'sequential'
if '如果' in text: → edge_type = 'conditional'
```

**示例**:
```
输入: "调用API，然后分析数据，接着生成报告"
连接: node1 --[然后]--> node2 --[接着]--> node3
```

### 3️⃣ StateExtractor (状态提取器)

**工作方式**: 正则模式匹配

```python
# 匹配数据对象模式
patterns = [
    r'(.{1,5})的结果',
    r'(.{1,5})的数据',
    r'(.{1,5})的列表',
]

# 根据字段名推断类型
if '数量' in field: → type = 'integer'
if '列表' in field: → type = 'array'
else: → type = 'string'
```

**示例**:
```
输入: "销售数据的结果，分析数据的列表"
提取: ["销售数据", "分析数据"]
类型: ["string", "array"]
```

## 完整流程示例

**输入**:
```
首先调用API获取销售数据，然后清洗数据，接着分析趋势，最后生成报告。
```

**处理**:
```
Step 1: 正则提取
  → ["调用API获取销售数据", "清洗数据", "分析趋势", "生成报告"]

Step 2: 关键词分类
  → [tool, tool, thought, tool]

Step 3: 边连接
  → node1 --[然后]--> node2 --[接着]--> node3 --[最后]--> node4

Step 4: 状态提取
  → ["销售数据": string, "分析结果": any]
```

**输出**:
```json
{
  "nodes": [
    {"name": "调用API获取销售数据", "type": "tool"},
    {"name": "清洗数据", "type": "tool"},
    {"name": "分析趋势", "type": "thought"},
    {"name": "生成报告", "type": "tool"}
  ],
  "edges": [
    {"source": "node1", "target": "node2", "type": "sequential"},
    {"source": "node2", "target": "node3", "type": "sequential"},
    {"source": "node3", "target": "node4", "type": "sequential"}
  ],
  "states": [
    {"field_name": "销售数据", "type": "string"},
    {"field_name": "分析结果", "type": "any"}
  ]
}
```

## 为什么不用LLM直接提取？

| 方法 | 速度 | 成本 | 可控性 | 准确率 |
|------|------|------|--------|--------|
| **正则+关键词** | ⚡ 快 | 💰 低 | ✅ 高 | 🔧 中等 |
| **纯LLM** | 🐌 慢 | 💸💸 高 | ❌ 低 | 🧠 高 |

**项目选择**: 混合方法
- 用正则处理常见模式（80%）
- 用LLM处理复杂情况（20%）

## LLM在哪里使用？

LLM不在提取阶段使用，而是在后续的**细化阶段**：

```
规则提取 → 粗糙的结构化数据
    ↓
LLM细化 → 精炼的配置文件
```

**细化示例**:
```python
# 规则提取的节点
node = {
    "name": "调用API获取销售数据",
    "description": "从文本抽取",
    "inputs": [],
    "outputs": []
}

# LLM细化后的节点
node = {
    "name": "调用销售数据API",
    "description": "从销售系统REST API获取本月的销售记录",
    "inputs": ["api_url", "api_key", "month"],
    "outputs": ["sales_data", "record_count"]
}
```

## 如何调试提取结果？

运行演示脚本查看详细过程：

```bash
python demo_extraction.py
```

或查看详细文档：

```bash
cat doc/extraction_explained.md
```

## 总结

```
┌─────────────────────────────────────────────────┐
│  结构化抽取 = 正则表达式 (70%) + 关键词匹配 (30%)  │
│  不直接调用LLM，而是用规则提取 + 可选LLM细化      │
└─────────────────────────────────────────────────┘
```

**关键点**:
1. ✅ 主要使用正则表达式，速度快
2. ✅ 关键词列表可自定义，易扩展
3. ✅ LLM仅在细化阶段可选使用
4. ✅ 整体设计平衡了速度和准确性
