"""PDCA 长期记忆系统

基于类 Wiki 的自我进化记忆系统：
- 每次迭代的经验自动沉淀为知识
- 下次迭代自动读取并复用
- 结构化的知识积累

使用方法：
    from pdca.core.memory import PDCAMemory
    
    memory = PDCAMemory(memory_dir="pdca_memory")
    
    # 读取历史经验（供 Plan 阶段使用）
    context = memory.get_context_for_next_iteration(iteration=1)
    
    # 写入本次迭代的经验（Act 阶段调用）
    memory.record_iteration_experience(
        iteration=1,
        workflow_name="xxx",
        review_result=review_result,
        proposals=proposals,
        evaluation_report=report
    )
"""

import json
import os
from pathlib import Path
from typing import Any, Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, Field
from enum import Enum
import hashlib


# ============== 记忆模型 ==============

class MemoryCategory(str, Enum):
    """记忆分类"""
    SUCCESS = "success"          # 成功经验
    FAILURE = "failure"         # 失败教训
    PATTERN = "pattern"         # 模式识别
    OPTIMIZATION = "optimization" # 优化方案
    CONFIG = "config"           # 配置经验
    WORKFLOW = "workflow"       # 工作流模板


@dataclass
class MemoryEntry:
    """记忆条目"""
    memory_id: str
    category: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    iteration: int = 0
    workflow_name: str = ""
    impact: str = "medium"  # high/medium/low
    usage_count: int = 0
    last_used: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryEntry':
        return cls(**data)


@dataclass
class IterationExperience:
    """迭代经验记录"""
    iteration: int
    workflow_name: str
    pass_rate: float
    issues: list[str]
    success_factors: list[str]
    proposals_applied: list[str]
    lessons_learned: list[str]
    timestamp: str


class WorkflowMemory(BaseModel):
    """工作流记忆"""
    workflow_name: str = Field(default="")
    total_iterations: int = 0
    best_pass_rate: float = 0.0
    avg_pass_rate: float = 0.0
    experiences: list[dict] = Field(default_factory=list)
    accumulated_wisdom: list[str] = Field(default_factory=list)
    
    # 成功模式
    success_patterns: list[str] = Field(default_factory=list)
    # 失败模式
    failure_patterns: list[str] = Field(default_factory=list)
    # 优化历史
    optimization_history: list[dict] = Field(default_factory=list)


class MemoryContext(BaseModel):
    """供下一轮迭代使用的记忆上下文"""
    iteration: int = Field(default=0)
    previous_workflow_name: str = Field(default="")
    
    # 直接可复用的经验
    reusable_experiences: list[str] = Field(default_factory=list)
    
    # 成功模式提示
    success_patterns: list[str] = Field(default_factory=list)
    
    # 失败教训提醒
    failure_warnings: list[str] = Field(default_factory=list)
    
    # 上轮优化方案（已验证有效）
    verified_optimizations: list[str] = Field(default_factory=list)
    
    # 配置建议
    config_suggestions: list[str] = Field(default_factory=list)
    
    # 总结提示词
    prompt_additions: str = Field(default="")


# ============== 核心记忆系统 ==============

