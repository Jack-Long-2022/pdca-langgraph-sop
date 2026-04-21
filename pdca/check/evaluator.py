"""验收测试模块 (Check阶段)

负责验收标准生成、测试用例生成和测试执行
使用LLM进行智能测试用例生成和深度评估
"""

import time
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field
from pdca.core.logger import get_logger
from pdca.core.llm import get_llm_manager, BaseLLM

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


# ============== LLM验收标准生成器 ==============

class LLMCriteriaGenerator:
    """使用LLM生成针对特定工作流的验收标准"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm or get_llm_manager().get_llm()
    
    def generate_criteria(
        self,
        workflow_description: str,
        node_count: int,
        nodes: list[dict],
        edges: list[dict]
    ) -> dict[str, list[str]]:
        """使用LLM生成特定工作流的验收标准
        
        Args:
            workflow_description: 工作流描述
            node_count: 节点数量
            nodes: 节点详情
            edges: 边详情
        
        Returns:
            分类的验收标准
        """
        logger.info("generating_criteria_with_llm")
        
        nodes_info = "\n".join([
            f"- {n.get('name', '未知')} ({n.get('type', 'unknown')})"
            for n in nodes
        ]) if nodes else "无"
        
        edges_info = "\n".join([
            f"- {e.get('source')} -> {e.get('target')}"
            for e in edges
        ]) if edges else "无"
        
        prompt = f"""你是一个测试架构师，需要为工作流生成详细的验收标准。

工作流信息：
- 描述: {workflow_description}
- 节点数: {node_count}
- 节点列表: {nodes_info}
- 边列表: {edges_info}

请为这个特定的工作流生成验收标准，包括：

1. **功能正确性标准** - 工作流必须满足的功能要求
   - 基于这个特定工作流的节点类型和流程
   - 考虑节点间的数据传递

2. **输出质量标准** - 输出必须满足的质量要求
   - 与这个工作流的目标相关

3. **性能指标** - 性能方面的要求
   - 根据节点数量和类型设定合理的性能要求

4. **异常处理标准** - 必须处理的异常情况
   - 考虑这个工作流可能遇到的错误场景

