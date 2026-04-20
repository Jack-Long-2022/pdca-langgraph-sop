"""循环控制器模块 (Act阶段)

负责PDCA循环控制、终止条件判断和版本管理
"""

from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from pdca.core.logger import get_logger

logger = get_logger(__name__)


# ============== 循环状态模型 ==============

class LoopStatus(str, Enum):
    """循环状态"""
    RUNNING = "running"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    FAILED = "failed"


class TerminationReason(str, Enum):
    """终止原因"""
    MAX_ITERATIONS = "max_iterations"      # 达到最大迭代次数
    QUALITY_THRESHOLD = "quality_threshold" # 质量达标
    MANUAL_STOP = "manual_stop"           # 手动停止
    ERROR = "error"                        # 执行错误


@dataclass
class LoopIteration:
    """循环迭代记录"""
    iteration_number: int
    status: LoopStatus
    start_time: str
    end_time: str = ""
    duration: float = 0.0
    pass_rate: float = 0.0
    issues_found: int = 0
    actions_taken: list[str] = field(default_factory=list)
    notes: str = ""


class LoopState(BaseModel):
    """循环状态"""
    workflow_name: str = Field(default="", description="工作流名称")
    current_iteration: int = Field(default=0, description="当前迭代")
    status: LoopStatus = Field(default=LoopStatus.RUNNING, description="循环状态")
    iterations: list[LoopIteration] = Field(default_factory=list, description="迭代记录")
    termination_reason: TerminationReason = Field(default=None, description="终止原因")
    current_version: str = Field(default="0.1.0", description="当前版本")


@dataclass
class VersionInfo:
    """版本信息"""
    version: str
    created_at: str
    changes: list[str]
    review_result: dict = field(default_factory=dict)
    status: str = "active"  # active/archived/rollback


# ============== 循环控制器 ==============

