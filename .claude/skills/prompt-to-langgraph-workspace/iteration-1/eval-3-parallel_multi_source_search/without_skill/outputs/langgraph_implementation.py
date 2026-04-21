"""
并行多源搜索工作流 - LangGraph实现示例

此实现展示了如何使用LangGraph创建一个并行从多个数据源搜索、
合并结果并生成摘要的工作流。
"""

import asyncio
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from datetime import datetime
import operator

# LangGraph导入
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver


# ==================== 状态定义 ====================

class WorkflowState(TypedDict):
    """工作流状态定义"""
    # 输入
    search_query: str

    # 并行搜索结果（使用operator.add自动合并）
    web_results: Annotated[List[Dict], operator.add]
    database_results: Annotated[List[Dict], operator.add]
    document_results: Annotated[List[Dict], operator.add]

    # 合并后的结果
    merged_results: List[Dict]
    source_breakdown: Dict[str, int]

    # 摘要
    summary: Optional[Dict]

    # 执行指标
    execution_metrics: Dict[str, Any]

    # 错误处理
    errors: Annotated[List[Dict], operator.add]


# ==================== 搜索节点实现 ====================

async def search_web(state: WorkflowState) -> Dict:
    """搜索网页节点"""
    start_time = datetime.now()

    try:
        # 模拟网页搜索（实际应调用真实API）
        await asyncio.sleep(1.5)  # 模拟网络延迟

        # 模拟搜索结果
        results = [
            {
                "url": f"https://example.com/web/{i}",
                "title": f"网页结果 {i}",
                "content": f"来自网页的内容 {i}",
                "relevance": 0.9 - (i * 0.05),
                "source": "web"
            }
            for i in range(1, 6)
        ]

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "web_results": results,
            "execution_metrics": {
                "web_search_time": elapsed,
                "web_result_count": len(results)
            }
        }

    except Exception as e:
        return {
            "errors": [{
                "source": "web",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }],
            "web_results": []  # 返回空列表以保持流程继续
        }


async def search_database(state: WorkflowState) -> Dict:
    """搜索数据库节点"""
    start_time = datetime.now()

    try:
        # 模拟数据库查询
        await asyncio.sleep(1.0)

        results = [
            {
                "id": f"db_{i}",
                "title": f"数据库记录 {i}",
                "content": f"来自数据库的内容 {i}",
                "relevance": 0.85 - (i * 0.04),
                "source": "database"
            }
            for i in range(1, 8)
        ]

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "database_results": results,
            "execution_metrics": {
                "database_search_time": elapsed,
                "database_result_count": len(results)
            }
        }

    except Exception as e:
        return {
            "errors": [{
                "source": "database",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }],
            "database_results": []
        }


async def search_documents(state: WorkflowState) -> Dict:
    """搜索文档库节点"""
    start_time = datetime.now()

    try:
        # 模拟文档库搜索（如Elasticsearch）
        await asyncio.sleep(1.2)

        results = [
            {
                "url": f"https://docs.example.com/doc/{i}",
                "title": f"文档 {i}",
                "content": f"来自文档库的内容 {i}",
                "relevance": 0.88 - (i * 0.045),
                "source": "documents"
            }
            for i in range(1, 10)
        ]

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "document_results": results,
            "execution_metrics": {
                "document_search_time": elapsed,
                "document_result_count": len(results)
            }
        }

    except Exception as e:
        return {
            "errors": [{
                "source": "documents",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }],
            "document_results": []
        }


# ==================== 合并节点实现 ====================

def merge_results(state: WorkflowState) -> Dict:
    """合并和去重结果节点"""

    # 1. 收集所有结果
    all_results = []
    all_results.extend(state.get("web_results", []))
    all_results.extend(state.get("database_results", []))
    all_results.extend(state.get("document_results", []))

    # 2. 去重（基于URL或ID）
    seen_identifiers = set()
    unique_results = []

    for result in all_results:
        # 优先使用URL，没有则用ID
        identifier = result.get("url") or result.get("id")

        if identifier and identifier not in seen_identifiers:
            seen_identifiers.add(identifier)
            unique_results.append(result)
        elif not identifier:
            # 没有标识符的结果也保留
            unique_results.append(result)

    # 3. 排序（按相关性降序）
    unique_results.sort(
        key=lambda x: x.get("relevance", 0),
        reverse=True
    )

    # 4. 限制数量
    max_results = 100
    final_results = unique_results[:max_results]

    # 5. 统计来源分布
    source_breakdown = {
        "web": len(state.get("web_results", [])),
        "database": len(state.get("database_results", [])),
        "documents": len(state.get("document_results", [])),
        "total_after_merge": len(final_results),
        "duplicates_removed": len(all_results) - len(final_results)
    }

    return {
        "merged_results": final_results,
        "source_breakdown": source_breakdown,
        "execution_metrics": {
            **state.get("execution_metrics", {}),
            "merge_time": 0.05,  # 合并操作很快
            "total_results_after_merge": len(final_results)
        }
    }


# ==================== 摘要生成节点实现 ====================