请以JSON格式输出：
{{
    "functional": ["标准1", "标准2", ...],
    "quality": ["标准1", "标准2", ...],
    "performance": ["标准1", "标准2", ...],
    "error_handling": ["标准1", "标准2", ...]
}}
"""
        
        try:
            response = self.llm.generate(prompt)
            return self._parse_criteria_response(response)
        except Exception as e:
            logger.warning("llm_criteria_generation_failed", error=str(e))
            return self._fallback_criteria()
    
    def _parse_criteria_response(self, response: str) -> dict[str, list[str]]:
        """解析LLM响应"""
        import json
        import re
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return {
                    "functional": data.get("functional", []),
                    "quality": data.get("quality", []),
                    "performance": data.get("performance", []),
                    "error_handling": data.get("error_handling", [])
                }
            except json.JSONDecodeError:
                pass
        
        return self._fallback_criteria()
    
    def _fallback_criteria(self) -> dict[str, list[str]]:
        """备用标准"""
        return {
            "functional": [
                "工作流能够正常启动和结束",
                "所有节点按正确的顺序执行",
                "节点间的数据传递正确"
            ],
            "quality": [
                "输出结果完整性",
                "输出格式一致性"
            ],
            "performance": [
                "单个节点执行时间 < 5秒",
                "工作流总执行时间 < 60秒"
            ],
            "error_handling": [
                "无效输入有明确错误提示",
                "关键步骤失败时有回退机制"
            ]
        }


class CriteriaGenerator:
    """验收标准生成器（兼容接口）"""
    
    FUNCTIONAL_CRITERIA = [
        "工作流能够正常启动和结束",
        "所有节点按正确的顺序执行",
        "节点间的数据传递正确",
        "输入输出格式符合预期",
    ]
    
    QUALITY_CRITERIA = [
        "输出结果完整性",
        "输出格式一致性",
        "错误处理合理性",
    ]
    
    PERFORMANCE_CRITERIA = [
        "单个节点执行时间 < 5秒",
        "工作流总执行时间 < 60秒",
        "内存使用合理",
    ]
    
    ERROR_HANDLING_CRITERIA = [
        "无效输入有明确错误提示",
        "网络异常能够捕获和处理",
        "关键步骤失败时有回退机制",
    ]
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm
        self.llm_generator = LLMCriteriaGenerator(llm) if llm else None
    
    def generate_criteria(
        self,
        workflow_description: str,
        node_count: int,
        nodes: list[dict] = None,
        edges: list[dict] = None
    ) -> dict[str, list[str]]:
        """生成验收标准
        
        Args:
            workflow_description: 工作流描述
            node_count: 节点数量
            nodes: 节点详情（LLM用）
            edges: 边详情（LLM用）
        
        Returns:
            分类的验收标准
        """
        nodes = nodes or []
        edges = edges or []
        
        if self.llm_generator:
            return self.llm_generator.generate_criteria(
                workflow_description,
                node_count,
                nodes,
                edges
            )
        
        # 备用方法
        criteria = {
            "functional": self.FUNCTIONAL_CRITERIA.copy(),
            "quality": self.QUALITY_CRITERIA.copy(),
            "performance": self.PERFORMANCE_CRITERIA.copy(),
            "error_handling": self.ERROR_HANDLING_CRITERIA.copy()
        }
        
        if node_count > 10:
            criteria["performance"].append("工作流总执行时间 < 120秒")
        
        return criteria


# ============== LLM测试用例生成器 ==============

class LLMTestCaseGenerator:
    """使用LLM生成针对特定工作流的测试用例"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm or get_llm_manager().get_llm()
    
    def generate_test_cases(
        self,
        workflow_description: str,
        nodes: list[dict],
        criteria: dict[str, list[str]]
    ) -> list[TestCase]:
        """使用LLM生成特定工作流的测试用例
        
        Args:
            workflow_description: 工作流描述
            nodes: 节点详情
            criteria: 验收标准
        
        Returns:
            测试用例列表
        """
        logger.info("generating_test_cases_with_llm")
        
        nodes_info = "\n".join([
            f"- {n.get('name', '未知')} ({n.get('type', 'unknown')}): {n.get('description', '')}"
            for n in nodes
        ]) if nodes else "无"
        
        criteria_info = "\n".join([
            f"- {c}" for c_list in criteria.values() for c in c_list
        ])
        
        prompt = f"""你是一个测试专家，需要为工作流生成全面的测试用例。

工作流信息：
- 描述: {workflow_description}
- 节点列表: 
{nodes_info}

验收标准：
{criteria_info}

请生成测试用例，覆盖：
1. **正常场景** - 验证工作流基本功能
2. **边界场景** - 空输入、最大输入、特殊字符等
3. **异常场景** - 无效输入、超时、错误处理等
4. **性能测试** - 执行时间、并发等

每个测试用例必须包含：
- case_id: 唯一标识
- name: 用例名称
- description: 详细描述
- category: functional/performance/edge_case/error
- inputs: 输入数据
- expected_outputs: 预期输出
- tags: 标签列表

请以JSON格式输出测试用例列表：
{{
    "test_cases": [
        {{
            "case_id": "test_001",
            "name": "用例名称",
            "description": "详细描述",
            "category": "functional|performance|edge_case|error",
            "inputs": {{"key": "value"}},
            "expected_outputs": {{"key": "value"}},
            "tags": ["tag1", "tag2"]
        }}
    ]
}}

只输出JSON。
"""
        
        try:
            response = self.llm.generate(prompt)
            return self._parse_test_cases_response(response)
        except Exception as e:
            logger.warning("llm_test_case_generation_failed", error=str(e))
            return self._fallback_test_cases(workflow_description, len(nodes))
    
    def _parse_test_cases_response(self, response: str) -> list[TestCase]:
        """解析LLM响应"""
        import json
        import re
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                cases_data = data.get("test_cases", [])
                
                cases = []
                for case_data in cases_data:
                    cases.append(TestCase(
                        case_id=case_data.get("case_id", f"test_{len(cases)}"),
                        name=case_data.get("name", "未命名测试"),
                        description=case_data.get("description", ""),
                        category=case_data.get("category", "functional"),
                        inputs=case_data.get("inputs", {}),
                        expected_outputs=case_data.get("expected_outputs", {}),
                        tags=case_data.get("tags", [])
                    ))
                
                return cases
            except json.JSONDecodeError:
                pass
        
        return []
    
    def _fallback_test_cases(self, workflow_description: str, node_count: int) -> list[TestCase]:
        """备用测试用例"""
        cases = [
            TestCase(
                case_id="normal_001",
                name="基本执行测试",
                description="验证工作流能够正常执行完成",
                category="functional",
                inputs={},
                expected_outputs={"success": True},
                tags=["basic", "smoke"]
            ),
            TestCase(
                case_id="normal_002",
                name="带输入的执行测试",
                description="验证带输入数据时工作流正常执行",
                category="functional",
                inputs={"input_text": "测试输入数据"},
                expected_outputs={"success": True, "has_output": True},
                tags=["input", "basic"]
            ),
            TestCase(
                case_id="edge_001",
                name="空输入测试",
                description="验证空输入时的行为",
                category="edge_case",
                inputs={"input_text": ""},
                expected_outputs={"success": True},
                tags=["edge", "empty"]
            ),
            TestCase(
                case_id="edge_002",
                name="最大输入测试",
                description="验证最大输入时的行为",
                category="edge_case",
                inputs={"input_text": "x" * 10000},
                expected_outputs={"success": True},
                tags=["edge", "max"]
            ),
            TestCase(
                case_id="error_001",
                name="无效输入测试",
                description="验证无效输入的处理",
                category="error",
                inputs={"invalid_param": True},
                expected_outputs={"success": False},
                tags=["error", "invalid"]
            )
        ]
        
        return cases