class LoopController:
    """循环控制器
    
    负责控制PDCA循环的执行次数和终止条件
    """
    
    def __init__(
        self,
        max_iterations: int = 2,
        quality_threshold: float = 90.0
    ):
        """初始化循环控制器
        
        Args:
            max_iterations: 最大迭代次数
            quality_threshold: 质量阈值（通过率百分比）
        """
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.state = LoopState()
        self.versions: list[VersionInfo] = []
    
    def start(self, workflow_name: str) -> LoopState:
        """开始循环
        
        Args:
            workflow_name: 工作流名称
        
        Returns:
            循环状态
        """
        logger.info("loop_start", 
                   workflow=workflow_name,
                   max_iterations=self.max_iterations,
                   quality_threshold=self.quality_threshold)
        
        self.state = LoopState(
            workflow_name=workflow_name,
            current_iteration=0,
            status=LoopStatus.RUNNING
        )
        
        # 创建初始版本
        self._create_version("0.1.0", ["初始版本"])
        
        return self.state
    
    def should_continue(self) -> bool:
        """检查是否应该继续循环
        
        Returns:
            是否继续
        """
        if self.state.status != LoopStatus.RUNNING:
            return False
        
        # 检查迭代次数
        if self.state.current_iteration >= self.max_iterations:
            self._terminate(TerminationReason.MAX_ITERATIONS)
            return False
        
        return True
    
    def should_terminate(
        self,
        pass_rate: float,
        manual_stop: bool = False
    ) -> bool:
        """检查是否应该终止
        
        Args:
            pass_rate: 当前通过率
            manual_stop: 是否手动停止
        
        Returns:
            是否终止
        """
        if manual_stop:
            self._terminate(TerminationReason.MANUAL_STOP)
            return True
        
        if pass_rate >= self.quality_threshold:
            self._terminate(TerminationReason.QUALITY_THRESHOLD)
            return True
        
        if self.state.current_iteration >= self.max_iterations:
            self._terminate(TerminationReason.MAX_ITERATIONS)
            return True
        
        return False
    
    def record_iteration(
        self,
        iteration_number: int,
        status: LoopStatus,
        pass_rate: float,
        issues_found: int = 0,
        actions_taken: list[str] = None
    ) -> LoopIteration:
        """记录迭代
        
        Args:
            iteration_number: 迭代编号
            status: 迭代状态
            pass_rate: 通过率
            issues_found: 发现的问题数
            actions_taken: 采取的行动
        
        Returns:
            迭代记录
        """
        iteration = LoopIteration(
            iteration_number=iteration_number,
            status=status,
            start_time=datetime.utcnow().isoformat() + "Z",
            pass_rate=pass_rate,
            issues_found=issues_found,
            actions_taken=actions_taken or []
        )
        
        self.state.iterations.append(iteration)
        self.state.current_iteration = iteration_number
        # Note: don't change self.state.status here - it tracks loop status, not iteration status
        
        logger.info("iteration_recorded",
                   iteration=iteration_number,
                   status=status.value,
                   pass_rate=pass_rate)
        
        return iteration
    
    def complete_iteration(
        self,
        iteration: LoopIteration,
        notes: str = ""
    ) -> None:
        """完成迭代
        
        Args:
            iteration: 迭代记录
            notes: 备注
        """
        iteration.end_time = datetime.utcnow().isoformat() + "Z"
        iteration.duration = self._calculate_duration(iteration)
        iteration.notes = notes
        
        logger.info("iteration_complete",
                   iteration=iteration.iteration_number,
                   duration=iteration.duration)
    
    def _terminate(self, reason: TerminationReason) -> None:
        """终止循环
        
        Args:
            reason: 终止原因
        """
        self.state.status = LoopStatus.TERMINATED
        self.state.termination_reason = reason
        
        logger.info("loop_terminated",
                   reason=reason.value,
                   iterations_completed=self.state.current_iteration)
    
    def _create_version(self, version: str, changes: list[str]) -> None:
        """创建版本
        
        Args:
            version: 版本号
            changes: 变更列表
        """
        version_info = VersionInfo(
            version=version,
            created_at=datetime.utcnow().isoformat() + "Z",
            changes=changes
        )
        
        self.versions.append(version_info)
        self.state.current_version = version
        
        logger.info("version_created", version=version)
    
    def _calculate_duration(self, iteration: LoopIteration) -> float:
        """计算迭代持续时间"""
        try:
            start = datetime.fromisoformat(iteration.start_time.replace("Z", "+00:00"))
            end = datetime.fromisoformat(iteration.end_time.replace("Z", "+00:00"))
            return (end - start).total_seconds()
        except:
            return 0.0
    
    def get_state(self) -> LoopState:
        """获取循环状态"""
        return self.state
    
    def get_versions(self) -> list[VersionInfo]:
        """获取版本历史"""
        return self.versions
    
    def get_summary(self) -> dict:
        """获取循环摘要"""
        if not self.state.iterations:
            return {"status": "not_started"}
        
        total_iterations = len(self.state.iterations)
        avg_pass_rate = sum(i.pass_rate for i in self.state.iterations) / total_iterations
        
        return {
            "workflow_name": self.state.workflow_name,
            "total_iterations": total_iterations,
            "current_version": self.state.current_version,
            "status": self.state.status.value,
            "termination_reason": self.state.termination_reason.value if self.state.termination_reason else None,
            "average_pass_rate": avg_pass_rate,
            "iterations": [
                {
                    "number": i.iteration_number,
                    "status": i.status.value,
                    "pass_rate": i.pass_rate,
                    "issues_found": i.issues_found
                }
                for i in self.state.iterations
            ]
        }


# ============== 版本管理器 ==============

