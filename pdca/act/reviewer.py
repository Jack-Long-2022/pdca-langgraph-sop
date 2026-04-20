"""复盘分析模块 (Act阶段)

GR/RAVP复盘流程、优化方案生成和变更应用
"""

from typing import Any, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from datetime import datetime
from pdca.core.logger import get_logger

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


# ============== GRRAVP复盘器 ==============

class GRRAVPReviewer:
    """GR/RAVP复盘器
    
    GR: Goal Review (目标回顾)
    RAVP: Result Analysis (结果分析) -> Action Planning (行动规划) -> Validation Planning (验证规划)
    """
    
    def __init__(self, llm: Optional[Any] = None):
        self.llm = llm
    
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
        
        # 1. 目标回顾
        goal_review = self._review_goals(original_goals, evaluation_report)
        
        # 2. 结果分析
        result_analysis = self._analyze_results(evaluation_report, code_generation_result)
        
        # 3. 行动规划
        action_planning = self._plan_actions(goal_review, result_analysis)
        
        # 4. 验证规划
        validation_planning = self._plan_validation(result_analysis)
        
        # 计算总体评分
        overall_score = self._calculate_overall_score(
            goal_review,
            result_analysis,
            evaluation_report
        )
        
        # 生成建议
        recommendations = self._generate_recommendations(
            goal_review,
            result_analysis,
            evaluation_report
        )
        
        result = GRRAVPReviewResult(
            workflow_name=workflow_name,
            review_date=datetime.utcnow().isoformat() + "Z",
            phase="completed",
            goal_review=goal_review.__dict__,
            result_analysis=result_analysis.__dict__,
            action_planning=action_planning.__dict__,
            validation_planning=validation_planning.__dict__,
            overall_score=overall_score,
            recommendations=recommendations,
            next_steps=[a.action for a in action_planning.actions[:3]]
        )
        
        logger.info("review_complete", 
                   workflow=workflow_name,
                   score=overall_score)
        
        return result
    
    def _review_goals(
        self,
        original_goals: list[str],
        evaluation_report: Any
    ) -> GoalReviewResult:
        """目标回顾"""
        result = GoalReviewResult()
        result.original_goals = original_goals
        
        # 根据评估报告分析目标达成情况
        pass_rate = evaluation_report.pass_rate if hasattr(evaluation_report, 'pass_rate') else 0
        
        for goal in original_goals:
            # 简单匹配逻辑
            goal_lower = goal.lower()
            if "通过" in goal or "pass" in goal_lower:
                if pass_rate >= 80:
                    result.achieved_goals.append(goal)
                elif pass_rate >= 50:
                    result.partial_goals.append(goal)
                else:
                    result.missed_goals.append(goal)
            else:
                # 默认认为部分达成
                result.partial_goals.append(goal)
        
        # 计算完成率
        total = len(original_goals)
        if total > 0:
            result.goal_completion_rate = (
                len(result.achieved_goals) / total * 100 +
                len(result.partial_goals) / total * 50
            )
        
        return result
    
    def _analyze_results(
        self,
        evaluation_report: Any,
        code_generation_result: Any = None
    ) -> ResultAnalysisResult:
        """结果分析"""
        result = ResultAnalysisResult()
        
        if not evaluation_report:
            return result
        
        # 分析成功因素
        if evaluation_report.passed > 0:
            result.success_factors.append("测试用例大部分通过")
        
        if evaluation_report.pass_rate >= 80:
            result.success_factors.append("通过率达标")
        
        # 分析失败因素
        if evaluation_report.failed > 0:
            result.failure_factors.append(f"{evaluation_report.failed}个测试用例失败")
        
        if evaluation_report.errors > 0:
            result.failure_factors.append(f"{evaluation_report.errors}个测试执行错误")
        
        # 记录质量指标
        result.quality_metrics = {
            "pass_rate": evaluation_report.pass_rate,
            "total_cases": evaluation_report.total_cases,
            "passed": evaluation_report.passed,
            "failed": evaluation_report.failed
        }
        
        # 记录性能指标
        result.performance_metrics = {
            "total_execution_time": evaluation_report.execution_time,
            "avg_execution_time": (
                evaluation_report.execution_time / evaluation_report.total_cases
                if evaluation_report.total_cases > 0 else 0
            )
        }
        
        return result
    
    def _plan_actions(
        self,
        goal_review: GoalReviewResult,
        result_analysis: ResultAnalysisResult
    ) -> ActionPlanningResult:
        """行动规划"""
        result = ActionPlanningResult()
        
        # 基于失败目标生成行动
        for goal in goal_review.missed_goals:
            result.actions.append(ActionPlanItem(
                action=f"解决目标未达成问题: {goal}",
                priority="high",
                expected_impact="达成目标"
            ))
        
        # 基于失败因素生成行动
        for factor in result_analysis.failure_factors:
            result.actions.append(ActionPlanItem(
                action=f"修复问题: {factor}",
                priority="high",
                expected_impact="提高通过率"
            ))
        
        # 基于意外结果生成行动
        for unexpected in result_analysis.unexpected_results:
            result.actions.append(ActionPlanItem(
                action=f"调查意外结果: {unexpected}",
                priority="medium",
                expected_impact="理解根本原因"
            ))
        
        # 排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        result.actions.sort(key=lambda a: priority_order.get(a.priority, 1))
        
        return result
    
    def _plan_validation(
        self,
        result_analysis: ResultAnalysisResult
    ) -> ValidationPlanningResult:
        """验证规划"""
        result = ValidationPlanningResult()
        
        # 添加质量指标验证
        if "pass_rate" in result_analysis.quality_metrics:
            result.metrics.append(ValidationPlanItem(
                metric="pass_rate",
                baseline=result_analysis.quality_metrics["pass_rate"],
                target=90.0,
                measurement_method="测试通过率",
                frequency="每次迭代"
            ))
        
        # 成功标准
        result.success_criteria = [
            "通过率达到90%以上",
            "所有高优先级行动完成",
            "无新的严重问题出现"
        ]
        
        # 反馈机制
        result.feedback_mechanisms = [
            "每次测试后自动生成报告",
            "每周复盘会议",
            "关键指标仪表板监控"
        ]
        
        return result
    
    def _calculate_overall_score(
        self,
        goal_review: GoalReviewResult,
        result_analysis: ResultAnalysisResult,
        evaluation_report: Any
    ) -> float:
        """计算总体评分"""
        score = 0.0
        
        # 目标完成度 (40%)
        score += goal_review.goal_completion_rate * 0.4
        
        # 通过率 (40%)
        if evaluation_report:
            score += evaluation_report.pass_rate * 0.4
        
        # 行动规划完成度 (20%)
        if result_analysis.failure_factors:
            # 假设每解决一个问题加5%
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


