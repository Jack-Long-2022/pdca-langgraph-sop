"""验收测试模块 (Check阶段)

负责验收标准生成、测试用例生成和测试执行。
使用单次LLM调用完成标准+用例生成（原2次合并为1次）。
"""

import time
from datetime import datetime
from typing import Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
from pdca.core.logger import get_logger
from pdca.core.llm import OpenAILLM, get_llm_for_task
from pdca.core.utils import parse_json_response
from pdca.core.prompts import SYSTEM_PROMPTS, TEST_PROMPT, REPORT_PROMPT

logger = get_logger(__name__)


# ============== 测试结果模型 ==============

class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestCase(BaseModel):
    case_id: str = Field(..., description="用例ID")
    name: str = Field(..., description="用例名称")
    description: str = Field(default="", description="用例描述")
    category: str = Field(default="functional", description="分类")
    inputs: dict[str, Any] = Field(default_factory=dict, description="输入数据")
    expected_outputs: dict[str, Any] = Field(default_factory=dict, description="预期输出")
    validation_logic: str = Field(default="", description="验证逻辑代码")
    timeout: float = Field(default=30.0, description="超时时间(秒)")
    tags: list[str] = Field(default_factory=list, description="标签")


class TestResult(BaseModel):
    case_id: str = Field(..., description="用例ID")
    status: TestStatus = Field(..., description="测试状态")
    execution_time: float = Field(default=0.0, description="执行时间(秒)")
    actual_outputs: dict[str, Any] = Field(default_factory=dict, description="实际输出")
    error_message: str = Field(default="", description="错误信息")
    timestamp: str = Field(default="", description="执行时间戳")


class EvaluationReport(BaseModel):
    workflow_name: str = Field(..., description="工作流名称")
    total_cases: int = Field(default=0, description="总用例数")
    passed: int = Field(default=0, description="通过数")
    failed: int = Field(default=0, description="失败数")
    skipped: int = Field(default=0, description="跳过数")
    errors: int = Field(default=0, description="错误数")
    pass_rate: float = Field(default=0.0, description="通过率")
    execution_time: float = Field(default=0.0, description="总执行时间")
    test_results: list[TestResult] = Field(default_factory=list, description="测试结果列表")
    issues: list[str] = Field(default_factory=list, description="问题列表")
    suggestions: list[str] = Field(default_factory=list, description="改进建议")


# ============== 测试生成器（单次LLM调用） ==============

class TestGenerator:
    """测试生成器 — 单次LLM调用完成验收标准+测试用例"""

    def __init__(self, llm: Optional[OpenAILLM] = None):
        self.llm = llm

    def generate(self, workflow_description: str, nodes: list[dict],
                 edges: list[dict]) -> tuple[list[dict], list[TestCase]]:
        """生成验收标准和测试用例

        Returns:
            (criteria_dict, test_cases)
        """
        if self.llm is None:
            return self._fallback_generate(workflow_description, len(nodes))

        nodes_info = "\n".join([f"- {n.get('name', '未知')} ({n.get('type', 'unknown')})" for n in nodes])
        edges_info = "\n".join([f"- {e.get('source')} -> {e.get('target')}" for e in edges])

        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["test"]},
            {"role": "user", "content": TEST_PROMPT.format(
                workflow_description=workflow_description,
                nodes=nodes_info, edges=edges_info,
            )},
        ]

        try:
            response = self.llm.generate_messages(messages)
            data = parse_json_response(response)
            if data:
                return self._parse_response(data)
        except Exception as e:
            logger.warning("llm_test_generation_failed", error=str(e))

        return self._fallback_generate(workflow_description, len(nodes))

    def _parse_response(self, data: dict) -> tuple[list[dict], list[TestCase]]:
        criteria = data.get("criteria", [])
        cases = []
        for cd in data.get("test_cases", []):
            cases.append(TestCase(
                case_id=cd.get("case_id", f"test_{len(cases)}"),
                name=cd.get("name", "未命名测试"),
                description=cd.get("description", ""),
                category=cd.get("category", "functional"),
                inputs=cd.get("inputs", {}),
                expected_outputs=cd.get("expected_outputs", {}),
                tags=cd.get("tags", []),
            ))
        return criteria, cases

    def _fallback_generate(self, workflow_description: str, node_count: int) -> tuple[list[dict], list[TestCase]]:
        criteria = [
            {"id": "func_1", "category": "functional", "description": "工作流能够正常启动和结束", "priority": "high"},
            {"id": "func_2", "category": "functional", "description": "所有节点按正确顺序执行", "priority": "high"},
            {"id": "qual_1", "category": "quality", "description": "输出结果完整性", "priority": "medium"},
            {"id": "perf_1", "category": "performance", "description": "工作流总执行时间 < 60秒", "priority": "medium"},
            {"id": "err_1", "category": "error_handling", "description": "无效输入有明确错误提示", "priority": "medium"},
        ]
        cases = [
            TestCase(case_id="normal_001", name="基本执行测试", category="functional",
                     inputs={}, expected_outputs={"success": True}, tags=["basic", "smoke"]),
            TestCase(case_id="normal_002", name="带输入执行测试", category="functional",
                     inputs={"input_text": "测试输入"}, expected_outputs={"success": True}, tags=["input"]),
            TestCase(case_id="edge_001", name="空输入测试", category="edge_case",
                     inputs={"input_text": ""}, expected_outputs={"success": True}, tags=["edge", "empty"]),
            TestCase(case_id="edge_002", name="最大输入测试", category="edge_case",
                     inputs={"input_text": "x" * 10000}, expected_outputs={"success": True}, tags=["edge", "max"]),
            TestCase(case_id="error_001", name="无效输入测试", category="error",
                     inputs={"invalid_param": True}, expected_outputs={"success": False}, tags=["error"]),
        ]
        return criteria, cases