class VersionManager:
    """版本管理器
    
    负责版本历史记录和回滚支持
    """
    
    def __init__(self):
        self.versions: list[VersionInfo] = []
        self.current_version: Optional[VersionInfo] = None
    
    def create_version(
        self,
        version: str,
        changes: list[str],
        review_result: dict = None
    ) -> VersionInfo:
        """创建新版本
        
        Args:
            version: 版本号
            changes: 变更列表
            review_result: 复盘结果
        
        Returns:
            版本信息
        """
        version_info = VersionInfo(
            version=version,
            created_at=datetime.utcnow().isoformat() + "Z",
            changes=changes,
            review_result=review_result or {},
            status="active"
        )
        
        # 归档旧版本
        if self.current_version:
            self.current_version.status = "archived"
        
        self.versions.append(version_info)
        self.current_version = version_info
        
        logger.info("version_created",
                   version=version,
                   change_count=len(changes))
        
        return version_info
    
    def get_version(self, version: str) -> Optional[VersionInfo]:
        """获取指定版本
        
        Args:
            version: 版本号
        
        Returns:
            版本信息，不存在则返回None
        """
        for v in self.versions:
            if v.version == version:
                return v
        return None
    
    def get_history(self) -> list[VersionInfo]:
        """获取版本历史
        
        Returns:
            版本信息列表
        """
        return sorted(
            self.versions,
            key=lambda v: v.created_at,
            reverse=True
        )
    
    def get_active_versions(self) -> list[VersionInfo]:
        """获取活跃版本
        
        Returns:
            活跃版本列表
        """
        return [v for v in self.versions if v.status == "active"]
    
    def rollback(self, target_version: str) -> bool:
        """回滚到指定版本
        
        Args:
            target_version: 目标版本号
        
        Returns:
            是否成功
        """
        target = self.get_version(target_version)
        
        if not target:
            logger.warning("rollback_failed_version_not_found",
                         version=target_version)
            return False
        
        if target.status == "archived":
            # 重新激活版本
            target.status = "active"
            
            # 归档当前版本
            if self.current_version and self.current_version.status == "active":
                self.current_version.status = "archived"
            
            self.current_version = target
            
            logger.info("rollback_success", version=target_version)
            return True
        
        logger.warning("rollback_failed_invalid_status",
                      version=target_version,
                      status=target.status)
        return False
    
    def can_rollback(self, target_version: str) -> bool:
        """检查是否可以回滚
        
        Args:
            target_version: 目标版本号
        
        Returns:
            是否可以回滚
        """
        target = self.get_version(target_version)
        return target is not None and target.status == "archived"
    
    def compare_versions(
        self,
        version1: str,
        version2: str
    ) -> dict:
        """比较两个版本
        
        Args:
            version1: 版本1
            version2: 版本2
        
        Returns:
            比较结果
        """
        v1 = self.get_version(version1)
        v2 = self.get_version(version2)
        
        if not v1 or not v2:
            return {"error": "版本不存在"}
        
        return {
            "version1": {
                "version": v1.version,
                "created_at": v1.created_at,
                "changes": v1.changes
            },
            "version2": {
                "version": v2.version,
                "created_at": v2.created_at,
                "changes": v2.changes
            },
            "common_changes": set(v1.changes) & set(v2.changes),
            "unique_to_v1": set(v1.changes) - set(v2.changes),
            "unique_to_v2": set(v2.changes) - set(v1.changes)
        }


# ============== 便捷函数 ==============

def create_loop_controller(
    max_iterations: int = 2,
    quality_threshold: float = 90.0
) -> LoopController:
    """创建循环控制器
    
    Args:
        max_iterations: 最大迭代次数
        quality_threshold: 质量阈值
    
    Returns:
        循环控制器
    """
    return LoopController(max_iterations, quality_threshold)


def run_pdca_cycle(
    workflow_name: str,
    evaluation_report: Any,
    max_iterations: int = 2,
    quality_threshold: float = 90.0
) -> dict:
    """运行PDCA循环
    
    Args:
        workflow_name: 工作流名称
        evaluation_report: 评估报告
        max_iterations: 最大迭代次数
        quality_threshold: 质量阈值
    
    Returns:
        循环结果摘要
    """
    controller = LoopController(max_iterations, quality_threshold)
    
    # 开始循环
    controller.start(workflow_name)
    
    # 记录第一次迭代
    pass_rate = evaluation_report.pass_rate if hasattr(evaluation_report, 'pass_rate') else 0
    iteration = controller.record_iteration(
        iteration_number=1,
        status=LoopStatus.COMPLETED,
        pass_rate=pass_rate
    )
    controller.complete_iteration(iteration)
    
    # 检查是否继续
    if controller.should_terminate(pass_rate):
        return controller.get_summary()
    
    # 第二次迭代（如果有）
    if controller.should_continue():
        iteration2 = controller.record_iteration(
            iteration_number=2,
            status=LoopStatus.COMPLETED,
            pass_rate=pass_rate + 5  # 模拟改进
        )
        controller.complete_iteration(iteration2)
    
    return controller.get_summary()