class TestCaseGenerator:
    """测试用例生成器（兼容接口）"""
    
    def __init__(self, llm: Optional[BaseLLM] = None, criteria_generator: CriteriaGenerator = None):
        self.llm = llm
        self.criteria_generator = criteria_generator or CriteriaGenerator(llm)
        self.llm_generator = LLMTestCaseGenerator(llm) if llm else None
    
    def generate_normal_cases(
        self,
        workflow_description: str,
        node_count: int
    ) -> list[TestCase]:
        """生成正常场景测试用例"""
        if self.llm_generator:
            all_cases = self.llm_generator.generate_test_cases(
                workflow_description,
                [],
                {}
            )
            return [c for c in all_cases if c.category == "functional"][:5]
        
        cases = [
            TestCase(
                case_id="normal_001",
                name="基本执行测试",
                description="验证工作流能够正常执行完成",
                category="functional",
                inputs={},
                expected_outputs={"success": True},
                tags=["basic", "smoke"]
            )
        ]
        
        if node_count >= 3:
            cases.append(TestCase(
                case_id="normal_002",
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
        """生成边界场景测试用例"""
        if self.llm_generator:
            all_cases = self.llm_generator.generate_test_cases(
                workflow_description,
                [],
                {}
            )
            return [c for c in all_cases if c.category == "edge_case"][:5]
        
        return [
            TestCase(
                case_id="edge_001",
                name="空输入测试",
                description="验证空输入时的行为",
                category="edge_case",
                inputs={"input_text": ""},
                expected_outputs={"success": True},
                tags=["edge", "empty"]
            ),
            TestCase(
                case_id="edge_002",
                name="最大输入测试",
                description="验证最大输入时的行为",
                category="edge_case",
                inputs={"input_text": "x" * 10000},
                expected_outputs={"success": True},
                tags=["edge", "max"]
            )
        ]
    
    def generate_error_cases(
        self,
        workflow_description: str
    ) -> list[TestCase]:
        """生成异常场景测试用例"""
        if self.llm_generator:
            all_cases = self.llm_generator.generate_test_cases(
                workflow_description,
                [],
                {}
            )
            return [c for c in all_cases if c.category == "error"][:5]
        
        return [
            TestCase(
                case_id="error_001",
                name="无效输入测试",
                description="验证无效输入的处理",
                category="error",
                inputs={"invalid_param": True},
                expected_outputs={"success": False},
                tags=["error", "invalid"]
            )
        ]
    
    def generate_all_cases(
        self,
        workflow_description: str,
        node_count: int,
        nodes: list[dict] = None,
        criteria: dict[str, list[str]] = None
    ) -> list[TestCase]:
        """生成所有测试用例（使用LLM）"""
        if self.llm_generator:
            criteria = criteria or {}
            return self.llm_generator.generate_test_cases(
                workflow_description,
                nodes or [],
                criteria
            )
        
        # 备用方法
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
        """执行单个测试用例"""
        logger.debug("executing_test_case", case_id=test_case.case_id)
        
        start_time = time.time()
        
        try:
            result = workflow_runner.run(
                input_data=test_case.inputs,
                timeout=test_case.timeout
            )
            
            execution_time = time.time() - start_time
            
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
        """执行所有测试用例"""
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
        """验证测试结果"""
        if not result.get("success", False):
            if test_case.expected_outputs.get("success") is False:
                return TestStatus.PASSED
            return TestStatus.FAILED
        
        if result.get("error") and test_case.expected_outputs.get("success") is not False:
            return TestStatus.FAILED
        
        return TestStatus.PASSED
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"


# ============== LLM评估报告生成器 ==============

class LLMEvaluationReportGenerator:
    """使用LLM生成深度评估报告"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm or get_llm_manager().get_llm()
    
    def generate_report(
        self,
        workflow_name: str,
        workflow_description: str,
        nodes: list[dict],
        test_results: list[TestResult],
        test_cases: list[TestCase]
    ) -> EvaluationReport:
        """使用LLM生成深度评估报告
        
        Args:
            workflow_name: 工作流名称
            workflow_description: 工作流描述
            nodes: 节点详情
            test_results: 测试结果
            test_cases: 测试用例
        
        Returns:
            评估报告
        """
        logger.info("generating_evaluation_report_with_llm")
        
        # 统计结果
        passed = sum(1 for r in test_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in test_results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in test_results if r.status == TestStatus.SKIPPED)
        errors = sum(1 for r in test_results if r.status == TestStatus.ERROR)
        total = len(test_results)
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        total_time = sum(r.execution_time for r in test_results)
        
        # 构建测试详情
        test_details = []
        for result, case in zip(test_results, test_cases):
            test_details.append(f"- {case.name}: {result.status.value} ({result.execution_time:.2f}s)")
        
        nodes_info = "\n".join([
            f"- {n.get('name', '未知')}: {n.get('description', '')}"
            for n in nodes
        ]) if nodes else "无"
        
        prompt = f"""你是一个测试分析专家，需要对工作流测试结果进行深度分析。

工作流信息：
- 名称: {workflow_name}
- 描述: {workflow_description}
- 节点: {nodes_info}

测试统计：
- 总用例数: {total}
- 通过: {passed}
- 失败: {failed}
- 跳过: {skipped}
- 错误: {errors}
- 通过率: {pass_rate:.1f}%
- 总执行时间: {total_time:.2f}s

测试结果详情：
{chr(10).join(test_details)}

请进行深度分析：
1. 分析失败用例的根本原因
2. 识别成功因素
3. 发现潜在问题
4. 生成具体的改进建议

请以JSON格式输出：
{{
    "issues": [
        {{
            "severity": "high|medium|low",
            "description": "问题描述",
            "root_cause": "根本原因分析",
            "related_cases": ["相关用例"]
        }}
    ],
    "success_factors": ["成功因素1", "成功因素2"],
    "suggestions": [
        {{
            "priority": "high|medium|low",
            "action": "具体改进动作",
            "expected_impact": "预期效果"
        }}
    ],
    "overall_assessment": "总体评估"
}}
"""
        
        try:
            response = self.llm.generate(prompt)
            return self._build_report(
                workflow_name, total, passed, failed, skipped, errors,
                pass_rate, total_time, test_results, response
            )
        except Exception as e:
            logger.warning("llm_report_generation_failed", error=str(e))
            return self._fallback_report(
                workflow_name, total, passed, failed, skipped, errors,
                pass_rate, total_time, test_results
            )
    
    def _build_report(
        self,
        workflow_name: str,
        total: int,
        passed: int,
        failed: int,
        skipped: int,
        errors: int,
        pass_rate: float,
        total_time: float,
        test_results: list[TestResult],
        llm_response: str
    ) -> EvaluationReport:
        """构建报告（合并LLM分析结果）"""
        import json
        import re
        
        issues = []
        suggestions = []
        success_factors = []
        
        json_match = re.search(r'\{[\s\S]*\}', llm_response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                issues = [
                    f"[{i.get('severity', 'medium')}] {i.get('description', '')}"
                    for i in data.get("issues", [])
                ]
                suggestions = [
                    f"[{s.get('priority', 'medium')}] {s.get('action', '')}"
                    for s in data.get("suggestions", [])
                ]
                success_factors = data.get("success_factors", [])
            except json.JSONDecodeError:
                pass
        
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
    
    def _fallback_report(
        self,
        workflow_name: str,
        total: int,
        passed: int,
        failed: int,
        skipped: int,
        errors: int,
        pass_rate: float,
        total_time: float,
        test_results: list[TestResult]
    ) -> EvaluationReport:
        """备用报告生成"""
        issues = []
        suggestions = []
        
        for result in test_results:
            if result.status == TestStatus.FAILED:
                issues.append(f"用例 {result.case_id} 执行失败: {result.error_message}")
            elif result.status == TestStatus.ERROR:
                issues.append(f"用例 {result.case_id} 执行错误: {result.error_message}")
        
        if failed > 0:
            suggestions.append("检查失败用例的预期输出是否合理，或修复相关代码")
        
        if errors > 0:
            suggestions.append("修复导致测试错误的异常情况，增强错误处理")
        
        if not issues:
            suggestions.append("所有测试通过，工作流质量良好")
        
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


class EvaluationReportGenerator:
    """评估报告生成器（兼容接口）"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm
        self.llm_generator = LLMEvaluationReportGenerator(llm) if llm else None
    
    def generate(
        self,
        workflow_name: str,
        test_results: list[TestResult],
        test_cases: list[TestCase],
        workflow_description: str = "",
        nodes: list[dict] = None
    ) -> EvaluationReport:
        """生成评估报告
        
        Args:
            workflow_name: 工作流名称
            test_results: 测试结果列表
            test_cases: 测试用例列表
            workflow_description: 工作流描述
            nodes: 节点详情
        
        Returns:
            评估报告
        """
        logger.info("generating_evaluation_report",
                   workflow=workflow_name,
                   result_count=len(test_results))
        
        # 统计
        passed = sum(1 for r in test_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in test_results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in test_results if r.status == TestStatus.SKIPPED)
        errors = sum(1 for r in test_results if r.status == TestStatus.ERROR)
        total = len(test_results)
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        total_time = sum(r.execution_time for r in test_results)
        
        if self.llm_generator:
            return self.llm_generator.generate_report(
                workflow_name,
                workflow_description,
                nodes or [],
                test_results,
                test_cases
            )
        
        return self._fallback_report(
            workflow_name, total, passed, failed, skipped, errors,
            pass_rate, total_time, test_results
        )
    
    def _fallback_report(
        self,
        workflow_name: str,
        total: int,
        passed: int,
        failed: int,
        skipped: int,
        errors: int,
        pass_rate: float,
        total_time: float,
        test_results: list[TestResult]
    ) -> EvaluationReport:
        """备用报告"""
        issues = []
        suggestions = []
        
        for result in test_results:
            if result.status == TestStatus.FAILED:
                issues.append(f"用例 {result.case_id} 执行失败: {result.error_message}")
            elif result.status == TestStatus.ERROR:
                issues.append(f"用例 {result.case_id} 执行错误: {result.error_message}")
        
        if failed > 0:
            suggestions.append("检查失败用例的预期输出是否合理，或修复相关代码")
        if errors > 0:
            suggestions.append("修复导致测试错误的异常情况")
        if not issues:
            suggestions.append("所有测试通过，工作流质量良好")
        
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


# ============== 便捷函数 ==============

def run_evaluation(
    workflow_name: str,
    workflow_description: str,
    node_count: int,
    workflow_runner: Any,
    llm: Any = None,
    nodes: list[dict] = None
) -> EvaluationReport:
    """运行完整评估流程（支持LLM）
    
    Args:
        workflow_name: 工作流名称
        workflow_description: 工作流描述
        node_count: 节点数量
        workflow_runner: 工作流运行器
        llm: LLM实例（可选）
        nodes: 节点详情（LLM用）
    
    Returns:
        评估报告
    """
    # 1. 生成验收标准（使用LLM）
    criteria_gen = CriteriaGenerator(llm)
    criteria = criteria_gen.generate_criteria(
        workflow_description,
        node_count,
        nodes or []
    )
    
    # 2. 生成测试用例（使用LLM）
    case_gen = TestCaseGenerator(llm, criteria_gen)
    test_cases = case_gen.generate_all_cases(
        workflow_description,
        node_count,
        nodes or [],
        criteria
    )
    
    # 3. 执行测试
    executor = TestExecutor()
    results = executor.execute_all(test_cases, workflow_runner)
    
    # 4. 生成报告（使用LLM）
    report_gen = EvaluationReportGenerator(llm)
    report = report_gen.generate(
        workflow_name,
        results,
        test_cases,
        workflow_description,
        nodes
    )
    
    return report