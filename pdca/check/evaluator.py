"""验收测试模块 (Check阶段)

负责验收标准生成、测试用例生成和测试执行
"""

import time
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field
from pdca.core.logger import get_logger

logger = get_logger(__name__)


# ============== 测试结果模型 ==============

class TestStatus(str, Enum):
    """测试状态"""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestCase(BaseModel):
    """测试用例"""
    case_id: str = Field(..., description="用例ID")
    name: str = Field(..., description="用例名称")
    description: str = Field(default="", description="用例描述")
    category: str = Field(default="functional", description="分类: functional/performance/edge_case")
    inputs: dict[str, Any] = Field(default_factory=dict, description="输入数据")
    expected_outputs: dict[str, Any] = Field(default_factory=dict, description="预期输出")
    validation_logic: str = Field(default="", description="验证逻辑代码")
    timeout: float = Field(default=30.0, description="超时时间(秒)")
    tags: list[str] = Field(default_factory=list, description="标签")


class TestResult(BaseModel):
    """测试结果"""
    case_id: str = Field(..., description="用例ID")
    status: TestStatus = Field(..., description="测试状态")
    execution_time: float = Field(default=0.0, description="执行时间(秒)")
    actual_outputs: dict[str, Any] = Field(default_factory=dict, description="实际输出")
    error_message: str = Field(default="", description="错误信息")
    timestamp: str = Field(default="", description="执行时间戳")


class EvaluationReport(BaseModel):
    """评估报告"""
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


# ============== 验收标准生成器 ==============

class CriteriaGenerator:
    """验收标准生成器"""
    
    # 功能正确性标准
    FUNCTIONAL_CRITERIA = [
        "工作流能够正常启动和结束",
        "所有节点按正确的顺序执行",
        "节点间的数据传递正确",
        "输入输出格式符合预期",
    ]
    
    # 输出质量标准
    QUALITY_CRITERIA = [
        "输出结果完整性",
        "输出格式一致性",
        "错误处理合理性",
    ]
    
    # 性能指标
    PERFORMANCE_CRITERIA = [
        "单个节点执行时间 < 5秒",
        "工作流总执行时间 < 60秒",
        "内存使用合理",
    ]
    
    # 异常处理标准
    ERROR_HANDLING_CRITERIA = [
        "无效输入有明确错误提示",
        "网络异常能够捕获和处理",
        "关键步骤失败时有回退机制",
    ]
    
    def generate_criteria(
        self,
        workflow_description: str,
        node_count: int
    ) -> dict[str, list[str]]:
        """生成验收标准
        
        Args:
            workflow_description: 工作流描述
            node_count: 节点数量
        
        Returns:
            分类的验收标准
        """
        logger.info("generating_criteria", 
                   workflow=workflow_description,
                   node_count=node_count)
        
        criteria = {
            "functional": self.FUNCTIONAL_CRITERIA.copy(),
            "quality": self.QUALITY_CRITERIA.copy(),
            "performance": self.PERFORMANCE_CRITERIA.copy(),
            "error_handling": self.ERROR_HANDLING_CRITERIA.copy()
        }
        
        # 根据节点数量调整性能标准
        if node_count > 10:
            criteria["performance"].append("工作流总执行时间 < 120秒")
        
        return criteria


# ============== 测试用例生成器 ==============

