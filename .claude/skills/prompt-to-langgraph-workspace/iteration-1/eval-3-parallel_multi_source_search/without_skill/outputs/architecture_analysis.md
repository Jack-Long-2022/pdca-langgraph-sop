# 并行多源搜索工作流 - 技术架构分析

## 工作流概述

此工作流实现了从三个数据源（网页、数据库、文档库）并行搜索，然后合并结果并生成摘要的完整流程。

## 并行执行机制

### 1. 并行组设计 (parallel_search)

```json
"parallel_execution": {
  "parallel_search": {
    "execution_mode": "concurrent",
    "max_concurrent_tasks": 3,
    "timeout": 60000,
    "continue_on_error": true,
    "error_handling": "collect_and_continue"
  }
}
```

**关键特性：**
- **执行模式**: `concurrent` - 所有搜索任务同时启动
- **并发控制**: 最多3个任务同时执行（对应3个数据源）
- **超时保护**: 60秒总超时，防止单个源阻塞整个流程
- **容错机制**: `continue_on_error: true` 确保某个源失败不影响其他源

### 2. 并行节点结构

```
start
  ├── search_web (并行组: parallel_search)
  ├── search_database (并行组: parallel_search)
  └── search_documents (并行组: parallel_search)
       │
       ▼ (所有并行任务完成后)
  collect_results (merge节点)
```

**并行执行的LangGraph实现概念：**
```python
from langgraph.graph import StateGraph
from typing import TypedDict, Annotated
import operator

# 定义状态结构
class WorkflowState(TypedDict):
    search_query: str
    web_results: Annotated[list, operator.add]
    database_results: Annotated[list, operator.add]
    document_results: Annotated[list, operator.add]
    merged_results: list
    summary: dict
    errors: list

# 并行执行函数
async def execute_parallel_searches(state: WorkflowState):
    """并行执行三个搜索任务"""
    import asyncio

    tasks = [
        search_web(state),
        search_database(state),
        search_documents(state)
    ]

    # 并行执行，使用gather等待所有任务完成
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理结果和异常
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            state['errors'].append({
                'source': ['web', 'database', 'documents'][i],
                'error': str(result)
            })
        else:
            # 结果已通过operator.add自动合并到state中
            pass

    return state
```

## 合并机制 (Merge Mechanism)

### 1. 合并节点配置

```json
{
  "id": "collect_results",
  "type": "merge",
  "merge_type": "parallel_reduce",
  "config": {
    "wait_for_all": true,
    "merge_strategy": "concatenate_deduplicate",
    "deduplication_field": "url",
    "sort_by": "relevance",
    "max_total_results": 100
  }
}
```

### 2. 合并策略详解

#### A. 等待机制 (`wait_for_all: true`)
- **目的**: 确保所有并行搜索任务都完成后再合并
- **实现**: LangGraph的Join节点天然支持等待所有入边完成
- **优势**: 保证数据的完整性，不会遗漏任何来源的结果

#### B. 连接与去重 (`concatenate_deduplicate`)

**实现逻辑：**
```python
def merge_results(state: WorkflowState):
    """合并并去重结果"""

    # 1. 收集所有结果
    all_results = []
    all_results.extend(state.get('web_results', []))
    all_results.extend(state.get('database_results', []))
    all_results.extend(state.get('document_results', []))

    # 2. 去重（基于URL）
    seen_urls = set()
    unique_results = []
    for result in all_results:
        url = result.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(result)
        elif not url:
            # 没有URL的结果（如数据库记录）直接添加
            unique_results.append(result)

    # 3. 排序（按相关性）
    unique_results.sort(
        key=lambda x: x.get('relevance', 0),
        reverse=True
    )

    # 4. 限制数量
    state['merged_results'] = unique_results[:100]

    # 5. 统计来源分布
    state['source_breakdown'] = {
        'web': len(state.get('web_results', [])),
        'database': len(state.get('database_results', [])),
        'documents': len(state.get('document_results', [])),
        'unique_after_deduplication': len(unique_results)
    }

    return state
```

#### C. 去重算法

**Hash-based去重：**
```python
def hash_based_deduplication(results, field='url'):
    """基于哈希的去重算法"""
    seen = set()
    unique = []

    for item in results:
        field_value = item.get(field)
        if field_value:
            # 使用哈希快速查找
            hash_value = hash(field_value)
            if hash_value not in seen:
                seen.add(hash_value)
                unique.append(item)
        else:
            unique.append(item)

    return unique
```

### 3. 状态合并机制 (State Merging)

**LangGraph的Reducer模式：**
```python
from typing import Annotated
import operator

class WorkflowState(TypedDict):
    # 使用operator.add自动合并列表
    web_results: Annotated[list, operator.add]
    database_results: Annotated[list, operator.add]
    document_results: Annotated[list, operator.add]

# 当并行分支都完成时，LangGraph会自动使用operator.add
# 将各分支的结果合并到最终state中
```