class PDCAMemory:
    """PDCA 长期记忆系统
    
    功能：
    1. 积累：每次迭代的经验自动沉淀
    2. 检索：根据上下文推荐相关经验
    3. 复用：将经验转化为下一轮迭代的提示
    4. 进化：评估经验有效性，淘汰过时经验
    """
    
    def __init__(
        self,
        memory_dir: str = ".pdca_memory",
        max_entries: int = 1000,
        min_usage_threshold: int = 3
    ):
        """初始化记忆系统
        
        Args:
            memory_dir: 记忆存储目录
            max_entries: 最大记忆条目数
            min_usage_threshold: 最低使用次数阈值（低于此值可能被淘汰）
        """
        self.memory_dir = Path(memory_dir)
        self.max_entries = max_entries
        self.min_usage_threshold = min_usage_threshold
        
        # 创建目录结构
        self._ensure_directories()
        
        # 加载或初始化记忆索引
        self._load_index()
    
    def _ensure_directories(self):
        """确保目录结构存在"""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建分类子目录
        for category in MemoryCategory:
            (self.memory_dir / category.value).mkdir(exist_ok=True)
        
        # 创建索引目录
        self.memory_dir.mkdir(exist_ok=True)
        
        # 初始化文件
        self.index_file = self.memory_dir / "index.json"
        self.workflows_file = self.memory_dir / "workflows.json"
        self.experience_log = self.memory_dir / "experience_log.json"
    
    def _load_index(self):
        """加载记忆索引"""
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.memories: Dict[str, MemoryEntry] = {
                    k: MemoryEntry.from_dict(v) 
                    for k, v in data.get('memories', {}).items()
                }
        else:
            self.memories = {}
        
        if self.workflows_file.exists():
            with open(self.workflows_file, 'r', encoding='utf-8') as f:
                self.workflows: Dict[str, WorkflowMemory] = {
                    k: WorkflowMemory(**v) 
                    for k, v in json.load(f).items()
                }
        else:
            self.workflows = {}
    
    def _save_index(self):
        """保存记忆索引"""
        data = {
            'memories': {
                k: v.to_dict() 
                for k, v in self.memories.items()
            },
            'saved_at': datetime.now().isoformat()
        }
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        workflows_data = {
            k: v.model_dump() 
            for k, v in self.workflows.items()
        }
        with open(self.workflows_file, 'w', encoding='utf-8') as f:
            json.dump(workflows_data, f, ensure_ascii=False, indent=2)
    
    def _generate_memory_id(self, title: str, category: str) -> str:
        """生成唯一记忆ID"""
        hash_input = f"{title}_{category}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]
    
    def _create_memory_page(self, entry: MemoryEntry) -> str:
        """创建类 Wiki 格式的记忆页面"""
        page = f"""# {entry.title}

## 基本信息
- **记忆ID**: {entry.memory_id}
- **分类**: {entry.category}
- **创建时间**: {entry.created_at}
- **迭代次数**: {entry.iteration}
- **工作流**: {entry.workflow_name}
- **影响程度**: {entry.impact}

## 标签
{" / ".join(['`'+t+'`' for t in entry.tags])}

## 内容

{entry.content}

## 使用统计
- **累计使用次数**: {entry.usage_count}
- **最后使用**: {entry.last_used or '从未使用'}

---

*此页面由 PDCA 记忆系统自动生成*
"""
        return page
    
    # ============== 写入接口 ==============
    
    def record_iteration_experience(
        self,
        iteration: int,
        workflow_name: str,
        review_result: Any,
        proposals: List[Any],
        evaluation_report: Any
    ):
        """记录迭代经验（供 Act 阶段调用）
        
        将本次迭代的经验自动沉淀为记忆
        """
        timestamp = datetime.now().isoformat()
        
        # 1. 记录工作流元数据
        self._record_workflow_metadata(
            workflow_name, iteration, evaluation_report
        )
        
        # 2. 从复盘结果提取经验
        if hasattr(review_result, 'goal_review'):
            self._extract_goal_review_experience(
                workflow_name, iteration, review_result, timestamp
            )
        
        if hasattr(review_result, 'result_analysis'):
            self._extract_analysis_experience(
                workflow_name, iteration, review_result, timestamp
            )
        
        # 3. 从评估报告提取经验
        if hasattr(evaluation_report, 'issues') and evaluation_report.issues:
            self._extract_issue_experience(
                workflow_name, iteration, evaluation_report.issues, timestamp
            )
        
        # 4. 从优化方案提取经验
        if proposals:
            self._extract_proposal_experience(
                workflow_name, iteration, proposals, timestamp
            )
        
        # 5. 保存索引
        self._save_index()
        
        # 6. 保存经验日志
        self._append_experience_log(
            iteration, workflow_name, evaluation_report
        )
    
    def _record_workflow_metadata(
        self, 
        workflow_name: str, 
        iteration: int,
        evaluation_report: Any
    ):
        """记录工作流元数据"""
        if workflow_name not in self.workflows:
            self.workflows[workflow_name] = WorkflowMemory(
                workflow_name=workflow_name
            )
        
        wm = self.workflows[workflow_name]
        wm.total_iterations = max(wm.total_iterations, iteration)
        
        if hasattr(evaluation_report, 'pass_rate'):
            wm.avg_pass_rate = (
                (wm.avg_pass_rate * (iteration - 1) + evaluation_report.pass_rate) 
                / iteration
            )
            if evaluation_report.pass_rate > wm.best_pass_rate:
                wm.best_pass_rate = evaluation_report.pass_rate
    
    def _extract_goal_review_experience(
        self,
        workflow_name: str,
        iteration: int,
        review_result: Any,
        timestamp: str
    ):
        """从目标回顾提取经验"""
        goal_review = review_result.goal_review
        if isinstance(goal_review, dict):
            # 处理成功经验
            achieved = goal_review.get('achieved_goals', [])
            for goal in achieved:
                entry = MemoryEntry(
                    memory_id=self._generate_memory_id(goal, MemoryCategory.SUCCESS.value),
                    category=MemoryCategory.SUCCESS.value,
                    title=f"目标达成: {goal[:50]}",
                    content=f"在第{iteration}轮迭代中成功达成目标：{goal}",
                    tags=["goal", "achieved", f"iteration_{iteration}"],
                    created_at=timestamp,
                    iteration=iteration,
                    workflow_name=workflow_name,
                    impact="high"
                )
                self._add_memory_entry(entry)
            
            # 处理失败教训
            missed = goal_review.get('missed_goals', [])
            for goal in missed:
                entry = MemoryEntry(
                    memory_id=self._generate_memory_id(goal, MemoryCategory.FAILURE.value),
                    category=MemoryCategory.FAILURE.value,
                    title=f"目标未达成: {goal[:50]}",
                    content=f"在第{iteration}轮迭代中未能达成目标：{goal}",
                    tags=["goal", "missed", f"iteration_{iteration}"],
                    created_at=timestamp,
                    iteration=iteration,
                    workflow_name=workflow_name,
                    impact="high"
                )
                self._add_memory_entry(entry)
    
    def _extract_analysis_experience(
        self,
        workflow_name: str,
        iteration: int,
        review_result: Any,
        timestamp: str
    ):
        """从结果分析提取经验"""
        result_analysis = review_result.result_analysis
        if isinstance(result_analysis, dict):
            # 成功因素
            for factor in result_analysis.get('success_factors', []):
                entry = MemoryEntry(
                    memory_id=self._generate_memory_id(factor, MemoryCategory.PATTERN.value),
                    category=MemoryCategory.PATTERN.value,
                    title=f"成功因素: {factor[:50]}",
                    content=f"第{iteration}轮迭代发现的成功因素：{factor}",
                    tags=["success_factor", "pattern", f"iteration_{iteration}"],
                    created_at=timestamp,
                    iteration=iteration,
                    workflow_name=workflow_name,
                    impact="medium"
                )
                self._add_memory_entry(entry)
            
            # 失败因素
            for factor in result_analysis.get('failure_factors', []):
                entry = MemoryEntry(
                    memory_id=self._generate_memory_id(factor, MemoryCategory.FAILURE.value),
                    category=MemoryCategory.FAILURE.value,
                    title=f"失败因素: {factor[:50]}",
                    content=f"第{iteration}轮迭代发现的失败因素：{factor}",
                    tags=["failure_factor", "pattern", f"iteration_{iteration}"],
                    created_at=timestamp,
                    iteration=iteration,
                    workflow_name=workflow_name,
                    impact="high"
                )
                self._add_memory_entry(entry)
    
    def _extract_issue_experience(
        self,
        workflow_name: str,
        iteration: int,
        issues: List[str],
        timestamp: str
    ):
        """从问题列表提取经验"""
        for issue in issues:
            entry = MemoryEntry(
                memory_id=self._generate_memory_id(issue, MemoryCategory.FAILURE.value),
                category=MemoryCategory.FAILURE.value,
                title=f"问题记录: {issue[:50]}",
                content=f"第{iteration}轮迭代发现的问题：{issue}",
                tags=["issue", "problem", f"iteration_{iteration}"],
                created_at=timestamp,
                iteration=iteration,
                workflow_name=workflow_name,
                impact="medium"
            )
            self._add_memory_entry(entry)
    
    def _extract_proposal_experience(
        self,
        workflow_name: str,
        iteration: int,
        proposals: List[Any],
        timestamp: str
    ):
        """从优化方案提取经验"""
        for proposal in proposals:
            title = getattr(proposal, 'title', str(proposal))[:50]
            desc = getattr(proposal, 'description', '')
            priority = getattr(proposal, 'priority', 'medium')
            
            entry = MemoryEntry(
                memory_id=self._generate_memory_id(title, MemoryCategory.OPTIMIZATION.value),
                category=MemoryCategory.OPTIMIZATION.value,
                title=f"优化方案: {title}",
                content=f"第{iteration}轮迭代生成的优化方案：{title}\n\n描述：{desc}\n优先级：{priority}",
                tags=["optimization", "proposal", f"iteration_{iteration}", priority],
                created_at=timestamp,
                iteration=iteration,
                workflow_name=workflow_name,
                impact="medium"
            )
            self._add_memory_entry(entry)
    
    def _add_memory_entry(self, entry: MemoryEntry):
        """添加记忆条目"""
        self.memories[entry.memory_id] = entry
        
        # 同时保存为类 Wiki 页面
        category_dir = self.memory_dir / entry.category
        wiki_file = category_dir / f"{entry.memory_id}.md"
        
        page_content = self._create_memory_page(entry)
        with open(wiki_file, 'w', encoding='utf-8') as f:
            f.write(page_content)
    
    def _append_experience_log(
        self,
        iteration: int,
        workflow_name: str,
        evaluation_report: Any
    ):
        """追加经验日志"""
        log_entry = {
            "iteration": iteration,
            "workflow_name": workflow_name,
            "timestamp": datetime.now().isoformat(),
            "pass_rate": getattr(evaluation_report, 'pass_rate', 0),
            "total_cases": getattr(evaluation_report, 'total_cases', 0),
            "passed": getattr(evaluation_report, 'passed', 0),
            "failed": getattr(evaluation_report, 'failed', 0),
        }
        
        # 读取现有日志
        if self.experience_log.exists():
            with open(self.experience_log, 'r', encoding='utf-8') as f:
                log = json.load(f)
        else:
            log = {"entries": []}
        
        log["entries"].append(log_entry)
        log["last_updated"] = datetime.now().isoformat()
        
        # 保存
        with open(self.experience_log, 'w', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    
    # ============== 读取接口 ==============
    
    def get_context_for_next_iteration(
        self,
        iteration: int,
        workflow_name: Optional[str] = None
    ) -> MemoryContext:
        """获取供下一轮迭代使用的记忆上下文（供 Plan 阶段调用）
        
        自动从记忆库中检索相关经验，生成提示词增强
        """
        context = MemoryContext(iteration=iteration)
        
        if workflow_name:
            context.previous_workflow_name = workflow_name
        
        # 1. 获取本工作流的历史经验
        if workflow_name and workflow_name in self.workflows:
            wm = self.workflows[workflow_name]
            context.success_patterns = wm.success_patterns
            context.failure_warnings = wm.failure_patterns
        
        # 2. 检索相关记忆（按标签和分类）
        relevant_memories = self._search_relevant_memories(
            workflow_name=workflow_name,
            limit=10
        )
        
        for memory in relevant_memories:
            # 更新使用统计
            memory.usage_count += 1
            memory.last_used = datetime.now().isoformat()
            
            if memory.category == MemoryCategory.SUCCESS.value:
                context.reusable_experiences.append(
                    f"✅ {memory.title}: {memory.content[:100]}"
                )
            elif memory.category == MemoryCategory.FAILURE.value:
                context.failure_warnings.append(
                    f"⚠️ {memory.title}: {memory.content[:100]}"
                )
            elif memory.category == MemoryCategory.OPTIMIZATION.value:
                context.verified_optimizations.append(
                    f"💡 {memory.title}: {memory.content[:100]}"
                )
        
        # 3. 生成提示增强文本
        context.prompt_additions = self._generate_prompt_additions(context)
        
        # 保存索引（更新使用统计）
        self._save_index()
        
        return context
    
    def _search_relevant_memories(
        self,
        workflow_name: Optional[str] = None,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """搜索相关记忆"""
        candidates = list(self.memories.values())
        
        # 按工作流筛选
        if workflow_name:
            candidates = [
                m for m in candidates 
                if m.workflow_name == workflow_name
            ]
        
        # 按分类筛选
        if categories:
            candidates = [
                m for m in candidates 
                if m.category in categories
            ]
        
        # 按标签筛选
        if tags:
            candidates = [
                m for m in candidates 
                if any(t in m.tags for t in tags)
            ]
        
        # 按使用次数和影响程度排序
        def relevance_score(m: MemoryEntry) -> tuple:
            usage_boost = min(m.usage_count * 0.1, 1.0)  # 最多加1分
            impact_score = {"high": 3, "medium": 2, "low": 1}.get(m.impact, 1)
            return (usage_boost + impact_score)
        
        candidates.sort(key=relevance_score, reverse=True)
        
        return candidates[:limit]
    
    def _generate_prompt_additions(self, context: MemoryContext) -> str:
        """生成提示增强文本"""
        additions = []
        
        additions.append("\n\n## 📚 历史经验参考")
        additions.append("（以下经验来自 PDCA 记忆系统，请参考）\n")
        
        if context.success_patterns:
            additions.append("### ✅ 成功模式")
            for pattern in context.success_patterns[:3]:
                additions.append(f"- {pattern}")
            additions.append("")
        
        if context.failure_warnings:
            additions.append("### ⚠️ 失败教训（避免重蹈覆辙）")
            for warning in context.failure_warnings[:3]:
                additions.append(f"- {warning}")
            additions.append("")
        
        if context.reusable_experiences:
            additions.append("### 🔄 可复用经验")
            for exp in context.reusable_experiences[:5]:
                additions.append(f"- {exp}")
            additions.append("")
        
        if context.verified_optimizations:
            additions.append("### 💡 优化方案参考")
            for opt in context.verified_optimizations[:3]:
                additions.append(f"- {opt}")
            additions.append("")
        
        return "\n".join(additions)
    
    # ============== 查询接口 ==============
    
    def search_memories(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[MemoryEntry]:
        """语义搜索记忆（简单关键词匹配）
        
        实际生产中可接入向量数据库做语义搜索
        """
        query_lower = query.lower()
        candidates = list(self.memories.values())
        
        if category:
            candidates = [m for m in candidates if m.category == category]
        
        # 简单评分
        def match_score(m: MemoryEntry) -> float:
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
    
    def get_wiki_page(self, memory_id: str) -> Optional[str]:
        """获取类 Wiki 格式的记忆页面"""
        if memory_id not in self.memories:
            return None
        
        memory = self.memories[memory_id]
        return self._create_memory_page(memory)
    
    def get_workflow_history(self, workflow_name: str) -> Optional[WorkflowMemory]:
        """获取工作流历史记忆"""
        return self.workflows.get(workflow_name)
    
    # ============== 管理接口 ==============
    
    def get_statistics(self) -> dict:
        """获取记忆统计"""
        total = len(self.memories)
        by_category = {}
        for category in MemoryCategory:
            count = sum(1 for m in self.memories.values() if m.category == category.value)
            by_category[category.value] = count
        
        return {
            "total_memories": total,
            "by_category": by_category,
            "workflows_tracked": len(self.workflows),
            "index_file": str(self.index_file)
        }
    
    def prune_old_memories(self, keep_recent: int = 100):
        """淘汰低价值记忆（保留策略）"""
        # 按使用次数和影响程度排序
        candidates = list(self.memories.values())
        candidates.sort(
            key=lambda m: (m.usage_count, {"high": 3, "medium": 2, "low": 1}.get(m.impact, 1)),
            reverse=True
        )
        
        # 保留高价值记忆
        to_keep = set(m.memory_id for m in candidates[:keep_recent])
        
        removed = 0
        for memory_id in list(self.memories.keys()):
            if memory_id not in to_keep:
                del self.memories[memory_id]
                # 删除 Wiki 页面
                for category_dir in self.memory_dir.iterdir():
                    if category_dir.is_dir():
                        wiki_file = category_dir / f"{memory_id}.md"
                        if wiki_file.exists():
                            wiki_file.unlink()
                removed += 1
        
        if removed > 0:
            self._save_index()
        
        return removed
    
    def export_all_wiki(self) -> dict:
        """导出所有 Wiki 页面"""
        wiki_export = {}
        for memory_id, memory in self.memories.items():
            wiki_export[memory_id] = self._create_memory_page(memory)
        return wiki_export


# ============== 与 LLM 交互的记忆增强 ==============

class LLMEnhancedMemory:
    """LLM 增强的记忆系统
    
    使用 LLM 来：
    1. 从迭代结果中自动提取有价值的经验
    2. 评估记忆的有效性
    3. 生成更好的记忆检索提示
    """
    
    def __init__(self, base_memory: PDCAMemory, llm: Any):
        self.memory = base_memory
        self.llm = llm
    
    def extract_and_store_experience(
        self,
        iteration: int,
        workflow_name: str,
        raw_result: Any
    ):
        """使用 LLM 从原始结果中智能提取经验"""
        prompt = f"""你是一个经验提取专家。请从以下 PDCA 迭代结果中提取有价值的经验。

工作流名称: {workflow_name}
迭代次数: {iteration}

迭代结果:
{self._serialize_result(raw_result)}

请提取：
1. **成功经验**：哪些做法是有效的，下次可以复用？
2. **失败教训**：哪些做法有问题，需要避免？
3. **模式识别**：是否发现了某种规律或模式？
4. **优化建议**：有什么具体的改进建议？

以 JSON 格式输出：
{{
    "successes": ["经验1", "经验2"],
    "failures": ["教训1", "教训2"],
    "patterns": ["模式1", "模式2"],
    "optimizations": ["建议1", "建议2"]
}}
"""
        
        try:
            response = self.llm.generate(prompt)
            # 解析 JSON 响应
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                extracted = json.loads(json_match.group())
                
                # 存储到记忆系统
                self._store_extracted_experiences(
                    workflow_name, iteration, extracted
                )
        except Exception as e:
            print(f"LLM 经验提取失败: {e}")
    
    def _serialize_result(self, result: Any) -> str:
        """序列化结果对象"""
        if hasattr(result, 'model_dump'):
            return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
        elif hasattr(result, '__dict__'):
            return json.dumps(result.__dict__, ensure_ascii=False, indent=2, default=str)
        return str(result)
    
    def _store_extracted_experiences(
        self,
        workflow_name: str,
        iteration: int,
        extracted: dict
    ):
        """存储 LLM 提取的经验"""
        timestamp = datetime.now().isoformat()
        
        for exp in extracted.get('successes', []):
            entry = MemoryEntry(
                memory_id=self.memory._generate_memory_id(exp, MemoryCategory.SUCCESS.value),
                category=MemoryCategory.SUCCESS.value,
                title=f"LLM提取-成功经验: {exp[:40]}",
                content=exp,
                tags=["llm_extracted", "success", f"iteration_{iteration}"],
                created_at=timestamp,
                iteration=iteration,
                workflow_name=workflow_name,
                impact="high"
            )
            self.memory._add_memory_entry(entry)
        
        for exp in extracted.get('failures', []):
            entry = MemoryEntry(
                memory_id=self.memory._generate_memory_id(exp, MemoryCategory.FAILURE.value),
                category=MemoryCategory.FAILURE.value,
                title=f"LLM提取-失败教训: {exp[:40]}",
                content=exp,
                tags=["llm_extracted", "failure", f"iteration_{iteration}"],
                created_at=timestamp,
                iteration=iteration,
                workflow_name=workflow_name,
                impact="high"
            )
            self.memory._add_memory_entry(entry)
        
        for pattern in extracted.get('patterns', []):
            entry = MemoryEntry(
                memory_id=self.memory._generate_memory_id(pattern, MemoryCategory.PATTERN.value),
                category=MemoryCategory.PATTERN.value,
                title=f"LLM提取-模式: {pattern[:40]}",
                content=pattern,
                tags=["llm_extracted", "pattern", f"iteration_{iteration}"],
                created_at=timestamp,
                iteration=iteration,
                workflow_name=workflow_name,
                impact="medium"
            )
            self.memory._add_memory_entry(entry)
        
        self.memory._save_index()
    
    def generate_context_prompt(self, iteration: int, workflow_name: str) -> str:
        """使用 LLM 生成更智能的上下文提示"""
        context = self.memory.get_context_for_next_iteration(iteration, workflow_name)
        
        prompt = f"""基于以下 PDCA 记忆上下文，请生成一个供 Plan 阶段使用的提示增强文本。

当前迭代: {iteration}
工作流名称: {workflow_name}

记忆上下文:
{context.prompt_additions}

请生成：
1. 针对这个工作流的特定建议
2. 需要特别注意的问题
3. 可以尝试的优化方向

直接输出提示文本，不要 JSON。
"""
        
        try:
            return self.llm.generate(prompt)
        except Exception:
            return context.prompt_additions


# ============== 与 run_pdca.py 的集成 ==============

def create_memory_integration(llm: Any = None) -> PDCAMemory:
    """创建记忆系统集成实例"""
    memory_dir = Path(__file__).parent.parent / ".pdca_memory"
    base_memory = PDCAMemory(memory_dir=str(memory_dir))
    
    if llm:
        return LLMEnhancedMemory(base_memory, llm)
    
    return base_memory


# ============== 便捷函数 ==============

def get_memory_context(
    iteration: int,
    workflow_name: str,
    memory_dir: str = ".pdca_memory"
) -> MemoryContext:
    """快速获取记忆上下文"""
    memory = PDCAMemory(memory_dir=memory_dir)
    return memory.get_context_for_next_iteration(iteration, workflow_name)


def record_iteration(
    iteration: int,
    workflow_name: str,
    review_result: Any,
    proposals: List[Any],
    evaluation_report: Any,
    memory_dir: str = ".pdca_memory"
):
    """快速记录迭代经验"""
    memory = PDCAMemory(memory_dir=memory_dir)
    memory.record_iteration_experience(
        iteration, workflow_name, review_result, proposals, evaluation_report
    )


if __name__ == "__main__":
    # 测试记忆系统
    memory = PDCAMemory(memory_dir="/tmp/test_pdca_memory")
    
    print("PDCA 记忆系统初始化成功")
    print(f"存储目录: {memory.memory_dir}")
    print(f"统计: {memory.get_statistics()}")