"""复盘分析模块 (Act阶段)

GR/RAVP复盘流程、优化方案生成和变更应用
使用LLM进行深度复盘分析和创意优化方案生成
"""

from typing import Any, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from datetime import datetime
from pdca.core.logger import get_logger
from pdca.core.llm import get_llm_manager, BaseLLM

logger = get_logger(__name__)


# ============== 复盘结果模型 ==============

class ReviewPhase(str):
    """复盘阶段"""
    GOAL_REVIEW = "goal_review"          # 目标回顾
    RESULT_ANALYSIS = "result_analysis"  # 结果分析
    ACTION_PLANNING = "action_planning"  # 行动规划
    VALIDATION_PLANNING = "validation_planning"  # 验证规划


@dataclass
class GoalReviewResult:
    """目标回顾结果"""
    original_goals: list[str] = field(default_factory=list)
    achieved_goals: list[str] = field(default_factory=list)
    missed_goals: list[str] = field(default_factory=list)
    partial_goals: list[str] = field(default_factory=list)
    goal_completion_rate: float = 0.0


@dataclass
class ResultAnalysisResult:
    """结果分析结果"""
    success_factors: list[str] = field(default_factory=list)
    failure_factors: list[str] = field(default_factory=list)
    unexpected_results: list[str] = field(default_factory=list)
    quality_metrics: dict[str, float] = field(default_factory=dict)
    performance_metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class ActionPlanItem:
    """行动规划项"""
    action: str
    priority: str  # high/medium/low
    owner: str = ""
    deadline: str = ""
    expected_impact: str = ""
    status: str = "pending"


@dataclass
class ActionPlanningResult:
    """行动规划结果"""
    actions: list[ActionPlanItem] = field(default_factory=list)
    resource_requirements: dict[str, Any] = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)


@dataclass
class ValidationPlanItem:
    """验证规划项"""
    metric: str
    baseline: Any
    target: Any
    measurement_method: str
    frequency: str


@dataclass
class ValidationPlanningResult:
    """验证规划结果"""
    metrics: list[ValidationPlanItem] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    feedback_mechanisms: list[str] = field(default_factory=list)


class GRRAVPReviewResult(BaseModel):
    """GR/RAVP复盘完整结果"""
    workflow_name: str = Field(default="", description="工作流名称")
    review_date: str = Field(default="", description="复盘日期")
    phase: str = Field(default="", description="当前阶段")
    
    # 各阶段结果
    goal_review: dict = Field(default_factory=dict, description="目标回顾")
    result_analysis: dict = Field(default_factory=dict, description="结果分析")
    action_planning: dict = Field(default_factory=dict, description="行动规划")
    validation_planning: dict = Field(default_factory=dict, description="验证规划")
    
    # 总体评估
    overall_score: float = Field(default=0.0, description="总体评分")
    recommendations: list[str] = Field(default_factory=list, description="建议")
    next_steps: list[str] = Field(default_factory=list, description="下一步")


class OptimizationProposal(BaseModel):
    """优化方案"""
    proposal_id: str = Field(..., description="方案ID")
    title: str = Field(..., description="方案标题")
    description: str = Field(default="", description="方案描述")
    
    # 影响分析
    affected_components: list[str] = Field(default_factory=list, description="影响的组件")
    estimated_effort: str = Field(default="", description="预估工作量")
    expected_benefits: list[str] = Field(default_factory=list, description="预期收益")
    risks: list[str] = Field(default_factory=list, description="风险")
    
    # 实施信息
    priority: str = Field(default="medium", description="优先级: high/medium/low")
    implementation_steps: list[str] = Field(default_factory=list, description="实施步骤")
    rollback_plan: str = Field(default="", description="回滚计划")


# ============== LLM GRRAVP复盘器 ==============

