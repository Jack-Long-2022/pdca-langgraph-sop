"""测试复盘分析模块"""

import pytest
from unittest.mock import MagicMock
from pdca.act.reviewer import (
    GRBARPReviewer,
    GoalReviewResult,
    ResultAnalysisResult,
    ActionPlanningResult,
    ValidationPlanningResult,
    GRBARPReviewResult,
    OptimizationProposal,
    OptimizationGenerator,
    ChangeApplicator,
    run_GRBARP_review,
    generate_optimizations
)


class TestGRBARPReviewer:
    """GRBARPReviewer测试"""
    
    def test_review_calculates_goal_completion(self):
        """测试目标完成率计算"""
        reviewer = GRBARPReviewer()
        
        evaluation_report = MagicMock()
        evaluation_report.pass_rate = 80.0
        evaluation_report.passed = 8
        evaluation_report.failed = 2
        evaluation_report.errors = 0
        evaluation_report.total_cases = 10
        
        result = reviewer.review(
            workflow_name="测试工作流",
            original_goals=["通过测试", "生成代码"],
            evaluation_report=evaluation_report
        )
        
        assert result.workflow_name == "测试工作流"
        assert result.overall_score >= 0
        assert "goal_review" in result.model_dump()
    
    def test_review_generates_recommendations(self):
        """测试建议生成"""
        reviewer = GRBARPReviewer()
        
        evaluation_report = MagicMock()
        evaluation_report.pass_rate = 50.0
        evaluation_report.passed = 5
        evaluation_report.failed = 3
        evaluation_report.errors = 2
        evaluation_report.total_cases = 10
        
        result = reviewer.review(
            workflow_name="测试工作流",
            original_goals=["目标1", "目标2"],
            evaluation_report=evaluation_report
        )
        
        assert len(result.recommendations) > 0
    
    def test_review_handles_empty_report(self):
        """测试空报告处理"""
        reviewer = GRBARPReviewer()
        
        result = reviewer.review(
            workflow_name="测试工作流",
            original_goals=["目标1"],
            evaluation_report=None
        )
        
        assert result.goal_review is not None


class TestGoalReviewResult:
    """GoalReviewResult测试"""
    
    def test_goal_review_result_creation(self):
        """测试目标回顾结果创建"""
        result = GoalReviewResult(
            original_goals=["目标1", "目标2"],
            achieved_goals=["目标1"],
            missed_goals=["目标2"],
            goal_completion_rate=50.0
        )
        
        assert len(result.original_goals) == 2
        assert len(result.achieved_goals) == 1
        assert result.goal_completion_rate == 50.0


class TestResultAnalysisResult:
    """ResultAnalysisResult测试"""
    
    def test_result_analysis_result_creation(self):
        """测试结果分析结果创建"""
        result = ResultAnalysisResult(
            success_factors=["因素1"],
            failure_factors=["因素2"],
            quality_metrics={"pass_rate": 80.0},
            performance_metrics={"time": 5.0}
        )
        
        assert len(result.success_factors) == 1
        assert result.quality_metrics["pass_rate"] == 80.0


class TestOptimizationGenerator:
    """OptimizationGenerator测试"""
    
    def test_generate_from_review(self):
        """测试从复盘结果生成优化方案"""
        generator = OptimizationGenerator()
        
        review_result = GRBARPReviewResult(
            workflow_name="测试",
            goal_review={
                "missed_goals": ["未达成目标1"]
            },
            result_analysis={
                "failure_factors": ["失败因素1"]
            },
            action_planning={
                "actions": [
                    {"action": "行动1", "priority": "high", "expected_impact": "影响1"}
                ]
            }
        )
        
        proposals = generator.generate_from_review(review_result)
        
        assert len(proposals) >= 1
        assert all(isinstance(p, OptimizationProposal) for p in proposals)
    
    def test_prioritize_proposals(self):
        """测试方案优先级排序"""
        generator = OptimizationGenerator()
        
        proposals = [
            OptimizationProposal(
                proposal_id="p1",
                title="低优先级",
                priority="low"
            ),
            OptimizationProposal(
                proposal_id="p2",
                title="高优先级",
                priority="high"
            ),
            OptimizationProposal(
                proposal_id="p3",
                title="中优先级",
                priority="medium"
            )
        ]
        
        sorted_proposals = generator.prioritize_proposals(proposals)
        
        assert sorted_proposals[0].priority == "high"
        assert sorted_proposals[1].priority == "medium"
        assert sorted_proposals[2].priority == "low"