# 向后兼容别名
CriteriaGenerator = TestGenerator
TestCaseGenerator = TestGenerator


# ============== 测试执行器 ==============

class TestExecutor:
    """测试执行器"""

    def __init__(self):
        self.results: list[TestResult] = []

    def execute_case(self, test_case: TestCase, workflow_runner: Any) -> TestResult:
        logger.debug("executing_test_case", case_id=test_case.case_id)
        start_time = time.time()

        try:
            result = workflow_runner.run(input_data=test_case.inputs, timeout=test_case.timeout)
            execution_time = time.time() - start_time
            status = self._validate_result(test_case, result)
            return TestResult(
                case_id=test_case.case_id, status=status,
                execution_time=execution_time,
                actual_outputs=result.get("outputs", {}),
                error_message=result.get("error", ""),
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
        except Exception as e:
            return TestResult(
                case_id=test_case.case_id, status=TestStatus.ERROR,
                execution_time=time.time() - start_time,
                error_message=str(e),
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

    def execute_all(self, test_cases: list[TestCase], workflow_runner: Any) -> list[TestResult]:
        logger.info("executing_all_test_cases", count=len(test_cases))
        self.results = [self.execute_case(case, workflow_runner) for case in test_cases]
        return self.results

    def _validate_result(self, test_case: TestCase, result: dict) -> TestStatus:
        if not result.get("success", False):
            if test_case.expected_outputs.get("success") is False:
                return TestStatus.PASSED
            return TestStatus.FAILED
        if result.get("error") and test_case.expected_outputs.get("success") is not False:
            return TestStatus.FAILED
        return TestStatus.PASSED


# ============== 评估报告生成器 ==============

class EvaluationReportGenerator:
    """评估报告生成器 — 单次LLM调用"""

    def __init__(self, llm: Optional[OpenAILLM] = None):
        self.llm = llm

    def generate(self, workflow_name: str, test_results: list[TestResult],
                 test_cases: list[TestCase], workflow_description: str = "",
                 nodes: list[dict] = None) -> EvaluationReport:
        logger.info("generating_evaluation_report", workflow=workflow_name, result_count=len(test_results))

        passed = sum(1 for r in test_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in test_results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in test_results if r.status == TestStatus.SKIPPED)
        errors = sum(1 for r in test_results if r.status == TestStatus.ERROR)
        total = len(test_results)
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        total_time = sum(r.execution_time for r in test_results)

        if self.llm is None:
            return self._fallback_report(workflow_name, total, passed, failed,
                                         skipped, errors, pass_rate, total_time, test_results)

        test_details = [f"- {c.name}: {r.status.value} ({r.execution_time:.2f}s)"
                        for r, c in zip(test_results, test_cases)]

        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["report"]},
            {"role": "user", "content": REPORT_PROMPT.format(
                workflow_name=workflow_name, test_results="\n".join(test_details),
            )},
        ]

        try:
            response = self.llm.generate_messages(messages)
            data = parse_json_response(response)
            if data:
                issues = [f"[{i.get('severity', 'medium')}] {i.get('description', '')}"
                          for i in data.get("issues", [])]
                suggestions = [f"[{s.get('priority', 'medium')}] {s.get('action', '')}"
                               for s in data.get("suggestions", [])]
                return EvaluationReport(
                    workflow_name=workflow_name, total_cases=total,
                    passed=passed, failed=failed, skipped=skipped, errors=errors,
                    pass_rate=pass_rate, execution_time=total_time,
                    test_results=test_results, issues=issues, suggestions=suggestions,
                )
        except Exception as e:
            logger.warning("llm_report_failed", error=str(e))

        return self._fallback_report(workflow_name, total, passed, failed,
                                     skipped, errors, pass_rate, total_time, test_results)

    def _fallback_report(self, workflow_name, total, passed, failed,
                         skipped, errors, pass_rate, total_time, test_results):
        issues = [f"用例 {r.case_id} 执行失败: {r.error_message}"
                  for r in test_results if r.status in (TestStatus.FAILED, TestStatus.ERROR)]
        suggestions = []
        if failed > 0:
            suggestions.append("检查失败用例的预期输出是否合理")
        if errors > 0:
            suggestions.append("修复导致测试错误的异常情况")
        if not issues:
            suggestions.append("所有测试通过，工作流质量良好")

        return EvaluationReport(
            workflow_name=workflow_name, total_cases=total,
            passed=passed, failed=failed, skipped=skipped, errors=errors,
            pass_rate=pass_rate, execution_time=total_time,
            test_results=test_results, issues=issues, suggestions=suggestions,
        )


# ============== 便捷函数 ==============

def run_evaluation(
    workflow_name: str,
    workflow_description: str,
    node_count: int,
    workflow_runner: Any,
    llm: Optional[OpenAILLM] = None,
    nodes: list[dict] = None,
) -> EvaluationReport:
    """运行完整评估流程"""
    nodes = nodes or []
    edges = []  # 简化：不传edges

    # 1. 生成验收标准+测试用例（单次LLM调用）
    test_gen = TestGenerator(llm)
    criteria, test_cases = test_gen.generate(workflow_description, nodes, edges)
    logger.info("test_cases_generated", count=len(test_cases))

    # 2. 执行测试
    executor = TestExecutor()
    results = executor.execute_all(test_cases, workflow_runner)

    # 3. 生成报告
    report_gen = EvaluationReportGenerator(llm)
    return report_gen.generate(workflow_name, results, test_cases, workflow_description, nodes)