class LLMGRRAVPReviewer:
    """使用LLM进行深度GR/RAVP复盘"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm or get_llm_manager().get_llm()
    
    def review(
        self,
        workflow_name: str,
        original_goals: list[str],
        evaluation_report: Any,
        code_generation_result: Any = None
    ) -> GRRAVPReviewResult:
        """使用LLM执行完整复盘
        
        Args:
            workflow_name: 工作流名称
            original_goals: 原始目标列表
            evaluation_report: 评估报告
            code_generation_result: 代码生成结果
        
        Returns:
            复盘结果
        """
        logger.info("llm_review_start", workflow=workflow_name)
        
        # 提取评估报告信息
        pass_rate = evaluation_report.pass_rate if hasattr(evaluation_report, 'pass_rate') else 0
        total_cases = evaluation_report.total_cases if hasattr(evaluation_report, 'total_cases') else 0
        passed = evaluation_report.passed if hasattr(evaluation_report, 'passed') else 0
        failed = evaluation_report.failed if hasattr(evaluation_report, 'failed') else 0
        issues = evaluation_report.issues if hasattr(evaluation_report, 'issues') else []
        suggestions = evaluation_report.suggestions if hasattr(evaluation_report, 'suggestions') else []
        
        goals_str = "\n".join([f"- {g}" for g in original_goals])
        issues_str = "\n".join([f"- {i}" for i in issues]) if issues else "无"
        suggestions_str = "\n".join([f"- {s}" for s in suggestions]) if suggestions else "无"
        
        prompt = f"""你是一个专业的复盘分析师，需要对工作流进行深度GR/RAVP复盘。

工作流名称：{workflow_name}

原始目标：
{goals_str}

测试评估结果：
- 通过率: {pass_rate:.1f}%
- 总用例数: {total_cases}
- 通过: {passed}
- 失败: {failed}

发现的问题：
{issues_str}

评估建议：
{suggestions_str}

请进行深度复盘分析：

1. **目标回顾 (GR)**：
   - 分析每个原始目标的达成情况
   - 量化目标完成率

2. **结果分析 (RA)**：
   - 识别成功因素（为什么某些部分做得好）
   - 分析失败因素（哪些地方出了问题，为什么）
   - 发现意外结果（超出预期的好或坏的结果）

3. **行动规划 (VP)**：
   - 基于分析结果制定具体的改进行动
   - 确定行动优先级

4. **验证规划**：
   - 制定验证改进行动效果的方法
   - 确定衡量标准