# ============== 优化方案生成器 ==============

class OptimizationGenerator:
    """优化方案生成器"""
    
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
        proposals = []
        
        # 基于未达成目标生成方案
        for goal in review_result.goal_review.get("missed_goals", []):
            proposals.append(OptimizationProposal(
                proposal_id=f"opt_{len(proposals) + 1}",
                title=f"达成目标: {goal}",
                description=f"制定具体措施确保目标达成",
                affected_components=["配置", "节点逻辑"],
                estimated_effort="medium",
                expected_benefits=["达成目标"],
                priority="high",
                implementation_steps=[
                    "分析目标未达成原因",
                    "制定改进计划",
                    "实施并验证"
                ]
            ))
        
        # 基于失败因素生成方案
        for factor in review_result.result_analysis.get("failure_factors", []):
            proposals.append(OptimizationProposal(
                proposal_id=f"opt_{len(proposals) + 1}",
                title=f"修复: {factor}",
                description=f"解决导致测试失败的问题",
                affected_components=["相关节点"],
                estimated_effort="small",
                expected_benefits=["提高通过率"],
                priority="high" if "失败" in factor else "medium",
                implementation_steps=[
                    "定位问题根因",
                    "修复代码",
                    "重新测试验证"
                ]
            ))
        
        # 基于行动规划生成方案
        actions = review_result.action_planning.get("actions", [])
        for action in actions[:3]:
            if hasattr(action, 'action'):
                # dataclass object
                action_str = action.action
                impact = action.expected_impact
                priority = action.priority
            else:
                # dict
                action_str = action.get('action', '')
                impact = action.get('expected_impact', '')
                priority = action.get('priority', 'medium')
            
            proposals.append(OptimizationProposal(
                proposal_id=f"opt_{len(proposals) + 1}",
                title=f"执行行动: {action_str}",
                description=impact,
                priority=priority,
                estimated_effort="medium"
            ))
        
        return proposals
    
    def prioritize_proposals(
        self,
        proposals: list[OptimizationProposal]
    ) -> list[OptimizationProposal]:
        """对方案进行优先级排序
        
        Args:
            proposals: 优化方案列表
        
        Returns:
            排序后的方案列表
        """
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
        
        # 记录变更
        change_record = {
            "proposal_id": proposal.proposal_id,
            "title": proposal.title,
            "applied_at": datetime.utcnow().isoformat() + "Z",
            "changes": []
        }
        
        # 应用变更
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
        # 简化实现
        return {
            "component": component,
            "action": "modified",
            "description": proposal.description
        }
    
    def rollback(self, change_index: int) -> bool:
        """回滚变更
        
        Args:
            change_index: 变更索引
        
        Returns:
            是否成功
        """
        if 0 <= change_index < len(self.change_history):
            logger.info("rolling_back_change",
                       change_index=change_index,
                       proposal_id=self.change_history[change_index]["proposal_id"])
            # 实现回滚逻辑
            return True
        return False
    
    def get_change_history(self) -> list[dict]:
        """获取变更历史"""
        return self.change_history


# ============== 便捷函数 ==============

def run_grravp_review(
    workflow_name: str,
    original_goals: list[str],
    evaluation_report: Any
) -> GRRAVPReviewResult:
    """快速执行GR/RAVP复盘
    
    Args:
        workflow_name: 工作流名称
        original_goals: 原始目标
        evaluation_report: 评估报告
    
    Returns:
        复盘结果
    """
    reviewer = GRRAVPReviewer()
    return reviewer.review(workflow_name, original_goals, evaluation_report)


def generate_optimizations(
    review_result: GRRAVPReviewResult
) -> list[OptimizationProposal]:
    """从复盘结果生成优化方案
    
    Args:
        review_result: 复盘结果
    
    Returns:
        优化方案列表
    """
    generator = OptimizationGenerator()
    proposals = generator.generate_from_review(review_result)
    return generator.prioritize_proposals(proposals)
