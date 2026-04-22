"""PDCA 长期记忆系统

基于JSON的结构化记忆系统：
- 每次迭代的经验自动沉淀
- 下次迭代自动读取并复用
- 简洁的关键词搜索

使用方法：
    from pdca.core.memory import PDCAMemory

    memory = PDCAMemory(memory_dir="pdca_memory")
    context = memory.get_context_for_next_iteration(iteration=1)
    memory.record_iteration_experience(...)
"""

import json
from pathlib import Path
from typing import Any, Optional, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from pdca.core.logger import get_logger

logger = get_logger(__name__)


# ============== 记忆模型 ==============

class MemoryCategory(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PATTERN = "pattern"
    OPTIMIZATION = "optimization"
    CONFIG = "config"
    WORKFLOW = "workflow"


class MemoryEntry(BaseModel):
    """记忆条目（Pydantic统一）"""
    memory_id: str
    category: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: str = ""
    iteration: int = 0
    workflow_name: str = ""
    impact: str = "medium"
    usage_count: int = 0
    last_used: str = ""


class WorkflowMemory(BaseModel):
    """工作流记忆"""
    workflow_name: str = ""
    total_iterations: int = 0
    best_pass_rate: float = 0.0
    avg_pass_rate: float = 0.0
    experiences: list[dict] = Field(default_factory=list)
    success_patterns: list[str] = Field(default_factory=list)
    failure_patterns: list[str] = Field(default_factory=list)
    optimization_history: list[dict] = Field(default_factory=list)


class MemoryContext(BaseModel):
    """供下一轮迭代使用的记忆上下文"""
    iteration: int = 0
    previous_workflow_name: str = ""
    reusable_experiences: list[str] = Field(default_factory=list)
    success_patterns: list[str] = Field(default_factory=list)
    failure_warnings: list[str] = Field(default_factory=list)
    verified_optimizations: list[str] = Field(default_factory=list)
    config_suggestions: list[str] = Field(default_factory=list)
    prompt_additions: str = ""


# ============== 核心记忆系统 ==============

class PDCAMemory:
    """PDCA 长期记忆系统

    功能：
    1. 积累：每次迭代的经验自动沉淀
    2. 检索：根据上下文推荐相关经验
    3. 复用：将经验转化为下一轮迭代的提示
    """

    def __init__(self, memory_dir: str = ".pdca_memory", max_entries: int = 1000):
        self.memory_dir = Path(memory_dir)
        self.max_entries = max_entries
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.memory_dir / "index.json"
        self.workflows_file = self.memory_dir / "workflows.json"
        self.experience_log = self.memory_dir / "experience_log.json"
        self._load_index()

    def _load_index(self):
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.memories: Dict[str, MemoryEntry] = {
                    k: MemoryEntry(**v) for k, v in data.get('memories', {}).items()
                }
        else:
            self.memories = {}

        if self.workflows_file.exists():
            with open(self.workflows_file, 'r', encoding='utf-8') as f:
                self.workflows: Dict[str, WorkflowMemory] = {
                    k: WorkflowMemory(**v) for k, v in json.load(f).items()
                }
        else:
            self.workflows = {}

    def _save_index(self):
        data = {
            'memories': {k: v.model_dump() for k, v in self.memories.items()},
            'saved_at': datetime.now().isoformat()
        }
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        workflows_data = {k: v.model_dump() for k, v in self.workflows.items()}
        with open(self.workflows_file, 'w', encoding='utf-8') as f:
            json.dump(workflows_data, f, ensure_ascii=False, indent=2)

    def _generate_memory_id(self, title: str, category: str) -> str:
        import hashlib
        hash_input = f"{title}_{category}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    # ============== 写入接口 ==============

    def record_iteration_experience(
        self,
        iteration: int,
        workflow_name: str,
        review_result: Any,
        proposals: List[Any],
        evaluation_report: Any
    ):
        """记录迭代经验"""
        timestamp = datetime.now().isoformat()

        # 1. 记录工作流元数据
        self._record_workflow_metadata(workflow_name, iteration, evaluation_report)

        # 2. 从复盘结果提取经验
        if hasattr(review_result, 'goal_review'):
            self._extract_goal_review_experience(workflow_name, iteration, review_result, timestamp)
        if hasattr(review_result, 'result_analysis'):
            self._extract_analysis_experience(workflow_name, iteration, review_result, timestamp)

        # 3. 从评估报告提取经验
        if hasattr(evaluation_report, 'issues') and evaluation_report.issues:
            self._extract_issue_experience(workflow_name, iteration, evaluation_report.issues, timestamp)

        # 4. 从优化方案提取经验
        if proposals:
            self._extract_proposal_experience(workflow_name, iteration, proposals, timestamp)

        # 5. 保存
        self._save_index()
        self._append_experience_log(iteration, workflow_name, evaluation_report)

    def _record_workflow_metadata(self, workflow_name: str, iteration: int, evaluation_report: Any):
        if workflow_name not in self.workflows:
            self.workflows[workflow_name] = WorkflowMemory(workflow_name=workflow_name)

        wm = self.workflows[workflow_name]
        wm.total_iterations = max(wm.total_iterations, iteration)

        if hasattr(evaluation_report, 'pass_rate'):
            wm.avg_pass_rate = (wm.avg_pass_rate * (iteration - 1) + evaluation_report.pass_rate) / iteration
            if evaluation_report.pass_rate > wm.best_pass_rate:
                wm.best_pass_rate = evaluation_report.pass_rate

    def _extract_goal_review_experience(self, workflow_name, iteration, review_result, timestamp):
        goal_review = review_result.goal_review
        if not isinstance(goal_review, dict):
            return

        for goal in goal_review.get('achieved_goals', []):
            self._add_entry(MemoryEntry(
                memory_id=self._generate_memory_id(goal, MemoryCategory.SUCCESS.value),
                category=MemoryCategory.SUCCESS.value,
                title=f"目标达成: {goal[:50]}", content=f"第{iteration}轮达成：{goal}",
                tags=["goal", "achieved", f"iteration_{iteration}"],
                created_at=timestamp, iteration=iteration, workflow_name=workflow_name, impact="high",
            ))

        for goal in goal_review.get('missed_goals', []):
            self._add_entry(MemoryEntry(
                memory_id=self._generate_memory_id(goal, MemoryCategory.FAILURE.value),
                category=MemoryCategory.FAILURE.value,
                title=f"目标未达成: {goal[:50]}", content=f"第{iteration}轮未达成：{goal}",
                tags=["goal", "missed", f"iteration_{iteration}"],
                created_at=timestamp, iteration=iteration, workflow_name=workflow_name, impact="high",
            ))

    def _extract_analysis_experience(self, workflow_name, iteration, review_result, timestamp):
        result_analysis = review_result.result_analysis
        if not isinstance(result_analysis, dict):
            return

        for factor in result_analysis.get('success_factors', []):
            self._add_entry(MemoryEntry(
                memory_id=self._generate_memory_id(factor, MemoryCategory.PATTERN.value),
                category=MemoryCategory.PATTERN.value,
                title=f"成功因素: {factor[:50]}", content=f"第{iteration}轮发现：{factor}",
                tags=["success_factor", "pattern", f"iteration_{iteration}"],
                created_at=timestamp, iteration=iteration, workflow_name=workflow_name,
            ))

        for factor in result_analysis.get('failure_factors', []):
            self._add_entry(MemoryEntry(
                memory_id=self._generate_memory_id(factor, MemoryCategory.FAILURE.value),
                category=MemoryCategory.FAILURE.value,
                title=f"失败因素: {factor[:50]}", content=f"第{iteration}轮发现：{factor}",
                tags=["failure_factor", f"iteration_{iteration}"],
                created_at=timestamp, iteration=iteration, workflow_name=workflow_name, impact="high",
            ))

    def _extract_issue_experience(self, workflow_name, iteration, issues, timestamp):
        for issue in issues:
            self._add_entry(MemoryEntry(
                memory_id=self._generate_memory_id(issue, MemoryCategory.FAILURE.value),
                category=MemoryCategory.FAILURE.value,
                title=f"问题记录: {issue[:50]}", content=f"第{iteration}轮问题：{issue}",
                tags=["issue", "problem", f"iteration_{iteration}"],
                created_at=timestamp, iteration=iteration, workflow_name=workflow_name,
            ))

    def _extract_proposal_experience(self, workflow_name, iteration, proposals, timestamp):
        for proposal in proposals:
            title = getattr(proposal, 'title', str(proposal))[:50]
            desc = getattr(proposal, 'description', '')
            priority = getattr(proposal, 'priority', 'medium')
            self._add_entry(MemoryEntry(
                memory_id=self._generate_memory_id(title, MemoryCategory.OPTIMIZATION.value),
                category=MemoryCategory.OPTIMIZATION.value,
                title=f"优化方案: {title}",
                content=f"第{iteration}轮方案：{title}\n描述：{desc}\n优先级：{priority}",
                tags=["optimization", "proposal", f"iteration_{iteration}", priority],
                created_at=timestamp, iteration=iteration, workflow_name=workflow_name,
            ))

    def _add_entry(self, entry: MemoryEntry):
        self.memories[entry.memory_id] = entry

    def _append_experience_log(self, iteration, workflow_name, evaluation_report):
        log_entry = {
            "iteration": iteration, "workflow_name": workflow_name,
            "timestamp": datetime.now().isoformat(),
            "pass_rate": getattr(evaluation_report, 'pass_rate', 0),
            "total_cases": getattr(evaluation_report, 'total_cases', 0),
            "passed": getattr(evaluation_report, 'passed', 0),
            "failed": getattr(evaluation_report, 'failed', 0),
        }

        if self.experience_log.exists():
            with open(self.experience_log, 'r', encoding='utf-8') as f:
                log = json.load(f)
        else:
            log = {"entries": []}

        log["entries"].append(log_entry)
        log["last_updated"] = datetime.now().isoformat()

        with open(self.experience_log, 'w', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    # ============== 读取接口 ==============

    def get_context_for_next_iteration(self, iteration: int, workflow_name: Optional[str] = None) -> MemoryContext:
        """获取供下一轮迭代使用的记忆上下文"""
        context = MemoryContext(iteration=iteration)

        if workflow_name:
            context.previous_workflow_name = workflow_name

        if workflow_name and workflow_name in self.workflows:
            wm = self.workflows[workflow_name]
            context.success_patterns = wm.success_patterns
            context.failure_warnings = wm.failure_patterns

        relevant_memories = self._search_relevant_memories(workflow_name=workflow_name, limit=10)

        for memory in relevant_memories:
            memory.usage_count += 1
            memory.last_used = datetime.now().isoformat()

            if memory.category == MemoryCategory.SUCCESS.value:
                context.reusable_experiences.append(f"{memory.title}: {memory.content[:100]}")
            elif memory.category == MemoryCategory.FAILURE.value:
                context.failure_warnings.append(f"{memory.title}: {memory.content[:100]}")
            elif memory.category == MemoryCategory.OPTIMIZATION.value:
                context.verified_optimizations.append(f"{memory.title}: {memory.content[:100]}")

        context.prompt_additions = self._generate_prompt_additions(context)
        self._save_index()
        return context

    def _search_relevant_memories(self, workflow_name=None, categories=None, tags=None, limit=10):
        candidates = list(self.memories.values())

        if workflow_name:
            candidates = [m for m in candidates if m.workflow_name == workflow_name]
        if categories:
            candidates = [m for m in candidates if m.category in categories]
        if tags:
            candidates = [m for m in candidates if any(t in m.tags for t in tags)]

        def relevance_score(m):
            usage_boost = min(m.usage_count * 0.1, 1.0)
            impact_score = {"high": 3, "medium": 2, "low": 1}.get(m.impact, 1)
            return usage_boost + impact_score

        candidates.sort(key=relevance_score, reverse=True)
        return candidates[:limit]

    def _generate_prompt_additions(self, context: MemoryContext) -> str:
        parts = ["\n\n## 历史经验参考\n"]

        if context.success_patterns:
            parts.append("### 成功模式")
            for p in context.success_patterns[:3]:
                parts.append(f"- {p}")

        if context.failure_warnings:
            parts.append("\n### 失败教训")
            for w in context.failure_warnings[:3]:
                parts.append(f"- {w}")

        if context.reusable_experiences:
            parts.append("\n### 可复用经验")
            for e in context.reusable_experiences[:5]:
                parts.append(f"- {e}")

        if context.verified_optimizations:
            parts.append("\n### 优化方案参考")
            for o in context.verified_optimizations[:3]:
                parts.append(f"- {o}")

        return "\n".join(parts)

    # ============== 查询接口 ==============

    def search_memories(self, query: str, category: Optional[str] = None, limit: int = 5) -> List[MemoryEntry]:
        """关键词搜索记忆（TODO: 向量搜索）"""
        query_lower = query.lower()
        candidates = list(self.memories.values())

        if category:
            candidates = [m for m in candidates if m.category == category]

        def match_score(m):
            score = 0.0
            if query_lower in m.title.lower():
                score += 3.0
            if query_lower in m.content.lower():
                score += 1.0
            if any(query_lower in tag.lower() for tag in m.tags):
                score += 2.0
            return score

        candidates = [m for m in candidates if match_score(m) > 0]
        candidates.sort(key=match_score, reverse=True)
        return candidates[:limit]

    def get_workflow_history(self, workflow_name: str) -> Optional[WorkflowMemory]:
        return self.workflows.get(workflow_name)

    def get_statistics(self) -> dict:
        by_category = {}
        for category in MemoryCategory:
            by_category[category.value] = sum(1 for m in self.memories.values() if m.category == category.value)
        return {
            "total_memories": len(self.memories),
            "by_category": by_category,
            "workflows_tracked": len(self.workflows),
        }

    def prune_old_memories(self, keep_recent: int = 100):
        candidates = sorted(
            list(self.memories.values()),
            key=lambda m: (m.usage_count, {"high": 3, "medium": 2, "low": 1}.get(m.impact, 1)),
            reverse=True,
        )
        to_keep = {m.memory_id for m in candidates[:keep_recent]}

        removed = 0
        for memory_id in list(self.memories.keys()):
            if memory_id not in to_keep:
                del self.memories[memory_id]
                removed += 1

        if removed > 0:
            self._save_index()
        return removed


# ============== 便捷函数 ==============

def get_memory_context(iteration: int, workflow_name: str, memory_dir: str = ".pdca_memory") -> MemoryContext:
    return PDCAMemory(memory_dir=memory_dir).get_context_for_next_iteration(iteration, workflow_name)


def record_iteration(iteration, workflow_name, review_result, proposals, evaluation_report,
                     memory_dir: str = ".pdca_memory"):
    PDCAMemory(memory_dir=memory_dir).record_iteration_experience(
        iteration, workflow_name, review_result, proposals, evaluation_report
    )
