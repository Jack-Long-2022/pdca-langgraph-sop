"""
条件重试工作流的Python实现示例
实现自动化的数据搜索、分析和报告生成流程
"""

import time
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """工作流状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WorkflowState:
    """工作流状态管理"""
    search_success: bool = False
    retry_count: int = 0
    max_retries: int = 3
    search_results: List[Dict] = field(default_factory=list)
    analysis_results: Optional[Dict] = None
    report: Optional[Dict] = None
    errors: List[str] = field(default_factory=list)
    execution_log: List[Dict] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "search_success": self.search_success,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "search_results": self.search_results,
            "analysis_results": self.analysis_results,
            "report": self.report,
            "errors": self.errors,
            "execution_log": self.execution_log,
            "status": self.status.value
        }


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    initial_delay: int = 1000  # 毫秒
    max_delay: int = 10000
    backoff_multiplier: float = 2.0
    retry_on_errors: List[str] = field(default_factory=lambda: [
        "network_error", "timeout", "rate_limit"
    ])
    retry_on_conditions: List[str] = field(default_factory=lambda: [
        "result_count == 0",
        "result.quality_score < 0.5"
    ])


class ConditionalRetryWorkflow:
    """条件重试工作流主类"""

    def __init__(self, retry_config: Optional[RetryConfig] = None):
        self.retry_config = retry_config or RetryConfig()
        self.state = WorkflowState()

    def calculate_retry_delay(self, retry_count: int) -> int:
        """
        计算重试延迟（指数退避策略）
        delay = min(initial_delay * (backoff_multiplier ^ retry_count), max_delay)
        """
        delay = self.retry_config.initial_delay * (
            self.retry_config.backoff_multiplier ** retry_count
        )
        return min(int(delay), self.retry_config.max_delay)

    def should_retry(self, error: Optional[str] = None,
                    condition_check: Optional[bool] = None) -> bool:
        """
        判断是否应该重试
        """
        if self.state.retry_count >= self.retry_config.max_retries:
            return False

        if error and error in self.retry_config.retry_on_errors:
            return True

        if condition_check is not None:
            return condition_check

        return False

    def log_execution(self, action: str, details: Dict[str, Any]):
        """记录执行日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "retry_count": self.state.retry_count
        }
        self.state.execution_log.append(log_entry)
        logger.info(f"执行日志: {action} - {details}")

    def search_data(self, query: str) -> Dict[str, Any]:
        """
        搜索数据（模拟实现）
        在实际应用中，这里会调用真实的搜索API
        """
        self.state.status = WorkflowStatus.RUNNING

        try:
            self.log_execution("search_data", {"query": query})

            # 模拟搜索操作
            # 这里替换为实际的搜索逻辑
            mock_results = self._mock_search_api(query)

            # 检查搜索结果
            result_count = len(mock_results.get("results", []))
            quality_score = mock_results.get("quality_score", 0.0)

            # 判断搜索是否成功
            if result_count > 0 and quality_score >= 0.5:
                self.state.search_success = True
                self.state.search_results = mock_results["results"]
                self.log_execution("search_success", {
                    "result_count": result_count,
                    "quality_score": quality_score
                })
            else:
                self.state.search_success = False
                self.log_execution("search_failed", {
                    "result_count": result_count,
                    "quality_score": quality_score
                })

            return {
                "success": self.state.search_success,
                "results": mock_results,
                "should_retry": not self.state.search_success
            }

        except Exception as e:
            error_msg = f"搜索错误: {str(e)}"
            self.state.errors.append(error_msg)
            self.log_execution("search_error", {"error": error_msg})

            return {
                "success": False,
                "error": error_msg,
                "error_type": "network_error",
                "should_retry": self.should_retry(error="network_error")
            }

    def _mock_search_api(self, query: str) -> Dict[str, Any]:
        """模拟搜索API（实际应用中替换为真实API）"""
        # 这里模拟不同的搜索结果用于测试
        # 在实际应用中，替换为真实的API调用

        import random

        # 模拟有时成功，有时失败
        if random.random() < 0.3:  # 30% 概率失败
            return {
                "results": [],
                "quality_score": 0.0
            }

        # 模拟成功返回数据
        return {
            "results": [
                {"id": 1, "title": f"结果1 - {query}", "score": 0.8},
                {"id": 2, "title": f"结果2 - {query}", "score": 0.9},
                {"id": 3, "title": f"结果3 - {query}", "score": 0.7}
            ],
            "quality_score": 0.8
        }

    def analyze_results(self) -> Dict[str, Any]:
        """分析搜索结果"""
        self.log_execution("analyze_results", {
            "result_count": len(self.state.search_results)
        })

        try:
            # 实际分析逻辑
            analysis = {
                "total_results": len(self.state.search_results),
                "average_score": sum(
                    r.get("score", 0) for r in self.state.search_results
                ) / len(self.state.search_results) if self.state.search_results else 0,
                "top_results": sorted(
                    self.state.search_results,
                    key=lambda x: x.get("score", 0),
                    reverse=True
                )[:5],
                "categories": self._categorize_results(self.state.search_results),
                "timestamp": datetime.now().isoformat()
            }

            self.state.analysis_results = analysis
            return {"success": True, "analysis": analysis}

        except Exception as e:
            error_msg = f"分析错误: {str(e)}"
            self.state.errors.append(error_msg)
            self.log_execution("analysis_error", {"error": error_msg})

            return {
                "success": False,
                "error": error_msg
            }

    def _categorize_results(self, results: List[Dict]) -> Dict[str, int]:
        """对结果进行分类"""
        categories = {}
        for result in results:
            category = result.get("category", "uncategorized")
            categories[category] = categories.get(category, 0) + 1
        return categories

    def generate_report(self) -> Dict[str, Any]:
        """生成最终报告"""
        self.log_execution("generate_report", {})

        report = {
            "timestamp": datetime.now().isoformat(),
            "status": "success" if self.state.search_success else "failed",
            "retry_count": self.state.retry_count,
            "max_retries": self.state.max_retries,
            "search_results_count": len(self.state.search_results),
            "analysis_results": self.state.analysis_results,
            "errors": self.state.errors,
            "execution_log": self.state.execution_log,
            "summary": {
                "total_execution_time": self._calculate_total_time(),
                "success_rate": 1.0 if self.state.search_success else 0.0,
                "retry_success": self.state.retry_count > 0 and self.state.search_success
            }
        }

        self.state.report = report
        return report

    def _calculate_total_time(self) -> float:
        """计算总执行时间"""
        if len(self.state.execution_log) < 2:
            return 0.0

        start_time = datetime.fromisoformat(self.state.execution_log[0]["timestamp"])
        end_time = datetime.fromisoformat(self.state.execution_log[-1]["timestamp"])
        return (end_time - start_time).total_seconds()

    def handle_failure(self) -> Dict[str, Any]:
        """处理最终失败"""
        self.state.status = WorkflowStatus.FAILED
        self.log_execution("handle_failure", {
            "total_retries": self.state.retry_count,
            "errors": self.state.errors
        })

        return {
            "success": False,
            "message": "工作流执行失败，已达到最大重试次数",
            "retry_count": self.state.retry_count,
            "errors": self.state.errors
        }

    def execute(self, query: str) -> Dict[str, Any]:
        """
        执行完整的工作流
        """
        logger.info(f"开始执行工作流，查询: {query}")
        self.state.status = WorkflowStatus.RUNNING

        # 搜索阶段（带重试）
        while True:
            search_result = self.search_data(query)

            if search_result["success"]:
                # 搜索成功，继续分析
                break
            elif search_result.get("should_retry"):
                # 需要重试
                self.state.retry_count += 1
                self.state.status = WorkflowStatus.RETRYING

                if self.state.retry_count >= self.retry_config.max_retries:
                    # 达到最大重试次数，处理失败
                    return self.handle_failure()

                # 计算并执行延迟
                delay = self.calculate_retry_delay(self.state.retry_count)
                logger.info(f"第 {self.state.retry_count} 次重试，等待 {delay}ms")
                time.sleep(delay / 1000)
            else:
                # 不可重试的错误
                return self.handle_failure()

        # 分析阶段
        analysis_result = self.analyze_results()
        if not analysis_result["success"]:
            logger.warning("分析阶段出错，但继续生成报告")

        # 生成报告
        report = self.generate_report()
        self.state.status = WorkflowStatus.SUCCESS

        logger.info("工作流执行成功")
        return {
            "success": True,
            "report": report,
            "state": self.state.to_dict()
        }


