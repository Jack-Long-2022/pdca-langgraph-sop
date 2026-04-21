"""示例2: 执行生成的 LangGraph 工作流

演示两种执行方式:
  A. 通过生成项目的 WorkflowRunner 执行（模板方式）
  B. 通过 LangGraph StateGraph 直接执行（原生方式）

使用方法:
    cd pdca-langgraph-sop
    python examples/demo_run_workflow.py

前置条件:
    先运行 demo_load_and_generate.py 生成工作流代码
"""

import sys
import json
from pathlib import Path
from typing import TypedDict, Annotated

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from pdca.plan.extractor import JSONLoader
from pdca.plan.config_generator import ConfigGenerator


# ============================================================
# 方式A: 手动构建 LangGraph StateGraph 并执行
# ============================================================

def run_with_langgraph():
    """使用 LangGraph StateGraph 直接构建和执行工作流"""
    from langgraph.graph import StateGraph, END

    # 1. 加载配置
    json_path = Path("config/extractions/wf_data_analysis.json")
    loader = JSONLoader()
    document = loader.load(json_path)

    generator = ConfigGenerator()
    config = generator.generate(document, workflow_name="自动化数据分析工作流")

    print("=" * 60)
    print("[方式A] LangGraph StateGraph 原生执行")
    print("=" * 60)

    # 2. 定义工作流状态 (基于 JSON 配置的 state_schema)
    #    这里用 TypedDict 定义所有状态字段
    state_fields = {}
    for s in config.state:
        type_map = {
            "string": str,
            "integer": int,
            "float": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        python_type = type_map.get(s.type, str)
        state_fields[s.field_name] = python_type

    # 动态创建状态类
    WorkflowState = TypedDict("WorkflowState", {
        "raw_sales_data": dict,
        "api_success": bool,
        "error_message": str,
        "cleaned_data": dict,
        "cleaning_log": list,
        "data_quality_score": float,
        "analysis_result": dict,
        "yoy_growth_rate": float,
        "key_insights": list,
        "report_path": str,
        "report_content": dict,
        "email_status": str,
        "retry_count": int,
        "should_retry": bool,
    })

    # 3. 定义节点处理函数
    def node_control_001_handler(state: dict) -> dict:
        """输入准备: 接收并验证输入参数"""
        print("  [输入准备] 初始化参数...")
        return {
            **state,
            "retry_count": 0,
            "api_success": False,
        }

    def node_tool_001_handler(state: dict) -> dict:
        """获取销售数据: 模拟API调用"""
        print("  [获取销售数据] 调用销售数据API...")
        retry_count = state.get("retry_count", 0)
        # 模拟: 第2次尝试成功
        success = retry_count >= 1
        if success:
            print(f"    API调用成功 (第{retry_count + 1}次)")
            return {
                **state,
                "raw_sales_data": {
                    "records": [
                        {"date": "2026-04-01", "amount": 15000, "product": "A"},
                        {"date": "2026-04-02", "amount": 22000, "product": "B"},
                        {"date": "2026-04-03", "amount": 18000, "product": "A"},
                        {"date": "2026-04-04", "amount": None, "product": "C"},
                    ]
                },
                "api_success": True,
                "error_message": "",
            }
        else:
            print(f"    API调用失败 (第{retry_count + 1}次)")
            return {
                **state,
                "raw_sales_data": {},
                "api_success": False,
                "error_message": "Connection timeout",
            }

    def node_control_002_handler(state: dict) -> dict:
        """API错误处理: 判断是否重试"""
        api_success = state.get("api_success", True)
        retry_count = state.get("retry_count", 0)
        max_retries = 3

        if not api_success and retry_count < max_retries:
            print(f"  [API错误处理] 将进行第{retry_count + 1}次重试...")
            return {
                **state,
                "should_retry": True,
                "retry_count": retry_count + 1,
            }
        else:
            print(f"  [API错误处理] {'成功,无需重试' if api_success else '已达到最大重试次数'}")
            return {
                **state,
                "should_retry": False,
            }

    def node_tool_002_handler(state: dict) -> dict:
        """数据清洗: 处理缺失值和异常值"""
        print("  [数据清洗] 清洗数据...")
        raw = state.get("raw_sales_data", {})
        records = raw.get("records", [])

        cleaning_log = []
        cleaned = []
        for r in records:
            if r.get("amount") is None:
                cleaning_log.append(f"缺失值: {r['date']} - {r['product']} amount为空, 填充均值")
                r = {**r, "amount": 18333}
            cleaned.append(r)

        return {
            **state,
            "cleaned_data": {"records": cleaned},
            "cleaning_log": cleaning_log,
            "data_quality_score": 92.5,
        }

    def node_thinking_001_handler(state: dict) -> dict:
        """销售趋势分析: 计算同比增长率"""
        print("  [趋势分析] 分析销售趋势...")
        cleaned = state.get("cleaned_data", {})
        records = cleaned.get("records", [])

        total = sum(r["amount"] for r in records)
        yoy_growth = 12.5

        return {
            **state,
            "analysis_result": {
                "total_sales": total,
                "trend": "上升",
                "period": "2026年4月",
            },
            "yoy_growth_rate": yoy_growth,
            "key_insights": [
                f"本月总销售额: {total}",
                f"同比增长率: {yoy_growth}%",
                "产品A销售占比最高",
            ],
        }

    def node_thinking_002_handler(state: dict) -> dict:
        """生成分析报告"""
        print("  [报告生成] 生成可视化报告...")
        return {
            **state,
            "report_path": "/tmp/sales_report_202604.html",
            "report_content": {
                "title": "2026年4月销售数据分析报告",
                "charts": ["趋势图", "产品占比图"],
                "sections": ["摘要", "详细分析", "建议"],
            },
        }

    def node_tool_003_handler(state: dict) -> dict:
        """邮件通知"""
        print("  [邮件通知] 发送报告邮件...")
        return {
            **state,
            "email_status": "sent",
        }

    def node_control_003_handler(state: dict) -> dict:
        """结果输出: 汇总结果"""
        print("  [结果输出] 汇总执行结果...")
        return {
            **state,
            "final_result": {
                "report_path": state.get("report_path"),
                "email_status": state.get("email_status"),
                "quality_score": state.get("data_quality_score"),
            },
        }

    # 4. 构建状态图
    graph = StateGraph(dict)

    # 添加节点
    graph.add_node("node_control_001", node_control_001_handler)
    graph.add_node("node_tool_001", node_tool_001_handler)
    graph.add_node("node_control_002", node_control_002_handler)
    graph.add_node("node_tool_002", node_tool_002_handler)
    graph.add_node("node_thinking_001", node_thinking_001_handler)
    graph.add_node("node_thinking_002", node_thinking_002_handler)
    graph.add_node("node_tool_003", node_tool_003_handler)
    graph.add_node("node_control_003", node_control_003_handler)

    # 设置入口点
    graph.set_entry_point("node_control_001")

    # 添加顺序边
    graph.add_edge("node_control_001", "node_tool_001")

    # 条件路由: API调用结果决定后续走向
    def route_api_result(state: dict) -> str:
        if state.get("api_success"):
            return "node_tool_002"
        return "node_control_002"

    graph.add_conditional_edges("node_tool_001", route_api_result)

    # 错误处理路由: 重试或终止
    def route_error_handler(state: dict) -> str:
        if state.get("should_retry"):
            return "node_tool_001"
        return "node_control_003"

    graph.add_conditional_edges("node_control_002", route_error_handler)

    # 后续顺序边
    graph.add_edge("node_tool_002", "node_thinking_001")
    graph.add_edge("node_thinking_001", "node_thinking_002")
    graph.add_edge("node_thinking_002", "node_tool_003")
    graph.add_edge("node_tool_003", "node_control_003")
    graph.add_edge("node_control_003", END)

    # 5. 编译并执行
    app = graph.compile()

    print("\n开始执行工作流...\n")
    result = app.invoke({
        "raw_sales_data": {},
        "retry_count": 0,
    })

    # 6. 打印结果
    print("\n" + "=" * 60)
    print("[执行结果]")
    print("=" * 60)
    print(f"  API调用成功:  {result.get('api_success')}")
    print(f"  重试次数:     {result.get('retry_count')}")
    print(f"  数据质量:     {result.get('data_quality_score')}")
    print(f"  同比增长:     {result.get('yoy_growth_rate')}%")
    print(f"  报告路径:     {result.get('report_path')}")
    print(f"  邮件状态:     {result.get('email_status')}")

    if result.get("cleaning_log"):
        print(f"  清洗日志:")
        for log in result["cleaning_log"]:
            print(f"    - {log}")

    if result.get("key_insights"):
        print(f"  关键洞察:")
        for insight in result["key_insights"]:
            print(f"    - {insight}")

    return result


# ============================================================
# 方式B: 通过生成的项目代码执行 (需要先运行生成脚本)
# ============================================================

def run_with_generated_project():
    """通过生成的项目 main.py 执行工作流"""
    print("\n" + "=" * 60)
    print("[方式B] 通过生成的项目执行")
    print("=" * 60)
    print()
    print("  执行命令:")
    print("    cd examples/demo_output")
    print("    python main.py --input input.txt --output output.txt")
    print()
    print("  或直接用 run_pdca.py 完整PDCA循环:")
    print("    python run_pdca.py --input examples/input.md --output examples/output")
    print()


if __name__ == "__main__":
    # 执行方式A
    result = run_with_langgraph()

    # 说明方式B
    run_with_generated_project()

    print("\n[完成] 两种执行方式均已演示")