class TestChangeApplicator:
    """ChangeApplicator测试"""
    
    def test_apply_optimization(self):
        """测试应用优化方案"""
        applicator = ChangeApplicator()
        
        proposal = OptimizationProposal(
            proposal_id="opt1",
            title="测试优化",
            description="测试描述",
            affected_components=["component1"],
            priority="high"
        )
        
        current_config = {"setting": "value"}
        new_config = applicator.apply_optimization(proposal, current_config)
        
        assert new_config is not None
        assert len(applicator.change_history) == 1
    
    def test_rollback(self):
        """测试回滚"""
        applicator = ChangeApplicator()
        
        proposal = OptimizationProposal(
            proposal_id="opt1",
            title="测试优化",
            affected_components=["comp1"],
            priority="high"
        )
        
        applicator.apply_optimization(proposal, {})
        result = applicator.rollback(0)
        
        assert result is True
    
    def test_get_change_history(self):
        """测试获取变更历史"""
        applicator = ChangeApplicator()
        
        proposal = OptimizationProposal(
            proposal_id="opt1",
            title="测试优化",
            affected_components=["comp1"],
            priority="high"
        )
        
        applicator.apply_optimization(proposal, {})
        
        history = applicator.get_change_history()
        
        assert len(history) == 1
        assert history[0]["proposal_id"] == "opt1"


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_run_GRBARP_review(self):
        """测试快速复盘"""
        evaluation_report = MagicMock()
        evaluation_report.pass_rate = 90.0
        evaluation_report.passed = 9
        evaluation_report.failed = 1
        evaluation_report.errors = 0
        evaluation_report.total_cases = 10
        evaluation_report.execution_time = 5.0
        
        result = run_GRBARP_review(
            workflow_name="测试工作流",
            original_goals=["通过测试"],
            evaluation_report=evaluation_report
        )
        
        assert isinstance(result, GRBARPReviewResult)
        assert result.workflow_name == "测试工作流"
    
    def test_generate_optimizations(self):
        """测试快速生成优化方案"""
        review_result = GRBARPReviewResult(
            workflow_name="测试",
            goal_review={"missed_goals": ["目标1"]},
            result_analysis={"failure_factors": []},
            action_planning={"actions": []}
        )
        
        proposals = generate_optimizations(review_result)
        
        assert isinstance(proposals, list)
        assert all(isinstance(p, OptimizationProposal) for p in proposals)


class TestIntegration:
    """集成测试"""
    
    def test_full_review_cycle(self):
        """测试完整复盘周期"""
        # 1. 创建评估报告
        evaluation_report = MagicMock()
        evaluation_report.pass_rate = 75.0
        evaluation_report.passed = 6
        evaluation_report.failed = 2
        evaluation_report.errors = 0
        evaluation_report.total_cases = 8
        evaluation_report.execution_time = 10.0
        
        # 2. 执行复盘
        review_result = run_GRBARP_review(
            workflow_name="数据处理工作流",
            original_goals=["通过所有测试", "性能达标"],
            evaluation_report=evaluation_report
        )
        
        assert review_result.overall_score >= 0
        
        # 3. 生成优化方案
        proposals = generate_optimizations(review_result)
        
        if proposals:
            # 4. 应用优化
            applicator = ChangeApplicator()
            new_config = applicator.apply_optimization(proposals[0], {})
            assert new_config is not None
