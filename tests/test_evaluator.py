"""测试验收测试模块"""

import pytest
from unittest.mock import MagicMock, patch
from pdca.check.evaluator import (
    TestStatus,
    TestCase,
    TestResult,
    EvaluationReport,
    CriteriaGenerator,
    TestCaseGenerator,
    TestExecutor,
    EvaluationReportGenerator,
    run_evaluation
)


class TestCriteriaGenerator:
    """CriteriaGenerator测试"""
    
    def test_generate_criteria(self):
        """测试生成验收标准"""
        generator = CriteriaGenerator()
        
        criteria = generator.generate_criteria(
            workflow_description="测试工作流",
            node_count=5
        )
        
        assert "functional" in criteria
        assert "quality" in criteria
        assert "performance" in criteria
        assert "error_handling" in criteria
        
        assert len(criteria["functional"]) > 0
        assert len(criteria["performance"]) > 0
    
    def test_generate_criteria_large_workflow(self):
        """测试大工作流的验收标准"""
        generator = CriteriaGenerator()
        
        criteria = generator.generate_criteria(
            workflow_description="复杂工作流",
            node_count=15
        )
        
        # 应该包含额外的性能标准
        assert any("120秒" in p for p in criteria["performance"])


class TestTestCaseGenerator:
    """TestCaseGenerator测试"""
    
    def test_generate_normal_cases(self):
        """测试生成正常场景用例"""
        generator = TestCaseGenerator()
        
        cases = generator.generate_normal_cases(
            workflow_description="测试工作流",
            node_count=3
        )
        
        assert len(cases) >= 2
        assert all(c.category == "functional" for c in cases)
    
    def test_generate_edge_cases(self):
        """测试生成边界场景用例"""
        generator = TestCaseGenerator()
        
        cases = generator.generate_edge_cases("测试工作流")
        
        assert len(cases) >= 3
        assert all(c.category == "edge_case" for c in cases)
        
        # 检查特殊用例 - 检查描述而不是case_id
        case_descriptions = [c.description for c in cases]
        assert any("空输入" in desc for desc in case_descriptions)
        assert any("最大" in desc for desc in case_descriptions)
    
    def test_generate_error_cases(self):
        """测试生成异常场景用例"""
        generator = TestCaseGenerator()
        
        cases = generator.generate_error_cases("测试工作流")
        
        assert len(cases) >= 2
        assert any(c.case_id.startswith("error") for c in cases)
    
    def test_generate_all_cases(self):
        """测试生成所有用例"""
        generator = TestCaseGenerator()
        
        cases = generator.generate_all_cases(
            workflow_description="测试工作流",
            node_count=5
        )
        
        assert len(cases) >= 7  # 至少3个正常 + 3个边界 + 2个异常
        
        # 检查用例分类
        categories = set(c.category for c in cases)
        assert "functional" in categories
        assert "edge_case" in categories


class TestTestExecutor:
    """TestExecutor测试"""
    
    def test_execute_case_success(self):
        """测试执行成功"""
        executor = TestExecutor()
        
        test_case = TestCase(
            case_id="test_001",
            name="成功测试",
            inputs={}
        )
        
        # 模拟工作流运行器
        runner = MagicMock()
        runner.run.return_value = {"success": True, "outputs": {}}
        
        result = executor.execute_case(test_case, runner)
        
        assert result.case_id == "test_001"
        assert result.status == TestStatus.PASSED
        assert result.execution_time >= 0
    
    def test_execute_case_failure(self):
        """测试执行失败"""
        executor = TestExecutor()
        
        test_case = TestCase(
            case_id="test_002",
            name="失败测试",
            expected_outputs={"success": False}
        )
        
        runner = MagicMock()
        runner.run.return_value = {"success": False, "error": "测试错误"}
        
        result = executor.execute_case(test_case, runner)
        
        assert result.status == TestStatus.PASSED  # 期望失败，实际失败 = 通过
    
    def test_execute_case_exception(self):
        """测试执行异常"""
        executor = TestExecutor()
        
        test_case = TestCase(
            case_id="test_003",
            name="异常测试"
        )
        
        runner = MagicMock()
        runner.run.side_effect = RuntimeError("测试异常")
        
        result = executor.execute_case(test_case, runner)
        
        assert result.status == TestStatus.ERROR
        assert "测试异常" in result.error_message
    
    def test_execute_all(self):
        """测试执行所有用例"""
        executor = TestExecutor()
        
        cases = [
            TestCase(case_id="t1", name="测试1"),
            TestCase(case_id="t2", name="测试2"),
            TestCase(case_id="t3", name="测试3")
        ]
        
        runner = MagicMock()
        runner.run.return_value = {"success": True, "outputs": {}}
        
        results = executor.execute_all(cases, runner)
        
        assert len(results) == 3
        assert all(r.status == TestStatus.PASSED for r in results)


