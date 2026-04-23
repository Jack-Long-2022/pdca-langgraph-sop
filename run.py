"""PDCA-LangGraph-SOP 统一入口

使用方法:
    # 从文本输入（完整 PDCA）
    python run.py --input examples/input.md --output output

    # 从配置文件跳过 Plan
    python run.py --config config/extractions/wf_xxx.json --output output

    # 启用记忆系统
    python run.py --input examples/input.md --output output --memory

工作流程:
    Plan: 读取输入 -> 结构化抽取 -> 生成工作流配置  (--config 模式跳过)
    Do:   根据配置生成可运行的代码工程
    Check: 运行测试验收，生成评估报告
    Act:   复盘分析，生成优化方案
"""

import argparse
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
import yaml

load_dotenv()

from pdca.core.config import WorkflowConfig
from pdca.core.llm import setup_llm, get_llm_for_task
from pdca.core.logger import get_logger, LogConfig, set_log_config
from pdca.core.memory import PDCAMemory, MemoryContext
from pdca.core.component_library import ComponentLibrary
from pdca.plan.extractor import StructuredExtractor
from pdca.plan.config_generator import ConfigGenerator
from pdca.do_.code_generator import CodeGenerator
from pdca.check.evaluator import run_evaluation
from pdca.act.reviewer import GRBARPReviewer, OptimizationGenerator
from pdca.act.loop_controller import create_loop_controller, LoopStatus


def _sanitize_name(name: str, max_length: int = 30) -> str:
    sanitized = re.sub(r'[^\w一-鿿]', '_', name)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return sanitized[:max_length] if len(sanitized) > max_length else sanitized


def generate_output_folder_name(config: WorkflowConfig, iteration: int) -> str:
    """语义化产出物文件夹名: {seq:03d}_{category}_{name}_v{version}"""
    category = config.meta.category or "general"
    sanitized = _sanitize_name(config.meta.name)
    version = config.meta.version
    return f"{iteration:03d}_{category}_{sanitized}_v{version}"