## 摘要生成机制

### 1. LLM驱动的摘要生成

```json
{
  "summary_type": "comprehensive",
  "max_length": 500,
  "include_key_points": true,
  "include_source_counts": true,
  "llm_model": "claude-3-5-sonnet",
  "temperature": 0.7
}
```

### 2. 摘要生成实现

```python
from anthropic import Anthropic

def generate_summary(state: WorkflowState):
    """生成综合摘要"""

    client = Anthropic()

    # 构建提示词
    prompt = f"""
基于以下来自多个来源的搜索结果，生成一个综合摘要：

来源分布：
- 网页: {state['source_breakdown']['web']} 条
- 数据库: {state['source_breakdown']['database']} 条
- 文档库: {state['source_breakdown']['documents']} 条

搜索结果（前20条最相关）：
{format_results_for_llm(state['merged_results'][:20])}

请生成：
1. 一个简洁的摘要（最多500字）
2. 3-5个关键点
3. 各来源的独特价值

摘要内容：
"""

    # 调用LLM
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        temperature=0.7,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )

    state['summary'] = {
        'content': response.content[0].text,
        'key_points': extract_key_points(response.content[0].text),
        'source_counts': state['source_breakdown'],
        'timestamp': datetime.now().isoformat()
    }

    return state
```

## 执行流程时序图

```
时间轴 →

0ms    [开始] start
       |
       ├───[并行启动]────────────────────────────────┐
       │                                            │
100ms  ├─ search_web ───────────────────────────────┤
       │  (搜索引擎API调用)                          │
500ms  ├─ search_database ──────────────────────────┤
       │  (SQL查询)                                  │
800ms  ├─ search_documents ─────────────────────────┤
       │  (Elasticsearch查询)                       │
       │                                            │
2000ms └─[全部完成]─────────────────────────────────┘
              │
              ▼
2100ms   [合并] collect_results
         - 连接所有结果
         - 去重（基于URL）
         - 排序（按相关性）
         - 限制数量（最多100条）
              │
              ▼
3000ms   [摘要] generate_summary
         - 调用LLM生成摘要
         - 提取关键点
              │
              ▼
5000ms   [格式化] format_output
         - 生成JSON格式
         - 生成Markdown格式
         - 添加执行指标
              │
              ▼
5500ms   [结束] end
```

## 性能优化特性

### 1. 并行加速
- **理论加速比**: 3x（三个源同时搜索）
- **实际加速比**: 2.5-2.8x（考虑网络和IO瓶颈）

### 2. 容错机制
```python
# 单个源失败的处理
async def search_with_retry(source_func, source_name):
    try:
        return await source_func()
    except Exception as e:
        logger.error(f"{source_name} 搜索失败: {e}")
        return []  # 返回空列表，不阻塞其他任务
```

### 3. 超时保护
- 单个源超时: 25-30秒
- 总并行组超时: 60秒
- 防止慢速源拖累整个流程

## 数据流图

```
输入: search_query
    │
    ▼
┌───┴────┐
│  START │
└───┬────┘
    │
    ├──────────────────────────────────────┐
    │                                      │
    ▼                                      ▼
┌────────┐    ┌────────┐    ┌──────────┐
│ Web    │    │ DB     │    │ Docs     │
│ Search │    │ Search │    │ Search   │
└────┬───┘    └────┬───┘    └────┬─────┘
     │             │             │
     └──────┬──────┴──────┬──────┘
            │             │
            ▼             ▼
         ┌──────────────────┐
         │  MERGE (Reduce)  │
         │  - Concatenate   │
         │  - Deduplicate   │
         │  - Sort          │
         │  - Limit         │
         └────────┬─────────┘
                  │
                  ▼
            ┌──────────┐
            │ Summary  │
            │ (LLM)    │
            └────┬─────┘
                 │
                 ▼
            ┌──────────┐
            │ Format   │
            └────┬─────┘
                 │
                 ▼
            ┌──────────┐
            │  END     │
            └──────────┘
```

## 关键技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 并行模式 | Concurrent | 最大化性能，三个源独立无依赖 |
| 合并策略 | Wait for all | 保证数据完整性 |
| 去重字段 | URL | 唯一标识符，跨来源通用 |
| 排序字段 | Relevance | 用户最关心相关性 |
| LLM模型 | Claude Sonnet | 平衡质量和速度 |
| 容错策略 | Continue on error | 单个源失败不阻塞整体 |

## 总结

此工作流通过LangGraph的并行执行能力，实现了高效的多源数据聚合：
1. **并行执行**节省时间（3个源同时搜索）
2. **智能合并**确保数据质量（去重、排序、限制）
3. **LLM摘要**提供价值提炼（综合分析、关键点提取）
4. **容错设计**保证稳定性（单点失败不影响整体）