# 使用示例
def main():
    """主函数示例"""
    # 创建工作流实例
    workflow = ConditionalRetryWorkflow(
        retry_config=RetryConfig(
            max_retries=3,
            initial_delay=1000,
            backoff_multiplier=2.0
        )
    )

    # 执行工作流
    result = workflow.execute("示例查询数据")

    # 输出结果
    print("\n" + "="*50)
    print("工作流执行结果:")
    print("="*50)
    print(f"状态: {'成功' if result['success'] else '失败'}")
    print(f"重试次数: {result['state']['retry_count']}")

    if result['success']:
        print("\n报告摘要:")
        print(f"- 搜索结果数: {result['report']['search_results_count']}")
        print(f"- 执行时间: {result['report']['summary']['total_execution_time']:.2f}秒")
        print(f"- 重试成功: {result['report']['summary']['retry_success']}")

        if result['report']['analysis_results']:
            analysis = result['report']['analysis_results']
            print(f"\n分析结果:")
            print(f"- 平均分数: {analysis['average_score']:.2f}")
            print(f"- 分类: {analysis['categories']}")
    else:
        print("\n错误信息:")
        for error in result['state']['errors']:
            print(f"- {error}")

    # 保存完整报告到文件
    output_file = "workflow_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result['report'], f, ensure_ascii=False, indent=2)
    print(f"\n完整报告已保存到: {output_file}")


if __name__ == "__main__":
    main()