class TestCaseGenerator:
    """测试用例生成器"""
    
    def __init__(self, criteria_generator: CriteriaGenerator = None):
        self.criteria_generator = criteria_generator or CriteriaGenerator()
    
    def generate_normal_cases(
        self,
        workflow_description: str,
        node_count: int
    ) -> list[TestCase]:
        """生成正常场景测试用例
        
        Args:
            workflow_description: 工作流描述
            node_count: 节点数量
        
        Returns:
            测试用例列表
        """
        cases = []
        
        # 基本执行测试
        cases.append(TestCase(
            case_id="normal_001",
            name="基本执行测试",
            description="验证工作流能够正常执行完成",
            category="functional",
            inputs={},
            expected_outputs={"success": True},
            tags=["basic", "smoke"]
        ))
        
        # 带输入的执行测试
        cases.append(TestCase(
            case_id="normal_002",
            name="带输入的执行测试",
            description="验证带输入数据时工作流正常执行",
            category="functional",
            inputs={"input_text": "测试输入数据"},
            expected_outputs={"success": True, "has_output": True},
            tags=["input", "basic"]
        ))
        
        # 多节点顺序执行测试
        if node_count >= 3:
            cases.append(TestCase(
                case_id="normal_003",
                name="多节点顺序执行测试",
                description="验证多个节点按顺序正确执行",
                category="functional",
                inputs={"items": ["item1", "item2", "item3"]},
                expected_outputs={"processed_count": 3},
                tags=["sequence", "multi-node"]
            ))
        
        return cases
    
    def generate_edge_cases(
        self,
        workflow_description: str
    ) -> list[TestCase]:
        """生成边界场景测试用例
        
        Args:
            workflow_description: 工作流描述
        
        Returns:
            边界测试用例列表
        """
        return [
            TestCase(
                case_id="edge_001",
                name="空输入测试",
                description="验证空输入时的行为",
                category="edge_case",
                inputs={"input_text": ""},
                expected_outputs={"success": True, "handles_empty": True},
                tags=["edge", "empty"]
            ),
            TestCase(
                case_id="edge_002",
                name="最大输入测试",
                description="验证最大输入时的行为",
                category="edge_case",
                inputs={"input_text": "x" * 10000},
                expected_outputs={"success": True, "output_length": "> 0"},
                tags=["edge", "max"]
            ),
            TestCase(
                case_id="edge_003",
                name="特殊字符测试",
                description="验证特殊字符处理",
                category="edge_case",
                inputs={"input_text": "测试<>\"'&字符"},
                expected_outputs={"success": True},
                tags=["edge", "special-char"]
            )
        ]
    
    def generate_error_cases(
        self,
        workflow_description: str
    ) -> list[TestCase]:
        """生成异常场景测试用例
        
        Args:
            workflow_description: 工作流描述
        
        Returns:
            异常测试用例列表
        """
        return [
            TestCase(
                case_id="error_001",
                name="无效输入测试",
                description="验证无效输入的处理",
                category="functional",
                inputs={"invalid_param": True},
                expected_outputs={"success": False, "has_error_message": True},
                tags=["error", "invalid"]
            ),
            TestCase(
                case_id="error_002",
                name="超时测试",
                description="验证超时处理",
                category="performance",
                inputs={"simulate_slow": True},
                expected_outputs={"success": False, "error_type": "TimeoutError"},
                timeout=5.0,
                tags=["error", "timeout"]
            )
        ]
    
    def generate_all_cases(
        self,
        workflow_description: str,
        node_count: int
    ) -> list[TestCase]:
        """生成所有测试用例
        
        Args:
            workflow_description: 工作流描述
            node_count: 节点数量
        
        Returns:
            完整测试用例列表
        """
        cases = []
        cases.extend(self.generate_normal_cases(workflow_description, node_count))
        cases.extend(self.generate_edge_cases(workflow_description))
        cases.extend(self.generate_error_cases(workflow_description))
        
        logger.info("test_cases_generated", count=len(cases))
        return cases


# ============== 测试执行器 ==============

