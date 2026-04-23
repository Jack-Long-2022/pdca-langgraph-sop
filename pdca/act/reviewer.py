"""复盘分析模块 (Act阶段)

GRBARP复盘流程和优化方案生成。
使用单次LLM调用完成复盘+优化（原2次合并为1次）。
"""

from typing import Any, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from datetime import datetime
from pdca.core.logger import get_logger
from pdca.core.llm import OpenAILLM, get_llm_for_task
from pdca.core.utils import parse_json_response
from pdca.core.prompts import SYSTEM_PROMPTS, REVIEW_PROMPT

logger = get_logger(__name__)


# ============== 复盘结果模型 ==============

class ReviewPhase(str):
    GOAL_REVIEW = "goal_review"
    RESULT_ANALYSIS = "result_analysis"
    ACTION_PLANNING = "action_planning"
    VALIDATION_PLANNING = "validation_planning"


@dataclass
class GoalReviewResult:
    original_goals: list[str] = field(default_factory=list)
    achieved_goals: list[str] = field(default_factory=list)
    missed_goals: list[str] = field(default_factory=list)
    partial_goals: list[str] = field(default_factory=list)
    goal_completion_rate: float = 0.0


@dataclass
class ResultAnalysisResult:
    success_factors: list[str] = field(default_factory=list)
    failure_factors: list[str] = field(default_factory=list)
    unexpected_results: list[str] = field(default_factory=list)
    quality_metrics: dict[str, float] = field(default_factory=dict)
    performance_metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class ActionPlanItem:
    action: str
    priority: str
    owner: str = ""
    deadline: str = ""
    expected_impact: str = ""
    status: str = "pending"


@dataclass
class ActionPlanningResult:
    actions: list[ActionPlanItem] = field(default_factory=list)
    resource_requirements: dict[str, Any] = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)


@dataclass
class ValidationPlanItem:
    metric: str
    baseline: Any
    target: Any
    measurement_method: str
    frequency: str


@dataclass
class ValidationPlanningResult:
    metrics: list[ValidationPlanItem] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    feedback_mechanisms: list[str] = field(default_factory=list)


class GRBARPReviewResult(BaseModel):
    """GRBARP复盘完整结果"""
    workflow_name: str = Field(default="", description="工作流名称")
    review_date: str = Field(default="", description="复盘日期")
    phase: str = Field(default="", description="当前阶段")
    goal_review: dict = Field(default_factory=dict, description="目标回顾")
    result_analysis: dict = Field(default_factory=dict, description="结果分析")
    action_planning: dict = Field(default_factory=dict, description="行动规划")
    validation_planning: dict = Field(default_factory=dict, description="验证规划")
    overall_score: float = Field(default=0.0, description="总体评分")
    recommendations: list[str] = Field(default_factory=list, description="建议")
    next_steps: list[str] = Field(default_factory=list, description="下一步")


class OptimizationProposal(BaseModel):
    """优化方案"""
    proposal_id: str = Field(..., description="方案ID")
    title: str = Field(..., description="方案标题")
    description: str = Field(default="", description="方案描述")
    affected_components: list[str] = Field(default_factory=list, description="影响的组件")
    estimated_effort: str = Field(default="", description="预估工作量")
    expected_benefits: list[str] = Field(default_factory=list, description="预期收益")
    risks: list[str] = Field(default_factory=list, description="风险")
    priority: str = Field(default="medium", description="优先级")
    implementation_steps: list[str] = Field(default_factory=list, description="实施步骤")
    rollback_plan: str = Field(default="", description="回滚计划")


# ============== 复盘器（单次LLM调用完成复盘+优化） ==============

