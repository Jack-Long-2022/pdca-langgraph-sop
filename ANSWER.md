# 结构化抽取 - 完整解答

## 你的问题

> 结构化抽取是如何起作用的？是LLM调用什么提示词，还是进行了代码编程提取？

## 答案

**主要使用代码编程提取（正则表达式 + 关键词匹配），LLM仅在后续细化阶段可选使用。**

## 详细解释

### 方法一: 正则表达式提取 (主要方法)

```python
# 从文本中提取动词短语
patterns = [
    r'(?:首先|先|第一|接着|然后)([^\n，。！？]+)',
    r'([^\n，。！？]+(?:调用|执行|运行|使用|获取))',
]
phrases = re.findall(patterns, text)
```

**工作原理**: 使用预定义的正则模式匹配文本中的动词短语

**示例**:
```
输入: "首先调用API，然后清洗数据，接着分析"
提取: ["调用API", "清洗数据", "分析"]
```

### 方法二: 关键词分类 (辅助方法)

```python
TOOL_KEYWORDS = ['调用', '执行', '运行', '获取']
THOUGHT_KEYWORDS = ['分析', '判断', '评估', '生成']
CONTROL_KEYWORDS = ['开始', '结束', '如果', '当']

for keyword in TOOL_KEYWORDS:
    if keyword in phrase:
        return 'tool'
```

**工作原理**: 根据预定义的关键词列表匹配节点类型

**示例**:
```
"调用API" → 包含"调用" → type = 'tool'
"分析趋势" → 包含"分析" → type = 'thought'
"如果出错" → 包含"如果" → type = 'control'
```

### 方法三: LLM细化 (可选方法)

```python
# 仅在ConfigGenerator中可选使用
if llm is not None:
    response = llm.generate(prompt)
    # 用LLM结果增强节点
    node.description = response.get("description")
    node.inputs = response.get("inputs")
```

**工作原理**: 使用LLM对规则提取的结果进行细化和增强

**示例**:
```
规则提取: name="调用API", description="从文本抽取"
LLM细化: name="调用销售数据API", description="从REST API获取本月销售记录",
         inputs=["api_url", "api_key"], outputs=["sales_data"]
```

## 实际运行结果

刚才运行的测试显示：

```
输入: "首先调用API获取销售数据，然后清洗数据，接着分析趋势"

提取结果:
1. 动词短语: ["调用API获取销售数据", "清洗数据", "分析趋势"]
2. 节点分类: [tool, tool, thought]
3. 边连接: node1→node2→node3 (sequential)
```

## 为什么这样设计？

| 方法 | 优点 | 缺点 | 使用场景 |
|------|------|------|----------|
| **正则提取** | 快速、可控、零成本 | 刚性、扩展性差 | 处理80%常见模式 |
| **关键词匹配** | 简单、易理解 | 依赖预定义列表 | 快速分类节点类型 |
| **LLM细化** | 智能、灵活 | 慢、有成本 | 处理复杂情况和细化 |

**混合架构**: 正则提取 (快速基础) → LLM细化 (智能增强)

## 关键文件位置

| 文件 | 作用 |
|------|------|
| `pdca/plan/extractor.py` | 结构化抽取核心代码 |
| `pdca/plan/config_generator.py` | 配置生成和LLM细化 |
| `test_extraction_simple.py` | 简化测试脚本 |
| `doc/extraction_simple.md` | 详细说明文档 |

## 如何验证？

运行测试脚本查看实际效果：

```bash
python test_extraction_simple.py
```

或者查看详细文档：

```bash
cat doc/extraction_simple.md
```

## 总结

```
┌─────────────────────────────────────────────────────┐
│  结构化抽取 = 正则表达式 (主要) + 关键词匹配 (辅助)  │
│  LLM仅在细化阶段可选使用，不是主要提取方法          │
└─────────────────────────────────────────────────────┘
```

**核心要点**:
1. ✅ 主要使用**代码编程**（正则+关键词），速度快且可控
2. ✅ LLM是**可选的细化工具**，用于增强而非提取
3. ✅ 混合架构平衡了**效率**和**质量**
4. ✅ 可以通过修改关键词列表和正则模式来自定义行为