class TestExecutor:
    """测试执行器"""
    
    def __init__(self):
        self.results: list[TestResult] = []
    
    def execute_case(
        self,
        test_case: TestCase,
        workflow_runner: Any
    ) -> TestResult:
        """执行单个测试用例
        
        Args:
            test_case: 测试用例
            workflow_runner: 工作流运行器
        
        Returns:
            测试结果
        """
        logger.debug("executing_test_case", case_id=test_case.case_id)
        
        start_time = time.time()
        
        try:
            # 执行工作流
            result = workflow_runner.run(
                input_data=test_case.inputs,
                timeout=test_case.timeout
            )
            
            execution_time = time.time() - start_time
            
            # 验证结果
            status = self._validate_result(test_case, result)
            
            return TestResult(
                case_id=test_case.case_id,
                status=status,
                execution_time=execution_time,
                actual_outputs=result.get("outputs", {}),
                error_message=result.get("error", ""),
                timestamp=self._get_timestamp()
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            logger.error("test_case_error",
                        case_id=test_case.case_id,
                        error=str(e))
            
            return TestResult(
                case_id=test_case.case_id,
                status=TestStatus.ERROR,
                execution_time=execution_time,
                actual_outputs={},
                error_message=str(e),
                timestamp=self._get_timestamp()
            )
    
    def execute_all(
        self,
        test_cases: list[TestCase],
        workflow_runner: Any
    ) -> list[TestResult]:
        """执行所有测试用例
        
        Args:
            test_cases: 测试用例列表
            workflow_runner: 工作流运行器
        
        Returns:
            测试结果列表
        """
        logger.info("executing_all_test_cases", count=len(test_cases))
        
        self.results = []
        
        for case in test_cases:
            result = self.execute_case(case, workflow_runner)
            self.results.append(result)
        
        return self.results
    
    def _validate_result(
        self,
        test_case: TestCase,
        result: dict
    ) -> TestStatus:
        """验证测试结果
        
        Args:
            test_case: 测试用例
            result: 执行结果
        
        Returns:
            测试状态
        """
        # 基本验证
        if not result.get("success", False):
            # 如果期望失败，则通过
            if test_case.expected_outputs.get("success") is False:
                return TestStatus.PASSED
            return TestStatus.FAILED
        
        # 检查是否有错误但期望成功
        if result.get("error") and test_case.expected_outputs.get("success") is not False:
            return TestStatus.FAILED
        
        return TestStatus.PASSED
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"


# ============== 评估报告生成器 ==============

class EvaluationReportGenerator:
    """评估报告生成器"""
    
    def generate(
        self,
        workflow_name: str,
        test_results: list[TestResult],
        test_cases: list[TestCase]
    ) -> EvaluationReport:
        """生成评估报告
        
        Args:
            workflow_name: 工作流名称
            test_results: 测试结果列表
            test_cases: 测试用例列表
        
        Returns:
            评估报告
        """
        logger.info("generating_evaluation_report",
                   workflow=workflow_name,
                   result_count=len(test_results))
        
        # 统计结果
        passed = sum(1 for r in test_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in test_results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in test_results if r.status == TestStatus.SKIPPED)
        errors = sum(1 for r in test_results if r.status == TestStatus.ERROR)
        total = len(test_results)
        
        # 计算通过率
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        
        # 计算总执行时间
        total_time = sum(r.execution_time for r in test_results)
        
        # 生成问题和建议
        issues = self._analyze_issues(test_results, test_cases)
        suggestions = self._generate_suggestions(issues, test_results)
        
        return EvaluationReport(
            workflow_name=workflow_name,
            total_cases=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            pass_rate=pass_rate,
            execution_time=total_time,
            test_results=test_results,
            issues=issues,
            suggestions=suggestions
        )
    
    def _analyze_issues(
        self,
        test_results: list[TestResult],
        test_cases: list[TestCase]
    ) -> list[str]:
        """分析问题
        
        Args:
            test_results: 测试结果
            test_cases: 测试用例
        
        Returns:
            问题列表
        """
        issues = []
        
        for result in test_results:
            if result.status == TestStatus.FAILED:
                issues.append(f"用例 {result.case_id} 执行失败: {result.error_message}")
            elif result.status == TestStatus.ERROR:
                issues.append(f"用例 {result.case_id} 执行错误: {result.error_message}")
        
        return issues
    
    def _generate_suggestions(
        self,
        issues: list[str],
        test_results: list[TestResult]
    ) -> list[str]:
        """生成改进建议
        
        Args:
            issues: 问题列表
            test_results: 测试结果
        
        Returns:
            建议列表
        """
        suggestions = []
        
        if not issues:
            suggestions.append("所有测试通过，工作流质量良好")
            return suggestions
        
        # 分析问题类型
        failed_count = sum(1 for r in test_results if r.status == TestStatus.FAILED)
        error_count = sum(1 for r in test_results if r.status == TestStatus.ERROR)
        
        if failed_count > 0:
            suggestions.append("检查失败用例的预期输出是否合理，或修复相关代码")
        
        if error_count > 0:
            suggestions.append("修复导致测试错误的异常情况，增强错误处理")
        
        # 检查超时
        timeout_results = [r for r in test_results if r.execution_time > 30]
        if timeout_results:
            suggestions.append("部分用例执行时间较长，考虑优化性能或增加超时设置")
        
        return suggestions


# ============== 便捷函数 ==============

def run_evaluation(
    workflow_name: str,
    workflow_description: str,
    node_count: int,
    workflow_runner: Any
) -> EvaluationReport:
    """运行完整评估流程
    
    Args:
        workflow_name: 工作流名称
        workflow_description: 工作流描述
        node_count: 节点数量
        workflow_runner: 工作流运行器
    
    Returns:
        评估报告
    """
    # 1. 生成测试用例
    generator = TestCaseGenerator()
    test_cases = generator.generate_all_cases(workflow_description, node_count)
    
    # 2. 执行测试
    executor = TestExecutor()
    results = executor.execute_all(test_cases, workflow_runner)
    
    # 3. 生成报告
    report_generator = EvaluationReportGenerator()
    report = report_generator.generate(workflow_name, results, test_cases)
    
    return report
