# 结构化抽取工作原理详解

## 核心发现

**结构化抽取主要使用规则/正则表达式，而非直接调用LLM！**

```
输入文本 → 正则/规则提取 → 结构化数据 → LLM细化 → 最终配置
         ↑ 主要方法        ↑ 中间结果    ↑ 可选步骤
```

## 详细流程图

```
┌─────────────────────────────────────────────────────────────┐
│                    输入: 用户描述文本                         │
│  "首先调用API获取数据，然后清洗数据，接着分析趋势..."          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              第一步: 正则表达式提取 (规则提取)                  │
├─────────────────────────────────────────────────────────────┤
│  NodeExtractor: 使用预定义模式匹配动词短语                    │
│                                                               │
│  匹配模式:                                                     │
│  1. (首先|先|第一|接着|然后|之后)([^\\n，。！？]+)              │
│  2. ([^\\n，。！？]+(调用|执行|运行|使用|获取|...))            │
│                                                               │
│  示例提取结果:                                                 │
│  - "调用API获取数据"                                          │
│  - "清洗数据"                                                 │
│  - "分析趋势"                                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              第二步: 关键词分类 (规则分类)                      │
├─────────────────────────────────────────────────────────────┤
│  根据预定义关键词列表识别节点类型:                              │
│                                                               │
│  TOOL_KEYWORDS = ['调用', '执行', '获取', '查询', ...]        │
│  THOUGHT_KEYWORDS = ['分析', '思考', '判断', '评估', ...]     │
│  CONTROL_KEYWORDS = ['开始', '结束', '如果', '当', ...]       │
│                                                               │
│  分类逻辑:                                                     │
│  if phrase contains TOOL_KEYWORDS → type = 'tool'            │
│  elif phrase contains THOUGHT_KEYWORDS → type = 'thought'    │
│  elif phrase contains CONTROL_KEYWORDS → type = 'control'    │
│                                                               │
│  示例分类结果:                                                 │
│  - "调用API获取数据" → type = 'tool'                         │
│  - "清洗数据" → type = 'tool'                               │
│  - "分析趋势" → type = 'thought'                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              第三步: 边连接识别 (规则识别)                       │
├─────────────────────────────────────────────────────────────┤
│  EdgeExtractor: 识别节点间的关系                               │
│                                                               │
│  连接词列表:                                                   │
│  SEQUENTIAL_WORDS = ['然后', '接着', '之后', '随后', ...]      │
│  CONDITIONAL_WORDS = ['如果', '当', '只要', ...]              │
│                                                               │
│  示例连接结果:                                                 │
│  - "调用API" --[然后]--> "清洗数据"                           │
│  - "清洗数据" --[接着]--> "分析趋势"                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              第四步: 状态提取 (规则提取)                         │
├─────────────────────────────────────────────────────────────┤
│  StateExtractor: 使用正则模式匹配数据对象                       │
│                                                               │
│  匹配模式:                                                     │
│  - '([^，,。\\n]{1,5})的结果' → state.field_name             │
│  - '([^，,。\\n]{1,5})的数据' → state.field_name             │
│                                                               │
│  类型推断:                                                     │
│  - field_name contains '数量' → type = 'integer'            │
│  - field_name contains '列表' → type = 'array'              │
│  - otherwise → type = 'string'                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              第五步: 结构化文档输出                              │
├─────────────────────────────────────────────────────────────┤
│  StructuredDocument:                                         │
│  {                                                            │
│    nodes: [                                                  │
│      {node_id, name, type, description, ...},                │
│      ...                                                      │
│    ],                                                         │
│    edges: [                                                  │
│      {source, target, condition, type},                      │
│      ...                                                      │
│    ],                                                         │
│    states: [...]                                             │
│  }                                                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│           第六步: LLM细化 (可选，在ConfigGenerator中)          │
├─────────────────────────────────────────────────────────────┤
│  如果提供LLM，则进行节点细化:                                   │
│                                                               │
│  Prompt示例:                                                  │
│  "请细化以下节点描述，使其更加精确和可执行。                      │
│   节点名称: 调用API获取数据                                     │
│   当前描述: 从文本抽取: 调用API获取数据                          │
│   节点类型: tool                                              │
│                                                               │
│  请生成:                                                       │
│  1. 更精确的节点名称                                            │
│  2. 详细的节点描述                                              │
│  3. 输入参数列表                                               │
│  4. 输出参数列表                                               │
│  5. 建议的配置参数"                                             │
│                                                               │
│  LLM输出后将用于增强节点的inputs/outputs/config字段             │
└─────────────────────────────────────────────────────────────┘
```

## 代码示例解析

### 1. 正则表达式提取