请以JSON格式输出完整的复盘结果：
{{
    "goal_review": {{
        "achieved_goals": ["已达成目标1", "..."],
        "missed_goals": ["未达成目标1", "..."],
        "partial_goals": ["部分达成目标1", "..."],
        "goal_completion_rate": 百分比
    }},
    "result_analysis": {{
        "success_factors": ["成功因素1", "..."],
        "failure_factors": ["失败因素1", "..."],
        "unexpected_results": ["意外结果1", "..."],
        "quality_metrics": {{"metric": value}},
        "performance_metrics": {{"metric": value}}
    }},
    "action_planning": {{
        "actions": [
            {{
                "action": "行动描述",
                "priority": "high|medium|low",
                "expected_impact": "预期影响"
            }}
        ]
    }},
    "validation_planning": {{
        "metrics": [
            {{
                "metric": "指标名称",
                "baseline": 当前值,
                "target": 目标值,
                "measurement_method": "测量方法"
            }}
        ],
        "success_criteria": ["成功标准1", "..."]
    }},
    "overall_score": 0-100的评分,
    "recommendations": ["建议1", "..."],
    "next_steps": ["下一步1", "..."]
}}
"""
        
        try:
            response = self.llm.generate(prompt)
            return self._parse_review_response(
                workflow_name, original_goals, response
            )
        except Exception as e:
            logger.warning("llm_review_failed", error=str(e))
            return self._fallback_review(
                workflow_name, original_goals, evaluation_report
            )
    
    def _parse_review_response(
        self,
        workflow_name: str,
        original_goals: list[str],
        response: str
    ) -> GRRAVPReviewResult:
        """解析LLM响应"""
        import json
        import re
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                
                # 构建goal_review
                goal_review = data.get("goal_review", {})
                if isinstance(goal_review.get("achieved_goals"), list):
                    goal_review["achieved_goals"] = goal_review["achieved_goals"]
                if isinstance(goal_review.get("missed_goals"), list):
                    goal_review["missed_goals"] = goal_review["missed_goals"]
                
                # 构建result_analysis
                result_analysis = data.get("result_analysis", {})
                
                # 构建action_planning
                action_planning = data.get("action_planning", {})
                actions = []
                for a in action_planning.get("actions", []):
                    actions.append(ActionPlanItem(
                        action=a.get("action", ""),
                        priority=a.get("priority", "medium"),
                        expected_impact=a.get("expected_impact", "")
                    ))
                action_planning["actions"] = [
                    {"action": a.action, "priority": a.priority, "expected_impact": a.expected_impact}
                    for a in actions
                ]
                
                # 构建validation_planning
                validation_planning = data.get("validation_planning", {})
                
                return GRRAVPReviewResult(
                    workflow_name=workflow_name,
                    review_date=datetime.utcnow().isoformat() + "Z",
                    phase="completed",
                    goal_review=goal_review,
                    result_analysis=result_analysis,
                    action_planning=action_planning,
                    validation_planning=validation_planning,
                    overall_score=data.get("overall_score", 0.0),
                    recommendations=data.get("recommendations", []),
                    next_steps=data.get("next_steps", [])
                )
            except json.JSONDecodeError as e:
                logger.warning("json_parse_failed", error=str(e))
        
        return self._fallback_review(workflow_name, original_goals, None)
    
    def _fallback_review(
        self,
        workflow_name: str,
        original_goals: list[str],
        evaluation_report: Any
    ) -> GRRAVPReviewResult:
        """备用复盘"""
        pass_rate = evaluation_report.pass_rate if hasattr(evaluation_report, 'pass_rate') else 0
        
        goal_review = {
            "original_goals": original_goals,
            "achieved_goals": [],
            "missed_goals": [],
            "partial_goals": original_goals,
            "goal_completion_rate": pass_rate
        }
        
        result_analysis = {
            "success_factors": ["测试通过率达标"] if pass_rate >= 80 else [],
            "failure_factors": [],
            "quality_metrics": {"pass_rate": pass_rate}
        }
        
        action_planning = {
            "actions": []
        }
        
        return GRRAVPReviewResult(
            workflow_name=workflow_name,
            review_date=datetime.utcnow().isoformat() + "Z",
            phase="completed",
            goal_review=goal_review,
            result_analysis=result_analysis,
            action_planning=action_planning,
            validation_planning={},
            overall_score=pass_rate,
            recommendations=["继续改进"] if pass_rate < 80 else ["保持现状"],
            next_steps=[]
        )


# ============== GRRAVP复盘器 ==============

class GRRAVPReviewer:
    """GR/RAVP复盘器
    
    GR: Goal Review (目标回顾)
    RAVP: Result Analysis (结果分析) -> Action Planning (行动规划) -> Validation Planning (验证规划)
    """
    
    def __init__(self, llm: Optional[Any] = None):
        self.llm = llm
        self.llm_reviewer = LLMGRRAVPReviewer(llm) if llm else None
    
    def review(
        self,
        workflow_name: str,
        original_goals: list[str],
        evaluation_report: Any,
        code_generation_result: Any = None
    ) -> GRRAVPReviewResult:
        """执行完整复盘
        
        Args:
            workflow_name: 工作流名称
            original_goals: 原始目标列表
            evaluation_report: 评估报告
            code_generation_result: 代码生成结果
        
        Returns:
            复盘结果
        """
        logger.info("review_start", workflow=workflow_name)
        
        # 如果有LLM，使用LLM进行深度复盘
        if self.llm_reviewer:
            return self.llm_reviewer.review(
                workflow_name,
                original_goals,
                evaluation_report,
                code_generation_result
            )
        
        # 备用方法
        return self._rule_based_review(
            workflow_name,
            original_goals,
            evaluation_report
        )
    
    def _rule_based_review(
        self,
        workflow_name: str,
        original_goals: list[str],
        evaluation_report: Any
    ) -> GRRAVPReviewResult:
        """基于规则的复盘（备用）"""
        result = GoalReviewResult()
        result.original_goals = original_goals
        
        pass_rate = evaluation_report.pass_rate if hasattr(evaluation_report, 'pass_rate') else 0
        
        for goal in original_goals:
            goal_lower = goal.lower()
            if "通过" in goal or "pass" in goal_lower:
                if pass_rate >= 80:
                    result.achieved_goals.append(goal)
                elif pass_rate >= 50:
                    result.partial_goals.append(goal)
                else:
                    result.missed_goals.append(goal)
            else:
                result.partial_goals.append(goal)
        
        total = len(original_goals)
        if total > 0:
            result.goal_completion_rate = (
                len(result.achieved_goals) / total * 100 +
                len(result.partial_goals) / total * 50
            )
        
        # 结果分析
        result_analysis = ResultAnalysisResult()
        if evaluation_report:
            if evaluation_report.passed > 0:
                result_analysis.success_factors.append("测试用例大部分通过")
            if pass_rate >= 80:
                result_analysis.success_factors.append("通过率达标")
            if evaluation_report.failed > 0:
                result_analysis.failure_factors.append(f"{evaluation_report.failed}个测试用例失败")
            if evaluation_report.errors > 0:
                result_analysis.failure_factors.append(f"{evaluation_report.errors}个测试执行错误")
            
            result_analysis.quality_metrics = {
                "pass_rate": pass_rate,
                "total_cases": evaluation_report.total_cases,
                "passed": evaluation_report.passed,
                "failed": evaluation_report.failed
            }
        
        # 行动规划
        action_planning = ActionPlanningResult()
        for goal in result.missed_goals:
            action_planning.actions.append(ActionPlanItem(
                action=f"解决目标未达成问题: {goal}",
                priority="high",
                expected_impact="达成目标"
            ))
        
        # 验证规划
        validation_planning = ValidationPlanningResult()
        validation_planning.metrics.append(ValidationPlanItem(
            metric="pass_rate",
            baseline=pass_rate,
            target=90.0,
            measurement_method="测试通过率",
            frequency="每次迭代"
        ))
        
        overall_score = self._calculate_overall_score(result, result_analysis, evaluation_report)
        
        return GRRAVPReviewResult(
            workflow_name=workflow_name,
            review_date=datetime.utcnow().isoformat() + "Z",
            phase="completed",
            goal_review=result.__dict__,
            result_analysis=result_analysis.__dict__,
            action_planning={
                "actions": [
                    {"action": a.action, "priority": a.priority, "expected_impact": a.expected_impact}
                    for a in action_planning.actions
                ]
            },
            validation_planning={
                "metrics": [
                    {"metric": m.metric, "baseline": m.baseline, "target": m.target}
                    for m in validation_planning.metrics
                ]
            },
            overall_score=overall_score,
            recommendations=self._generate_recommendations(result, result_analysis, evaluation_report),
            next_steps=[a.action for a in action_planning.actions[:3]]
        )
    
    def _calculate_overall_score(
        self,
        goal_review: GoalReviewResult,
        result_analysis: ResultAnalysisResult,
        evaluation_report: Any
    ) -> float:
        """计算总体评分"""
        score = 0.0
        
        score += goal_review.goal_completion_rate * 0.4
        
        if evaluation_report:
            score += evaluation_report.pass_rate * 0.4
        
        if result_analysis.failure_factors:
            solved = len(result_analysis.success_factors)
            total_issues = len(result_analysis.failure_factors) + solved
            action_score = (solved / total_issues * 100) if total_issues > 0 else 100
            score += action_score * 0.2
        
        return min(100.0, max(0.0, score))
    
    def _generate_recommendations(
        self,
        goal_review: GoalReviewResult,
        result_analysis: ResultAnalysisResult,
        evaluation_report: Any
    ) -> list[str]:
        """生成建议"""
        recommendations = []
        
        if goal_review.goal_completion_rate < 50:
            recommendations.append("目标完成率较低，建议重新审视目标设定")
        
        if evaluation_report and evaluation_report.pass_rate < 70:
            recommendations.append("测试通过率偏低，建议优先解决失败用例")
        
        if not result_analysis.success_factors:
            recommendations.append("缺少成功经验总结，建议记录有效的实践")
        
        if len(result_analysis.failure_factors) > 3:
            recommendations.append("问题较多，建议分批解决，先处理高优先级问题")
        
        if not recommendations:
            recommendations.append("整体表现良好，继续保持")
        
        return recommendations


# ============== LLM优化方案生成器 ==============

class LLMOptimizationGenerator:
    """使用LLM生成创意优化方案"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm or get_llm_manager().get_llm()
    
    def generate_from_review(
        self,
        review_result: GRRAVPReviewResult
    ) -> list[OptimizationProposal]:
        """从复盘结果生成优化方案
        
        Args:
            review_result: 复盘结果
        
        Returns:
            优化方案列表
        """
        logger.info("generating_optimizations_with_llm")
        
        goal_review = review_result.goal_review
        result_analysis = review_result.result_analysis
        issues = goal_review.get("missed_goals", []) + result_analysis.get("failure_factors", [])
        success_factors = result_analysis.get("success_factors", [])
        
        issues_str = "\n".join([f"- {i}" for i in issues]) if issues else "无"
        success_str = "\n".join([f"- {s}" for s in success_factors]) if success_factors else "无"
        
        prompt = f"""你是一个创新优化专家，需要基于复盘结果生成有创意且可行的优化方案。

复盘发现的问题：
{issues_str}

成功的因素（可以借鉴）：
{success_str}

请生成创新性的优化方案，要求：
1. 每个方案都要有创意，不能只是"修复问题"
2. 要考虑长期价值和可复用性
3. 方案要具体可执行
4. 要识别潜在风险

对于每个方案，请提供：
- 方案ID和标题
- 详细描述
- 影响的组件
- 预估工作量（小/中/大）
- 预期收益
- 潜在风险
- 实施步骤
- 回滚计划

请以JSON格式输出：
{{
    "proposals": [
        {{
            "proposal_id": "opt_001",
            "title": "方案标题",
            "description": "详细描述",
            "affected_components": ["组件1", "组件2"],
            "estimated_effort": "small|medium|large",
            "expected_benefits": ["收益1", "收益2"],
            "risks": ["风险1", "风险2"],
            "priority": "high|medium|low",
            "implementation_steps": ["步骤1", "步骤2"],
            "rollback_plan": "回滚计划描述"
        }}
    ]
}}
"""
        
        try:
            response = self.llm.generate(prompt)
            return self._parse_proposals_response(response)
        except Exception as e:
            logger.warning("llm_optimization_failed", error=str(e))
            return self._fallback_proposals(review_result)
    
    def _parse_proposals_response(self, response: str) -> list[OptimizationProposal]:
        """解析LLM响应"""
        import json
        import re
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                proposals_data = data.get("proposals", [])
                
                proposals = []
                for p_data in proposals_data:
                    proposals.append(OptimizationProposal(
                        proposal_id=p_data.get("proposal_id", f"opt_{len(proposals)}"),
                        title=p_data.get("title", "未命名方案"),
                        description=p_data.get("description", ""),
                        affected_components=p_data.get("affected_components", []),
                        estimated_effort=p_data.get("estimated_effort", "medium"),
                        expected_benefits=p_data.get("expected_benefits", []),
                        risks=p_data.get("risks", []),
                        priority=p_data.get("priority", "medium"),
                        implementation_steps=p_data.get("implementation_steps", []),
                        rollback_plan=p_data.get("rollback_plan", "")
                    ))
                
                return proposals
            except json.JSONDecodeError:
                pass
        
        return []
    
    def _fallback_proposals(
        self,
        review_result: GRRAVPReviewResult
    ) -> list[OptimizationProposal]:
        """备用方案生成"""
        proposals = []
        
        for goal in review_result.goal_review.get("missed_goals", []):
            proposals.append(OptimizationProposal(
                proposal_id=f"opt_{len(proposals) + 1}",
                title=f"达成目标: {goal}",
                description=f"制定具体措施确保目标达成",
                affected_components=["配置", "节点逻辑"],
                estimated_effort="medium",
                expected_benefits=["达成目标"],
                priority="high",
                implementation_steps=["分析原因", "制定计划", "实施", "验证"]
            ))
        
        return proposals


