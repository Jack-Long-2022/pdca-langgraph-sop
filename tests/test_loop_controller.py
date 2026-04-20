"""测试循环控制器模块"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime
from pdca.act.loop_controller import (
    LoopStatus,
    TerminationReason,
    LoopIteration,
    LoopState,
    VersionInfo,
    LoopController,
    VersionManager,
    create_loop_controller,
    run_pdca_cycle
)


class TestLoopController:
    """LoopController测试"""
    
    def test_start_loop(self):
        """测试开始循环"""
        controller = LoopController(max_iterations=2, quality_threshold=90.0)
        
        state = controller.start("测试工作流")
        
        assert state.workflow_name == "测试工作流"
        assert state.current_iteration == 0
        assert state.status == LoopStatus.RUNNING
        assert len(controller.versions) == 1
    
    def test_should_continue_when_running(self):
        """测试运行中应该继续"""
        controller = LoopController(max_iterations=2)
        controller.start("测试")
        
        assert controller.should_continue() is True
    
    def test_should_terminate_max_iterations(self):
        """测试达到最大迭代次数终止"""
        controller = LoopController(max_iterations=2)
        controller.start("测试")
        
        # 达到最大迭代次数
        controller.state.current_iteration = 2
        
        assert controller.should_terminate(50.0) is True
        assert controller.state.termination_reason == TerminationReason.MAX_ITERATIONS
    
    def test_should_terminate_quality_threshold(self):
        """测试质量达标终止"""
        controller = LoopController(quality_threshold=90.0)
        controller.start("测试")
        
        assert controller.should_terminate(95.0) is True
        assert controller.state.termination_reason == TerminationReason.QUALITY_THRESHOLD
    
    def test_should_terminate_manual_stop(self):
        """测试手动停止"""
        controller = LoopController()
        controller.start("测试")
        
        assert controller.should_terminate(50.0, manual_stop=True) is True
        assert controller.state.termination_reason == TerminationReason.MANUAL_STOP
    
    def test_record_iteration(self):
        """测试记录迭代"""
        controller = LoopController()
        controller.start("测试")
        
        iteration = controller.record_iteration(
            iteration_number=1,
            status=LoopStatus.COMPLETED,
            pass_rate=80.0,
            issues_found=2,
            actions_taken=["修复问题1", "修复问题2"]
        )
        
        assert iteration.iteration_number == 1
        assert iteration.pass_rate == 80.0
        assert iteration.issues_found == 2
        assert len(iteration.actions_taken) == 2
    
    def test_complete_iteration(self):
        """测试完成迭代"""
        controller = LoopController()
        controller.start("测试")
        
        iteration = LoopIteration(
            iteration_number=1,
            status=LoopStatus.RUNNING,
            start_time=datetime.utcnow().isoformat() + "Z"
        )
        
        controller.complete_iteration(iteration, "测试备注")
        
        assert iteration.end_time != ""
        assert iteration.duration >= 0
        assert iteration.notes == "测试备注"
    
    def test_get_summary(self):
        """测试获取摘要"""
        controller = LoopController(max_iterations=2, quality_threshold=90.0)
        controller.start("测试工作流")
        
        # 记录迭代
        iteration = controller.record_iteration(
            iteration_number=1,
            status=LoopStatus.COMPLETED,
            pass_rate=85.0
        )
        controller.complete_iteration(iteration)
        
        summary = controller.get_summary()
        
        assert summary["workflow_name"] == "测试工作流"
        assert summary["total_iterations"] == 1
        assert summary["average_pass_rate"] == 85.0
    
    def test_get_state(self):
        """测试获取状态"""
        controller = LoopController()
        controller.start("测试")
        
        state = controller.get_state()
        
        assert state.workflow_name == "测试"
        assert state.status == LoopStatus.RUNNING


class TestVersionManager:
    """VersionManager测试"""
    
    def test_create_version(self):
        """测试创建版本"""
        manager = VersionManager()
        
        version = manager.create_version(
            version="1.0.0",
            changes=["添加功能A", "修复问题B"]
        )
        
        assert version.version == "1.0.0"
        assert len(version.changes) == 2
        assert version.status == "active"
        assert manager.current_version == version
    
    def test_create_multiple_versions(self):
        """测试创建多个版本"""
        manager = VersionManager()
        
        v1 = manager.create_version("1.0.0", ["初始版本"])
        v2 = manager.create_version("1.1.0", ["新功能"])
        
        assert v1.status == "archived"
        assert v2.status == "active"
        assert manager.current_version == v2
    
    def test_get_version(self):
        """测试获取版本"""
        manager = VersionManager()
        manager.create_version("1.0.0", ["初始"])
        
        version = manager.get_version("1.0.0")
        
        assert version is not None
        assert version.version == "1.0.0"
    
    def test_get_version_not_found(self):
        """测试版本不存在"""
        manager = VersionManager()
        
        version = manager.get_version("99.0.0")
        
        assert version is None
    
    def test_get_history(self):
        """测试获取历史"""
        manager = VersionManager()
        manager.create_version("1.0.0", ["v1"])
        manager.create_version("2.0.0", ["v2"])
        manager.create_version("3.0.0", ["v3"])
        
        history = manager.get_history()
        
        assert len(history) == 3
        # 应该按时间倒序
        assert history[0].version == "3.0.0"
    
    def test_rollback(self):
        """测试回滚"""
        manager = VersionManager()
        manager.create_version("1.0.0", ["v1"])
        manager.create_version("2.0.0", ["v2"])
        
        result = manager.rollback("1.0.0")
        
        assert result is True
        assert manager.current_version.version == "1.0.0"
        assert manager.get_version("1.0.0").status == "active"
    
    def test_rollback_failed_not_found(self):
        """测试回滚失败-版本不存在"""
        manager = VersionManager()
        manager.create_version("1.0.0", ["v1"])
        
        result = manager.rollback("99.0.0")
        
        assert result is False
    
    def test_can_rollback(self):
        """测试检查回滚能力"""
        manager = VersionManager()
        manager.create_version("1.0.0", ["v1"])
        manager.create_version("2.0.0", ["v2"])
        
        assert manager.can_rollback("1.0.0") is True
        assert manager.can_rollback("99.0.0") is False
    
    def test_compare_versions(self):
        """测试比较版本"""
        manager = VersionManager()
        manager.create_version("1.0.0", ["变更A", "变更B"])
        manager.create_version("2.0.0", ["变更A", "变更C"])
        
        comparison = manager.compare_versions("1.0.0", "2.0.0")
        
        assert "变更A" in comparison["common_changes"]
        assert "变更B" in comparison["unique_to_v1"]
        assert "变更C" in comparison["unique_to_v2"]


class TestLoopIteration:
    """LoopIteration测试"""
    
    def test_loop_iteration_creation(self):
        """测试迭代记录创建"""
        iteration = LoopIteration(
            iteration_number=1,
            status=LoopStatus.RUNNING,
            start_time="2026-04-20T00:00:00Z",
            pass_rate=75.0,
            issues_found=3,
            actions_taken=["行动1"]
        )
        
        assert iteration.iteration_number == 1
        assert iteration.pass_rate == 75.0
        assert iteration.duration == 0.0  # 未完成时为0


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_create_loop_controller(self):
        """测试创建循环控制器"""
        controller = create_loop_controller(
            max_iterations=3,
            quality_threshold=95.0
        )
        
        assert controller.max_iterations == 3
        assert controller.quality_threshold == 95.0
    
    def test_run_pdca_cycle(self):
        """测试运行PDCA循环"""
        evaluation_report = MagicMock()
        evaluation_report.pass_rate = 85.0
        evaluation_report.passed = 8
        evaluation_report.failed = 2
        evaluation_report.total_cases = 10
        
        result = run_pdca_cycle(
            workflow_name="测试工作流",
            evaluation_report=evaluation_report,
            max_iterations=2,
            quality_threshold=90.0
        )
        
        assert result["workflow_name"] == "测试工作流"
        assert result["total_iterations"] >= 1


class TestIntegration:
    """集成测试"""
    
    def test_full_loop_cycle(self):
        """测试完整循环周期"""
        # 1. 创建控制器 - 使用80作为阈值，这样80%通过率会触发终止
        controller = LoopController(max_iterations=3, quality_threshold=80.0)
        
        # 2. 开始循环
        controller.start("数据处理工作流")
        
        # 3. 第一次迭代
        iteration1 = controller.record_iteration(
            iteration_number=1,
            status=LoopStatus.COMPLETED,
            pass_rate=70.0,
            issues_found=3
        )
        controller.complete_iteration(iteration1)
        
        # 4. 检查是否继续
        assert controller.should_continue() is True
        
        # 5. 第二次迭代
        iteration2 = controller.record_iteration(
            iteration_number=2,
            status=LoopStatus.COMPLETED,
            pass_rate=80.0,
            issues_found=1
        )
        controller.complete_iteration(iteration2)
        
        # 6. 检查是否达到质量阈值 (80 >= 80)
        should_stop = controller.should_terminate(80.0)
        assert should_stop is True
        assert controller.state.termination_reason == TerminationReason.QUALITY_THRESHOLD
        
        # 7. 验证摘要
        summary = controller.get_summary()
        assert summary["total_iterations"] == 2
        assert summary["average_pass_rate"] == 75.0