class GRBARPReviewer:
    """GRBARP复盘器 — 单次LLM调用完成复盘+优化方案"""

    def __init__(self, llm: Optional[Any] = None, component_library: Optional[Any] = None):
        self.llm = llm
        self.component_library = component_library

    def review(self, workflow_name: str, original_goals: list[str],
               evaluation_report: Any, code_generation_result: Any = None
               ) -> GRBARPReviewResult:
        """执行完整复盘（含优化建议）"""
        logger.info("review_start", workflow=workflow_name)

        if self.llm is None:
            return self._rule_based_review(workflow_name, original_goals, evaluation_report)

        pass_rate = getattr(evaluation_report, 'pass_rate', 0)
        total_cases = getattr(evaluation_report, 'total_cases', 0)
        passed = getattr(evaluation_report, 'passed', 0)
        failed = getattr(evaluation_report, 'failed', 0)
        issues = getattr(evaluation_report, 'issues', [])
        suggestions = getattr(evaluation_report, 'suggestions', [])

        goals_str = "\n".join([f"- {g}" for g in original_goals])
        issues_str = "\n".join([f"- {i}" for i in issues]) if issues else "无"

        evaluation_summary = f"""通过率: {pass_rate:.1f}%
总用例数: {total_cases}
通过: {passed}
失败: {failed}

发现的问题：
{issues_str}"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["review"]},
            {"role": "user", "content": REVIEW_PROMPT.format(
                workflow_name=workflow_name,
                goals=goals_str,
                evaluation_report=evaluation_summary,
            )},
        ]

        try:
            response = self.llm.generate_messages(messages)
            data = parse_json_response(response)
            if data:
                return self._parse_review_response(workflow_name, data)
        except Exception as e:
            logger.warning("llm_review_failed", error=str(e))

        return self._rule_based_review(workflow_name, original_goals, evaluation_report)

    def _parse_review_response(self, workflow_name: str, data: dict) -> GRBARPReviewResult:
        return GRBARPReviewResult(
            workflow_name=workflow_name,
            review_date=datetime.utcnow().isoformat() + "Z",
            phase="completed",
            goal_review=data.get("goal_review", {}),
            result_analysis=data.get("result_analysis", {}),
            action_planning=data.get("action_planning", {}),
            validation_planning=data.get("validation_planning", {}),
            overall_score=data.get("overall_score", 0.0),
            recommendations=data.get("recommendations", []),
            next_steps=data.get("next_steps", []),
        )

    def _rule_based_review(self, workflow_name, original_goals, evaluation_report):
        pass_rate = getattr(evaluation_report, 'pass_rate', 0)
        return GRBARPReviewResult(
            workflow_name=workflow_name,
            review_date=datetime.utcnow().isoformat() + "Z",
            phase="completed",
            goal_review={
                "original_goals": original_goals,
                "achieved_goals": [],
                "missed_goals": [],
                "partial_goals": original_goals,
                "goal_completion_rate": pass_rate,
            },
            result_analysis={
                "success_factors": ["测试通过率达标"] if pass_rate >= 80 else [],
                "failure_factors": [],
                "quality_metrics": {"pass_rate": pass_rate},
            },
            action_planning={"actions": []},
            validation_planning={},
            overall_score=pass_rate,
            recommendations=["继续改进"] if pass_rate < 80 else ["保持现状"],
            next_steps=[],
        )


# ============== 优化方案生成器 ==============

class OptimizationGenerator:
    """优化方案生成器 — 从复盘结果的optimizations字段提取"""

    def __init__(self, llm: Optional[Any] = None, component_library: Optional[Any] = None):
        self.llm = llm
        self.component_library = component_library

    def generate_from_review(
        self,
        review_result: GRBARPReviewResult,
        config: Optional[Any] = None,
    ) -> list[OptimizationProposal]:
        """从复盘结果生成优化方案（已在单次LLM调用中完成）"""
        # LLM已在review中生成优化建议，提取即可
        proposals = []

        for action in review_result.action_planning.get("actions", []):
            if isinstance(action, dict):
                proposals.append(OptimizationProposal(
                    proposal_id=f"opt_{len(proposals) + 1}",
                    title=action.get("action", "未命名方案"),
                    description=action.get("expected_impact", ""),
                    priority=action.get("priority", "medium"),
                    implementation_steps=action.get("steps", []),
                ))
            elif isinstance(action, str):
                proposals.append(OptimizationProposal(
                    proposal_id=f"opt_{len(proposals) + 1}",
                    title=action, priority="medium",
                ))

        # 如果LLM没返回优化建议，用规则生成
        if not proposals:
            for goal in review_result.goal_review.get("missed_goals", []):
                proposals.append(OptimizationProposal(
                    proposal_id=f"opt_{len(proposals) + 1}",
                    title=f"达成目标: {goal}",
                    description="制定具体措施确保目标达成",
                    priority="high",
                    implementation_steps=["分析原因", "制定计划", "实施", "验证"],
                ))

        # 知识固化：从复盘中识别并保存可复用组件到库
        if self.component_library and config:
            discoveries = self.component_library.discover_reusable_components(
                review_result, config,
                config.meta.name if hasattr(config, 'meta') else "unknown",
            )
            logger.info("reusable_components_solidified", count=len(discoveries))

        return proposals

    def prioritize_proposals(self, proposals: list[OptimizationProposal]) -> list[OptimizationProposal]:
        priority_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(proposals, key=lambda p: priority_order.get(p.priority, 1))


# ============== 变更应用器 ==============

class ChangeApplicator:
    """变更应用器"""

    def __init__(self):
        self.change_history: list[dict] = []

    def apply_optimization(self, proposal: OptimizationProposal, current_config: Any) -> dict[str, Any]:
        logger.info("applying_optimization", proposal_id=proposal.proposal_id, title=proposal.title)

        import copy
        new_config = copy.deepcopy(current_config)

        self.change_history.append({
            "proposal_id": proposal.proposal_id,
            "title": proposal.title,
            "applied_at": datetime.utcnow().isoformat() + "Z",
            "changes": [{"component": c, "action": "modified", "description": proposal.description}
                        for c in proposal.affected_components],
        })
        return new_config

    def rollback(self, change_index: int) -> bool:
        return 0 <= change_index < len(self.change_history)

    def get_change_history(self) -> list[dict]:
        return self.change_history


# ============== 便捷函数 ==============

def run_GRBARP_review(
    workflow_name: str,
    original_goals: list[str],
    evaluation_report: Any,
    llm: Any = None,
    component_library: Any = None,
) -> GRBARPReviewResult:
    """快速执行GRBARP复盘"""
    return GRBARPReviewer(llm, component_library=component_library).review(
        workflow_name, original_goals, evaluation_report
    )


def generate_optimizations(
    review_result: GRBARPReviewResult,
    llm: Any = None,
    config: Any = None,
    component_library: Any = None,
) -> list[OptimizationProposal]:
    """从复盘结果生成优化方案"""
    generator = OptimizationGenerator(llm, component_library=component_library)
    proposals = generator.generate_from_review(review_result, config=config)
    return generator.prioritize_proposals(proposals)