class OptimizationGenerator:
    """优化方案生成器"""
    
    def __init__(self, llm: Optional[Any] = None):
        self.llm = llm
        self.llm_generator = LLMOptimizationGenerator(llm) if llm else None
    
    def generate_from_review(
        self,
        review_result: GRRAVPReviewResult
    ) -> list[OptimizationProposal]:
        """从复盘结果生成优化方案
        
        Args:
            review_result: 复盘结果
        
        Returns:
            优化方案列表
        """
        if self.llm_generator:
            return self.llm_generator.generate_from_review(review_result)
        
        # 备用方法
        proposals = []
        
        for goal in review_result.goal_review.get("missed_goals", []):
            proposals.append(OptimizationProposal(
                proposal_id=f"opt_{len(proposals) + 1}",
                title=f"达成目标: {goal}",
                description="制定具体措施确保目标达成",
                affected_components=["配置", "节点逻辑"],
                estimated_effort="medium",
                expected_benefits=["达成目标"],
                priority="high",
                implementation_steps=["分析原因", "制定计划", "实施", "验证"]
            ))
        
        for factor in review_result.result_analysis.get("failure_factors", []):
            proposals.append(OptimizationProposal(
                proposal_id=f"opt_{len(proposals) + 1}",
                title=f"修复: {factor}",
                description="解决导致测试失败的问题",
                affected_components=["相关节点"],
                estimated_effort="small",
                expected_benefits=["提高通过率"],
                priority="high" if "失败" in str(factor) else "medium",
                implementation_steps=["定位问题", "修复代码", "测试验证"]
            ))
        
        return proposals
    
    def prioritize_proposals(
        self,
        proposals: list[OptimizationProposal]
    ) -> list[OptimizationProposal]:
        """对方案进行优先级排序"""
        priority_order = {"high": 0, "medium": 1, "low": 2}
        
        return sorted(
            proposals,
            key=lambda p: (
                priority_order.get(p.priority, 1),
                len(p.affected_components)
            )
        )