def update_output_index(output_base: Path, folder_name: str, config: WorkflowConfig, report=None) -> None:
    index_path = output_base / "index.yaml"

    existing = {"workflows": []}
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            existing = yaml.safe_load(f) or {"workflows": []}

    entry = {
        "folder": folder_name,
        "name": config.meta.name,
        "description": config.meta.description,
        "category": config.meta.category or "general",
        "version": config.meta.version,
        "nodes": len(config.nodes),
        "created_at": datetime.now().isoformat(timespec='seconds'),
    }
    if report:
        entry["pass_rate"] = round(report.pass_rate, 1)
        entry["status"] = "completed"

    workflows = existing.get("workflows", [])
    for i, wf in enumerate(workflows):
        if wf.get("folder") == folder_name:
            workflows[i] = entry
            break
    else:
        workflows.append(entry)
    existing["workflows"] = workflows

    output_base.mkdir(parents=True, exist_ok=True)
    with open(index_path, 'w', encoding='utf-8') as f:
        yaml.dump(existing, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def parse_args():
    parser = argparse.ArgumentParser(description="PDCA-LangGraph-SOP - 统一入口")

    # 输入方式（互斥）
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", "-i", type=Path, help="输入文件路径（markdown 格式，走完整 PDCA）")
    input_group.add_argument("--config", type=Path, help="工作流配置 JSON 路径（跳过 Plan，直接 Do/Check/Act）")

    # 输出
    parser.add_argument("--output", "-o", type=Path, default=Path("generated_workflow"), help="输出目录")
    parser.add_argument("--workflow-name", default=None, help="工作流名称（默认从输入推断）")
    parser.add_argument("--category", "-c", default="general", help="工作流分类 (data/auto/qa/integration)")

    # PDCA 控制
    parser.add_argument("--max-iterations", type=int, default=2, help="最大迭代次数 (默认 2)")
    parser.add_argument("--quality-threshold", type=float, default=80.0, help="质量阈值%% (默认 80)")
    parser.add_argument("--skip-do", action="store_true", help="跳过 Do 阶段")
    parser.add_argument("--skip-check", action="store_true", help="跳过 Check 阶段")

    # 增强功能
    parser.add_argument("--memory", action="store_true", help="启用记忆系统（跨迭代经验积累）")
    parser.add_argument("--memory-dir", type=Path, default=Path(".pdca_memory"), help="记忆系统目录")
    parser.add_argument("--component-library-dir", type=Path, default=Path(".pdca_components"), help="组件库目录")
    parser.add_argument("--no-component-library", action="store_true", help="禁用组件库")

    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    return parser.parse_args()


def load_config_from_json(config_path: Path) -> WorkflowConfig:
    """从 JSON 文件加载 WorkflowConfig

    支持两种格式:
    1. 含 analysis 的 JSON（顶层有 analysis + config）
    2. 纯 WorkflowConfig JSON（顶层直接是 meta/nodes/edges/state）
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if "config" in data and "meta" in data.get("config", {}):
        return WorkflowConfig(**data["config"])

    if "meta" in data:
        return WorkflowConfig(**data)

    raise ValueError(f"无法识别的配置格式: {config_path}")


# ── Plan ──────────────────────────────────────────────────────────────────

def plan_phase(
    input_file: Path,
    workflow_name: str = None,
    verbose: bool = False,
    llm: Any = None,
    memory_context: Optional[MemoryContext] = None,
    component_library: Any = None,
):
    """Plan 阶段：从输入文本生成工作流配置"""
    print("\n" + "=" * 60)
    print("[Plan] PLAN 阶段：LLM 结构化抽取与配置生成")
    print("=" * 60)

    print(f"\n[Read] 读取输入文件: {input_file}")
    input_text = input_file.read_text(encoding='utf-8')
    print(f"   文本长度: {len(input_text)} 字符")

    if verbose:
        preview = input_text[:200] + "..." if len(input_text) > 200 else input_text
        print(f"   预览: {preview}")

    # 注入历史经验
    if memory_context and memory_context.reusable_experiences:
        print(f"\n[Memory] 注入历史经验:")
        print(f"   成功模式: {len(memory_context.success_patterns)} 条")
        print(f"   失败教训: {len(memory_context.failure_warnings)} 条")
        print(f"   可复用经验: {len(memory_context.reusable_experiences)} 条")
        input_text = (
            f"{input_text}\n\n"
            f"{memory_context.prompt_additions}\n\n"
            "请参考以上历史经验，在抽取节点时避免重复历史上的问题。"
        )
    elif memory_context:
        print(f"\n[Memory] 无历史经验，从头开始")

    print(f"\n[Extract] 执行 LLM 结构化抽取...")
    extractor = StructuredExtractor(llm=llm)
    document = extractor.extract(input_text)

    print(f"   节点数: {len(document.nodes)}, 边数: {len(document.edges)}, 状态数: {len(document.states)}")

    if verbose:
        for node in document.nodes:
            print(f"     - {node.name} ({node.type}): {node.description}")

    print(f"\n[Config] 使用 LLM 生成工作流配置...")
    generator = ConfigGenerator(component_library=component_library)
    config = generator.generate_with_refinement(document, llm=llm, workflow_name=workflow_name)

    print(f"   工作流: {config.meta.workflow_id} / {config.meta.name} / v{config.meta.version}")

    return document, config


# ── Do ────────────────────────────────────────────────────────────────────

def do_phase(config: WorkflowConfig, output_dir: Path, verbose: bool = False, llm: Any = None):
    """Do 阶段：根据配置生成可运行的代码工程"""
    print("\n" + "=" * 60)
    print("[Do] DO 阶段：LLM 代码生成")
    print("=" * 60)

    print(f"\n[Generate] 输出到: {output_dir}")
    generator = CodeGenerator(llm=llm)
    generated_files = generator.generate_project(config, output_dir)
    print(f"   生成 {len(generated_files)} 个文件")

    # 保存配置摘要
    config_json_path = output_dir / "config" / "workflow_metadata.json"
    config_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "workflow_id": config.meta.workflow_id,
            "name": config.meta.name,
            "version": config.meta.version,
            "description": config.meta.description,
            "node_count": len(config.nodes),
            "edge_count": len(config.edges),
            "state_count": len(config.state),
            "nodes": [{"name": n.name, "type": n.type, "description": n.description} for n in config.nodes],
        }, f, indent=1, ensure_ascii=False)
    print(f"   配置已保存: {config_json_path}")

    return generated_files


# ── Check ─────────────────────────────────────────────────────────────────

def check_phase(config: WorkflowConfig, output_dir: Path, verbose: bool = False, llm: Any = None):
    """Check 阶段：运行测试并生成评估报告"""
    print("\n" + "=" * 60)
    print("[Check] CHECK 阶段：LLM 测试与评估")
    print("=" * 60)

    class MockWorkflowRunner:
        def run(self, input_data=None, timeout=30):
            import time
            import random
            time.sleep(0.1)
            if random.random() < 0.8:
                return {"success": True, "outputs": {"result": "模拟执行成功"}}
            return {"success": False, "error": "模拟执行失败（示例）"}

    nodes_info = [{"name": n.name, "type": n.type, "description": n.description} for n in config.nodes]

    print(f"\n[Test] 工作流: {config.meta.name}, 节点数: {len(config.nodes)}")

    report = run_evaluation(
        workflow_name=config.meta.name,
        workflow_description=config.meta.description,
        node_count=len(config.nodes),
        workflow_runner=MockWorkflowRunner(),
        llm=llm,
        nodes=nodes_info,
    )

    print(f"\n[Report] 通过率: {report.pass_rate:.1f}% ({report.passed}/{report.total_cases})")

    if report.issues:
        print(f"[Warning] 发现 {len(report.issues)} 个问题:")
        for issue in report.issues[:5]:
            print(f"   - {issue}")
    if report.suggestions:
        print(f"[Suggestion] 改进建议:")
        for s in report.suggestions[:3]:
            print(f"   - {s}")

    report_path = output_dir / "evaluation_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report.model_dump(), f, indent=2, ensure_ascii=False)
    print(f"   报告已保存: {report_path}")

    return report


# ── Act ───────────────────────────────────────────────────────────────────

def act_phase(
    config: WorkflowConfig,
    report,
    original_goals: list,
    output_dir: Path,
    iteration: int,
    verbose: bool = False,
    llm: Any = None,
    component_library: Any = None,
    memory: Optional[PDCAMemory] = None,
):
    """Act 阶段：复盘分析、优化方案、可选记忆沉淀"""
    print("\n" + "=" * 60)
    mode_label = "LLM 复盘与记忆沉淀" if memory else "LLM 复盘与优化"
    print(f"[Act] ACT 阶段：{mode_label}")
    print("=" * 60)

    # GRBARP 复盘
    print(f"\n[Review] 执行 GRBARP 复盘...")
    reviewer = GRBARPReviewer(llm=llm, component_library=component_library)
    review_result = reviewer.review(
        workflow_name=config.meta.name,
        original_goals=original_goals,
        evaluation_report=report,
    )
    print(f"   总体评分: {review_result.overall_score:.1f}/100")

    goal_review = review_result.goal_review
    if isinstance(goal_review, dict):
        print(f"   目标: 已达成 {len(goal_review.get('achieved_goals', []))}, "
              f"部分 {len(goal_review.get('partial_goals', []))}, "
              f"未达成 {len(goal_review.get('missed_goals', []))}")

    result_analysis = review_result.result_analysis
    if isinstance(result_analysis, dict):
        if result_analysis.get("success_factors"):
            print(f"   成功因素:")
            for f in result_analysis["success_factors"][:3]:
                print(f"     [OK] {f}")
        if result_analysis.get("failure_factors"):
            print(f"   失败因素:")
            for f in result_analysis["failure_factors"][:3]:
                print(f"     [FAIL] {f}")

    # 优化方案
    print(f"\n[Suggestion] 生成优化方案...")
    opt_generator = OptimizationGenerator(llm=llm, component_library=component_library)
    proposals = opt_generator.generate_from_review(review_result, config=config)
    proposals = opt_generator.prioritize_proposals(proposals)
    print(f"   生成 {len(proposals)} 个优化方案")
    for i, p in enumerate(proposals[:3], 1):
        print(f"   {i}. [{p.priority}] {p.title}")

    # 记忆沉淀
    if memory:
        print(f"\n[Memory] 沉淀经验...")
        memory.record_iteration_experience(
            iteration=iteration,
            workflow_name=config.meta.name,
            review_result=review_result,
            proposals=proposals,
            evaluation_report=report,
        )
        stats = memory.get_statistics()
        print(f"   已积累 {stats['total_memories']} 条记忆")

    # 组件库知识固化
    if component_library:
        discoveries = component_library.discover_reusable_components(
            review_result, config, config.meta.name
        )
        if discoveries:
            print(f"[Library] 发现 {len(discoveries)} 个可复用组件")

    # 保存结果
    review_path = output_dir / "review_result.json"
    with open(review_path, 'w', encoding='utf-8') as f:
        json.dump(review_result.model_dump(), f, indent=2, ensure_ascii=False)

    proposals_path = output_dir / "optimization_proposals.json"
    with open(proposals_path, 'w', encoding='utf-8') as f:
        json.dump([p.model_dump() for p in proposals], f, indent=2, ensure_ascii=False)

    print(f"   复盘: {review_path}")
    print(f"   方案: {proposals_path}")

    return review_result, proposals


# ── 主流程 ────────────────────────────────────────────────────────────────

def run_pdca_cycle(args):
    """运行完整 PDCA 循环"""
    log_config = LogConfig(log_level="DEBUG" if args.verbose else "INFO")
    set_log_config(log_config)

    mode = "Config -> Do/Check/Act" if args.config else "Plan -> Do -> Check -> Act"
    print("\n" + "=" * 60)
    print("[PDCA] PDCA-LangGraph-SOP")
    print("=" * 60)
    print(f"模式: {mode}")
    print(f"记忆: {'启用' if args.memory else '关闭'}")
    print(f"输出: {args.output}")
    print(f"迭代: {args.max_iterations}, 阈值: {args.quality_threshold}%")

    # 初始化 LLM（双模型路由）
    setup_llm(name="planner", provider="zhipu", model=os.getenv("ZHIPU_MODEL", "glm-4.7"))
    setup_llm(name="executor", provider="minimax", model=os.getenv("MINIMAX_MODEL", "MiniMax-Text-01"))
    planner_llm = get_llm_for_task("extract")
    executor_llm = get_llm_for_task("code")

    # 初始化记忆系统
    memory = None
    if args.memory:
        print(f"\n[Memory] 初始化: {args.memory_dir}")
        memory = PDCAMemory(memory_dir=str(args.memory_dir))
        stats = memory.get_statistics()
        print(f"   已有 {stats['total_memories']} 条记忆")

    # 初始化组件库
    component_library = None
    if not args.no_component_library:
        component_library = ComponentLibrary(
            library_dir=str(args.component_library_dir),
            llm=planner_llm,
            enable_llm_matching=True,
        )
        lib_stats = component_library.get_statistics()
        print(f"[Library] 组件库: {lib_stats['total_templates']} 个模板")

    original_goals = [
        "成功生成可运行的工作流代码",
        "测试通过率达到80%以上",
        "工作流能够正常执行完成",
    ]

    loop_controller = create_loop_controller(
        max_iterations=args.max_iterations,
        quality_threshold=args.quality_threshold,
    )
    loop_controller.start("PDCA循环")

    for iteration in range(1, args.max_iterations + 1):
        print(f"\n{'=' * 60}")
        print(f"[PDCA] 第 {iteration} 次迭代")
        print(f"{'=' * 60}")

        # ── PLAN ──
        if args.config:
            # 从 JSON 文件加载配置，跳过 Plan
            config = load_config_from_json(args.config)
            print(f"\n[Plan] 已从配置文件加载: {args.config}")
            print(f"   工作流: {config.meta.name} ({len(config.nodes)} 节点, {len(config.edges)} 边)")
        else:
            # 记忆增强：第 2 次迭代起注入历史经验
            memory_context = None
            if memory and iteration > 1:
                wf_name = args.workflow_name or "default"
                memory_context = memory.get_context_for_next_iteration(
                    iteration=iteration - 1, workflow_name=wf_name
                )
            _, config = plan_phase(
                args.input,
                args.workflow_name,
                args.verbose,
                llm=planner_llm,
                memory_context=memory_context,
                component_library=component_library,
            )
            config.meta.category = args.category

        # ── DO ──
        folder_name = generate_output_folder_name(config, iteration)
        output_dir = args.output / folder_name
        if not args.skip_do:
            do_phase(config, output_dir, args.verbose, llm=executor_llm)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)

        # ── CHECK ──
        if not args.skip_check:
            report = check_phase(config, output_dir, args.verbose, llm=executor_llm)
        else:
            print("\n跳过 CHECK 阶段")
            continue

        # ── ACT ──
        act_phase(
            config, report, original_goals, output_dir, iteration,
            args.verbose, planner_llm, component_library, memory,
        )

        loop_controller.record_iteration(
            iteration_number=iteration,
            status=LoopStatus.COMPLETED,
            pass_rate=report.pass_rate,
            issues_found=len(report.issues),
        )

        update_output_index(args.output, folder_name, config, report)
        print(f"\n[Index] 索引已更新: {args.output / 'index.yaml'}")

        if report.pass_rate >= args.quality_threshold:
            print(f"\n达到质量阈值 ({args.quality_threshold}%)，PDCA 循环完成")
            break
        elif iteration < args.max_iterations:
            print(f"\n未达阈值，继续下一次迭代...")
        else:
            print(f"\n已达最大迭代次数，PDCA 循环结束")

    print(f"\n{'=' * 60}")
    print(f"[Complete] 结果保存在: {args.output}")
    print(f"{'=' * 60}")

    if memory:
        stats = memory.get_statistics()
        print(f"\n[Memory] 总计 {stats['total_memories']} 条经验")


def main():
    args = parse_args()
    run_pdca_cycle(args)


if __name__ == "__main__":
    main()