class TestEvaluationReportGenerator:
    """EvaluationReportGenerator测试"""
    
    def test_generate_report_all_passed(self):
        """测试全通过报告"""
        generator = EvaluationReportGenerator()
        
        test_cases = [
            TestCase(case_id="t1", name="测试1"),
            TestCase(case_id="t2", name="测试2")
        ]
        
        test_results = [
            TestResult(case_id="t1", status=TestStatus.PASSED, execution_time=0.1),
            TestResult(case_id="t2", status=TestStatus.PASSED, execution_time=0.2)
        ]
        
        report = generator.generate("测试工作流", test_results, test_cases)
        
        assert report.workflow_name == "测试工作流"
        assert report.total_cases == 2
        assert report.passed == 2
        assert report.failed == 0
        assert report.pass_rate == 100.0
    
    def test_generate_report_with_failures(self):
        """测试有失败的报告"""
        generator = EvaluationReportGenerator()
        
        test_cases = [
            TestCase(case_id="t1", name="测试1"),
            TestCase(case_id="t2", name="测试2")
        ]
        
        test_results = [
            TestResult(case_id="t1", status=TestStatus.PASSED, execution_time=0.1),
            TestResult(case_id="t2", status=TestStatus.FAILED, error_message="错误")
        ]
        
        report = generator.generate("测试工作流", test_results, test_cases)
        
        assert report.passed == 1
        assert report.failed == 1
        assert report.pass_rate == 50.0
        assert len(report.issues) > 0
    
    def test_generate_report_analyzes_issues(self):
        """测试问题分析"""
        generator = EvaluationReportGenerator()
        
        test_cases = [
            TestCase(case_id="t1", name="测试1"),
            TestCase(case_id="t2", name="测试2")
        ]
        
        test_results = [
            TestResult(case_id="t1", status=TestStatus.FAILED, error_message="验证失败"),
            TestResult(case_id="t2", status=TestStatus.ERROR, error_message="空指针异常")
        ]
        
        report = generator.generate("测试工作流", test_results, test_cases)
        
        assert len(report.issues) == 2
        assert any("验证失败" in issue for issue in report.issues)
    
    def test_generate_report_suggests_improvements(self):
        """测试改进建议"""
        generator = EvaluationReportGenerator()
        
        test_cases = [
            TestCase(case_id="t1", name="测试1"),
            TestCase(case_id="t2", name="测试2", timeout=1.0)
        ]
        
        test_results = [
            TestResult(case_id="t1", status=TestStatus.FAILED, error_message="失败"),
            TestResult(case_id="t2", status=TestStatus.PASSED, execution_time=35.0)
        ]
        
        report = generator.generate("测试工作流", test_results, test_cases)
        
        assert len(report.suggestions) > 0


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_run_evaluation(self):
        """测试完整评估流程"""
        runner = MagicMock()
        runner.run.return_value = {"success": True, "outputs": {}}
        
        report = run_evaluation(
            workflow_name="测试工作流",
            workflow_description="测试描述",
            node_count=3,
            workflow_runner=runner
        )
        
        assert isinstance(report, EvaluationReport)
        assert report.workflow_name == "测试工作流"
        assert report.total_cases > 0


class TestDataModels:
    """数据模型测试"""
    
    def test_test_case_model(self):
        """测试TestCase模型"""
        case = TestCase(
            case_id="test_001",
            name="测试用例",
            description="描述",
            category="functional",
            inputs={"key": "value"},
            expected_outputs={"result": "expected"},
            timeout=10.0,
            tags=["tag1", "tag2"]
        )
        
        assert case.case_id == "test_001"
        assert case.name == "测试用例"
        assert case.inputs["key"] == "value"
    
    def test_test_result_model(self):
        """测试TestResult模型"""
        result = TestResult(
            case_id="test_001",
            status=TestStatus.PASSED,
            execution_time=1.5,
            actual_outputs={"output": "value"},
            error_message="",
            timestamp="2026-04-20T00:00:00Z"
        )
        
        assert result.status == TestStatus.PASSED
        assert result.execution_time == 1.5
    
    def test_evaluation_report_model(self):
        """测试EvaluationReport模型"""
        report = EvaluationReport(
            workflow_name="测试工作流",
            total_cases=10,
            passed=8,
            failed=1,
            skipped=1,
            errors=0,
            pass_rate=80.0,
            execution_time=5.5
        )
        
        assert report.total_cases == 10
        assert report.pass_rate == 80.0