# ============== 变更应用器 ==============

class ChangeApplicator:
    """变更应用器"""
    
    def __init__(self):
        self.change_history: list[dict] = []
    
    def apply_optimization(
        self,
        proposal: OptimizationProposal,
        current_config: Any
    ) -> dict[str, Any]:
        """应用优化方案
        
        Args:
            proposal: 优化方案
            current_config: 当前配置
        
        Returns:
            更新后的配置
        """
        logger.info("applying_optimization",
                   proposal_id=proposal.proposal_id,
                   title=proposal.title)
        
        change_record = {
            "proposal_id": proposal.proposal_id,
            "title": proposal.title,
            "applied_at": datetime.utcnow().isoformat() + "Z",
            "changes": []
        }
        
        new_config = self._clone_config(current_config)
        
        for component in proposal.affected_components:
            change = self._apply_change_to_component(new_config, component, proposal)
            change_record["changes"].append(change)
        
        self.change_history.append(change_record)
        
        return new_config
    
    def _clone_config(self, config: Any) -> Any:
        """克隆配置"""
        import copy
        return copy.deepcopy(config)
    
    def _apply_change_to_component(
        self,
        config: Any,
        component: str,
        proposal: OptimizationProposal
    ) -> dict:
        """应用到组件"""
        return {
            "component": component,
            "action": "modified",
            "description": proposal.description
        }
    
    def rollback(self, change_index: int) -> bool:
        """回滚变更"""
        if 0 <= change_index < len(self.change_history):
            logger.info("rolling_back_change",
                       change_index=change_index,
                       proposal_id=self.change_history[change_index]["proposal_id"])
            return True
        return False
    
    def get_change_history(self) -> list[dict]:
        """获取变更历史"""
        return self.change_history


# ============== 便捷函数 ==============

def run_grravp_review(
    workflow_name: str,
    original_goals: list[str],
    evaluation_report: Any,
    llm: Any = None
) -> GRRAVPReviewResult:
    """快速执行GR/RAVP复盘（支持LLM）
    
    Args:
        workflow_name: 工作流名称
        original_goals: 原始目标
        evaluation_report: 评估报告
        llm: LLM实例（可选）
    
    Returns:
        复盘结果
    """
    reviewer = GRRAVPReviewer(llm)
    return reviewer.review(workflow_name, original_goals, evaluation_report)


def generate_optimizations(
    review_result: GRRAVPReviewResult,
    llm: Any = None
) -> list[OptimizationProposal]:
    """从复盘结果生成优化方案（支持LLM）
    
    Args:
        review_result: 复盘结果
        llm: LLM实例（可选）
    
    Returns:
        优化方案列表
    """
    generator = OptimizationGenerator(llm)
    proposals = generator.generate_from_review(review_result)
    return generator.prioritize_proposals(proposals)