def generate_summary(state: WorkflowState) -> Dict:
    """生成摘要节点"""

    merged_results = state.get("merged_results", [])

    # 构建摘要内容
    summary = {
        "total_results": len(merged_results),
        "query": state.get("search_query", ""),
        "source_breakdown": state.get("source_breakdown", {}),
        "key_points": [],
        "top_results": []
    }

    # 提取关键点（基于高相关性结果）
    top_results = merged_results[:5]
    summary["top_results"] = [
        {
            "title": r.get("title"),
            "source": r.get("source"),
            "relevance": r.get("relevance")
        }
        for r in top_results
    ]

    # 生成关键点（简化版，实际应使用LLM）
    summary["key_points"] = [
        f"从{state['source_breakdown'].get('web', 0)}个网页来源找到相关内容",
        f"数据库查询返回{state['source_breakdown'].get('database', 0)}条记录",
        f"文档库检索到{state['source_breakdown'].get('documents', 0)}份相关文档",
        f"合并后共{len(merged_results)}条唯一结果",
        f"去重移除了{state['source_breakdown'].get('duplicates_removed', 0)}条重复内容"
    ]

    # 生成文本摘要
    summary_text = f"""
搜索摘要（基于查询：{state['search_query']}）

本次搜索从三个数据源并行检索信息：
• 网页搜索：{state['source_breakdown'].get('web', 0)} 条结果
• 数据库查询：{state['source_breakdown'].get('database', 0)} 条记录
• 文档库检索：{state['source_breakdown'].get('documents', 0)} 份文档

合并去重后共获得 {len(merged_results)} 条唯一结果。

最相关的结果包括：
"""

    for i, result in enumerate(top_results, 1):
        summary_text += f"\n{i}. {result.get('title')} (来源: {result.get('source')}, 相关性: {result.get('relevance', 0):.2f})"

    summary["summary_text"] = summary_text.strip()
    summary["generated_at"] = datetime.now().isoformat()

    return {"summary": summary}


# ==================== 格式化输出节点实现 ====================

def format_output(state: WorkflowState) -> Dict:
    """格式化输出节点"""

    output = {
        "query": state.get("search_query"),
        "summary": state.get("summary"),
        "detailed_results": state.get("merged_results", [])[:20],  # 只返回前20条
        "execution_metrics": state.get("execution_metrics", {}),
        "source_breakdown": state.get("source_breakdown", {}),
        "errors": state.get("errors", []) if state.get("errors") else None,
        "generated_at": datetime.now().isoformat()
    }

    return {"final_output": output}


# ==================== 工作流构建 ====================

def build_parallel_search_workflow():
    """构建并行多源搜索工作流"""

    # 创建状态图
    workflow = StateGraph(WorkflowState)

    # 添加节点
    workflow.add_node("search_web", search_web)
    workflow.add_node("search_database", search_database)
    workflow.add_node("search_documents", search_documents)
    workflow.add_node("merge_results", merge_results)
    workflow.add_node("generate_summary", generate_summary)
    workflow.add_node("format_output", format_output)

    # 设置入口点（并行执行三个搜索）
    workflow.set_entry_point("search_web")

    # 并行执行：三个搜索节点可以并发
    # 在实际LangGraph实现中，需要使用特定的并行模式
    workflow.add_edge("search_web", "merge_results")
    workflow.add_edge("search_database", "merge_results")
    workflow.add_edge("search_documents", "merge_results")

    # 顺序执行：合并 -> 摘要 -> 格式化
    workflow.add_edge("merge_results", "generate_summary")
    workflow.add_edge("generate_summary", "format_output")
    workflow.add_edge("format_output", END)

    # 编译工作流
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


# ==================== 并行执行包装器 ====================

async def execute_parallel_search(workflow, query: str) -> Dict:
    """
    执行并行搜索工作流

    实际实现中，LangGraph会自动处理并行执行。
    这里展示如何手动实现并行逻辑。
    """

    initial_state = {
        "search_query": query,
        "web_results": [],
        "database_results": [],
        "document_results": [],
        "merged_results": [],
        "summary": None,
        "execution_metrics": {},
        "errors": [],
        "source_breakdown": {}
    }

    # 并行执行三个搜索任务
    search_tasks = [
        search_web(initial_state),
        search_database(initial_state),
        search_documents(initial_state)
    ]

    # 使用asyncio.gather并行执行
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

    # 合并搜索结果到state
    for result in search_results:
        if isinstance(result, Exception):
            initial_state["errors"].append({
                "error": str(result),
                "timestamp": datetime.now().isoformat()
            })
        elif isinstance(result, dict):
            initial_state.update(result)

    # 顺序执行后续节点
    merge_result = merge_results(initial_state)
    initial_state.update(merge_result)

    summary_result = generate_summary(initial_state)
    initial_state.update(summary_result)

    output_result = format_output(initial_state)
    initial_state.update(output_result)

    return initial_state


# ==================== 使用示例 ====================

async def main():
    """主函数：演示工作流执行"""

    print("=" * 60)
    print("并行多源搜索工作流 - 执行示例")
    print("=" * 60)

    # 构建工作流
    workflow = build_parallel_search_workflow()

    # 执行搜索
    query = "LangGraph并行工作流设计"
    print(f"\n搜索查询: {query}\n")

    result = await execute_parallel_search(workflow, query)

    # 输出结果
    print("=" * 60)
    print("执行结果摘要")
    print("=" * 60)

    if result.get("summary"):
        summary = result["summary"]
        print(f"\n{summary.get('summary_text', '')}\n")

    print("=" * 60)
    print("来源分布")
    print("=" * 60)
    for source, count in result.get("source_breakdown", {}).items():
        print(f"  {source}: {count}")

    print("\n" + "=" * 60)
    print("执行指标")
    print("=" * 60)
    metrics = result.get("execution_metrics", {})
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    if result.get("errors"):
        print("\n" + "=" * 60)
        print("错误信息")
        print("=" * 60)
        for error in result["errors"]:
            print(f"  - {error}")

    print("\n" + "=" * 60)
    print("工作流执行完成")
    print("=" * 60)


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())
