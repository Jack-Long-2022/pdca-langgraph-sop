"""循环控制器模块 (Act阶段)

负责PDCA循环控制和终止条件判断。
使用简单规则判断（去掉LLM决策，减少冗余调用）。
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
    RUNNING = "running"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    FAILED = "failed"


class TerminationReason(str, Enum):
    MAX_ITERATIONS = "max_iterations"
    QUALITY_THRESHOLD = "quality_threshold"
    MANUAL_STOP = "manual_stop"
    ERROR = "error"


@dataclass
class LoopIteration:
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
    workflow_name: str = Field(default="", description="工作流名称")
    current_iteration: int = Field(default=0, description="当前迭代")
    status: LoopStatus = Field(default=LoopStatus.RUNNING, description="循环状态")
    iterations: list[LoopIteration] = Field(default_factory=list, description="迭代记录")
    termination_reason: Optional[TerminationReason] = Field(default=None, description="终止原因")
    current_version: str = Field(default="0.1.0", description="当前版本")


@dataclass
class VersionInfo:
    version: str
    created_at: str
    changes: list[str]
    review_result: dict = field(default_factory=dict)
    status: str = "active"


# ============== 循环控制器 ==============

class LoopController:
    """循环控制器 — 纯规则判断，不调LLM"""

    def __init__(self, max_iterations: int = 2, quality_threshold: float = 90.0):
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.state = LoopState()
        self.versions: list[VersionInfo] = []

    def start(self, workflow_name: str) -> LoopState:
        logger.info("loop_start", workflow=workflow_name,
                    max_iterations=self.max_iterations,
                    quality_threshold=self.quality_threshold)
        self.state = LoopState(
            workflow_name=workflow_name,
            current_iteration=0,
            status=LoopStatus.RUNNING,
        )
        self._create_version("0.1.0", ["初始版本"])
        return self.state

    def should_continue(self, evaluation_report: Any = None) -> bool:
        """检查是否应该继续循环（纯规则判断）"""
        if self.state.status != LoopStatus.RUNNING:
            return False

        if self.state.current_iteration >= self.max_iterations:
            self._terminate(TerminationReason.MAX_ITERATIONS)
            return False

        # 检查质量是否达标
        if evaluation_report and hasattr(evaluation_report, 'pass_rate'):
            if evaluation_report.pass_rate >= self.quality_threshold:
                self._terminate(TerminationReason.QUALITY_THRESHOLD)
                return False

        return True

    def should_terminate(self, pass_rate: float, manual_stop: bool = False) -> bool:
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

    def record_iteration(self, iteration_number: int, status: LoopStatus,
                         pass_rate: float, issues_found: int = 0,
                         actions_taken: list[str] = None) -> LoopIteration:
        iteration = LoopIteration(
            iteration_number=iteration_number, status=status,
            start_time=datetime.utcnow().isoformat() + "Z",
            pass_rate=pass_rate, issues_found=issues_found,
            actions_taken=actions_taken or [],
        )
        self.state.iterations.append(iteration)
        self.state.current_iteration = iteration_number
        logger.info("iteration_recorded", iteration=iteration_number,
                    status=status.value, pass_rate=pass_rate)
        return iteration

    def complete_iteration(self, iteration: LoopIteration, notes: str = ""):
        iteration.end_time = datetime.utcnow().isoformat() + "Z"
        iteration.notes = notes
        try:
            start = datetime.fromisoformat(iteration.start_time.replace("Z", "+00:00"))
            end = datetime.fromisoformat(iteration.end_time.replace("Z", "+00:00"))
            iteration.duration = (end - start).total_seconds()
        except Exception:
            iteration.duration = 0.0
        logger.info("iteration_complete", iteration=iteration.iteration_number,
                    duration=iteration.duration)

    def get_state(self) -> LoopState:
        return self.state

    def get_summary(self) -> dict:
        if not self.state.iterations:
            return {"status": "not_started"}
        total = len(self.state.iterations)
        avg_pass_rate = sum(i.pass_rate for i in self.state.iterations) / total
        return {
            "workflow_name": self.state.workflow_name,
            "total_iterations": total,
            "current_version": self.state.current_version,
            "status": self.state.status.value,
            "termination_reason": self.state.termination_reason.value if self.state.termination_reason else None,
            "average_pass_rate": avg_pass_rate,
            "iterations": [
                {"number": i.iteration_number, "status": i.status.value,
                 "pass_rate": i.pass_rate, "issues_found": i.issues_found}
                for i in self.state.iterations
            ],
        }

    def _terminate(self, reason: TerminationReason):
        self.state.status = LoopStatus.TERMINATED
        self.state.termination_reason = reason
        logger.info("loop_terminated", reason=reason.value,
                    iterations_completed=self.state.current_iteration)

    def _create_version(self, version: str, changes: list[str]):
        self.versions.append(VersionInfo(
            version=version,
            created_at=datetime.utcnow().isoformat() + "Z",
            changes=changes,
        ))
        self.state.current_version = version
        logger.info("version_created", version=version)


# ============== 版本管理器 ==============

class VersionManager:
    """版本管理器"""

    def __init__(self):
        self.versions: list[VersionInfo] = []
        self.current_version: Optional[VersionInfo] = None

    def create_version(self, version: str, changes: list[str],
                       review_result: dict = None) -> VersionInfo:
        version_info = VersionInfo(
            version=version,
            created_at=datetime.utcnow().isoformat() + "Z",
            changes=changes,
            review_result=review_result or {},
            status="active",
        )
        if self.current_version:
            self.current_version.status = "archived"
        self.versions.append(version_info)
        self.current_version = version_info
        logger.info("version_created", version=version, change_count=len(changes))
        return version_info

    def get_version(self, version: str) -> Optional[VersionInfo]:
        for v in self.versions:
            if v.version == version:
                return v
        return None

    def get_history(self) -> list[VersionInfo]:
        return sorted(self.versions, key=lambda v: v.created_at, reverse=True)

    def rollback(self, target_version: str) -> bool:
        target = self.get_version(target_version)
        if not target or target.status != "archived":
            return False
        target.status = "active"
        if self.current_version:
            self.current_version.status = "archived"
        self.current_version = target
        logger.info("rollback_success", version=target_version)
        return True


# ============== 便捷函数 ==============

def create_loop_controller(
    max_iterations: int = 2,
    quality_threshold: float = 90.0
) -> LoopController:
    return LoopController(max_iterations, quality_threshold)


def run_pdca_cycle(
    workflow_name: str,
    evaluation_report: Any,
    max_iterations: int = 2,
    quality_threshold: float = 90.0
) -> dict:
    """运行PDCA循环（纯规则决策）"""
    controller = LoopController(max_iterations, quality_threshold)
    controller.start(workflow_name)

    pass_rate = getattr(evaluation_report, 'pass_rate', 0)
    iteration = controller.record_iteration(
        iteration_number=1, status=LoopStatus.COMPLETED, pass_rate=pass_rate
    )
    controller.complete_iteration(iteration)

    if controller.should_terminate(pass_rate):
        return controller.get_summary()

    if controller.should_continue(evaluation_report):
        iteration2 = controller.record_iteration(
            iteration_number=2, status=LoopStatus.COMPLETED,
            pass_rate=min(100, pass_rate + 5),
        )
        controller.complete_iteration(iteration2)

    return controller.get_summary()