```python
def _extract_verb_phrases(self, text: str) -> list[str]:
    """提取动词短语"""
    patterns = [
        # 匹配: "首先xxx", "然后xxx", "接着xxx"
        r'(?:首先|先|第一|接着|然后|之后|随后|最后|最终)([^\n，。！？]+)',
        
        # 匹配包含动作词的短语
        r'([^\n，。！？]+(?:调用|执行|运行|使用|获取|查询|分析|判断|生成|创建))',
    ]
    
    phrases = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        phrases.extend(matches)
    
    return phrases
```

**输入示例**: "首先调用API获取数据，然后清洗数据，接着分析趋势"

**提取结果**: 
- "调用API获取数据"
- "清洗数据"
- "分析趋势"

### 2. 关键词分类

```python
def _identify_node_type(self, verb_phrase: str) -> str:
    """识别节点类型"""
    
    # 检查控制关键词
    for keyword in self.CONTROL_KEYWORDS:
        if verb_phrase.startswith(keyword):
            return 'control'
    
    # 检查思维关键词
    for keyword in self.THOUGHT_KEYWORDS:
        if keyword in verb_phrase:
            return 'thought'
    
    # 检查工具关键词
    for keyword in self.TOOL_KEYWORDS:
        if keyword in verb_phrase:
            return 'tool'
    
    return 'tool'
```

**分类示例**:
- "调用API获取数据" → 包含"调用"、"获取" → `tool`
- "分析趋势" → 包含"分析" → `thought`
- "如果数据不完整" → 以"如果"开头 → `control`

### 3. LLM细化 (可选)

```python
def _refine_nodes_with_llm(self, config: WorkflowConfig, llm):
    """使用LLM细化节点"""
    refined_nodes = []
    
    for node in config.nodes:
        prompt = PromptTemplates.get_node_refinement_prompt(
            node_name=node.name,
            node_description=node.description or "",
            node_type=node.type
        )
        
        # 调用LLM
        response = llm.generate(prompt)
        refined_data = self._parse_llm_json_response(response)
        
        if refined_data:
            # 用LLM的结果增强节点
            node.name = refined_data.get("name", node.name)
            node.description = refined_data.get("description", node.description)
            node.inputs = refined_data.get("inputs", node.inputs)
            node.outputs = refined_data.get("outputs", node.outputs)
        
        refined_nodes.append(node)
    
    return refined_nodes
```

## 优缺点分析

### 优点
✅ **快速**: 正则表达式匹配速度快，不需要等待LLM响应
✅ **可控**: 规则明确，行为可预测
✅ **低成本**: 不消耗大量API调用
✅ **可调试**: 可以直接看到匹配结果

### 缺点
❌ **刚性**: 只能匹配预定义的模式
❌ **扩展性差**: 新的表达方式需要修改代码
❌ **语义理解弱**: 无法理解复杂或隐含的表达

## 为什么这样设计？

这是一个**混合架构**的设计决策：

```
规则提取 (快速、可控) → LLM细化 (智能、灵活)
```

1. **规则提取**: 处理80%的常见情况，快速且可控
2. **LLM细化**: 处理剩余20%的复杂情况，提供智能增强

这种设计在**效率**和**质量**之间取得了平衡。

## 实际运行示例

**输入文本**:
```
我想创建一个自动化流程：
首先调用API获取销售数据，
然后对数据进行清洗，
接着分析销售趋势，
最后生成报告并发送邮件。
```

**提取结果**:
```
nodes: [
  {id: "node_abc", name: "调用API获取销售数据", type: "tool"},
  {id: "node_def", name: "对数据进行清洗", type: "tool"},
  {id: "node_ghi", name: "分析销售趋势", type: "thought"},
  {id: "node_jkl", name: "生成报告并发送邮件", type: "tool"}
]

edges: [
  {source: "node_abc", target: "node_def", type: "sequential"},
  {source: "node_def", target: "node_ghi", type: "sequential"},
  {source: "node_ghi", target: "node_jkl", type: "sequential"}
]
```

## 如何自定义规则？

如果需要支持新的表达方式，可以修改关键词列表：

```python
# 添加新的关键词
TOOL_KEYWORDS = [
    '调用', '执行', '运行', 
    '抓取',  # 新增
    '下载',  # 新增
    ...
]

# 添加新的正则模式
patterns = [
    r'(?:首先|先|第一)([^\n，。！？]+)',
    r'步骤(\d+):([^\n，。！？]+)',  # 新增: "步骤1:xxx"
    ...
]
```

## 总结

| 方法 | 使用位置 | 作用 | 优缺点 |
|------|----------|------|--------|
| **正则表达式** | StructuredExtractor | 快速提取结构 | 快但不灵活 |
| **关键词匹配** | NodeExtractor/EdgeExtractor | 分类节点/边 | 简单但刚性 |
| **LLM细化** | ConfigGenerator | 智能增强 | 灵活但慢 |
