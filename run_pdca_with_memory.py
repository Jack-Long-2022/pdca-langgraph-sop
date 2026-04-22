"""PDCA 完整循环执行脚本（带记忆系统版本）

与 run_pdca.py 的区别：
1. 使用 PDCAMemory 积累每次迭代的经验
2. Act 阶段自动将经验存入记忆系统
3. Plan 阶段自动读取历史经验用于上下文增强
4. 支持跨工作流的模式识别

使用方法：
    python run_pdca_with_memory.py --input examples/input.md --output examples/output

工作流程：
1. Plan: 读取记忆 -> 结构化抽取 -> 生成工作流配置
2. Do: 根据配置生成可运行的代码工程
3. Check: 运行测试验收，生成评估报告
4. Act: 复盘分析，生成优化方案 -> 存入记忆
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Any
from dotenv import load_dotenv

load_dotenv()

from pdca.core.llm import setup_llm, get_llm_manager, get_llm_for_task
from pdca.core.logger import setup_logging, get_logger, LogConfig, set_log_config
from pdca.core.memory import PDCAMemory, MemoryContext
from pdca.core.component_library import ComponentLibrary
from pdca.plan.extractor import StructuredExtractor
from pdca.plan.config_generator import ConfigGenerator
from pdca.do_.code_generator import CodeGenerator
from pdca.check.evaluator import run_evaluation
from pdca.act.reviewer import GRBARPReviewer, OptimizationGenerator
from pdca.act.loop_controller import create_loop_controller


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="PDCA-LangGraph-SOP with Memory - 完整PDCA循环执行"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="输入文件路径"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("generated_workflow"),
        help="输出目录路径"
    )
    parser.add_argument(
        "--workflow-name",
        default=None,
        help="工作流名称"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=2,
        help="最大PDCA循环迭代次数"
    )
    parser.add_argument(
        "--quality-threshold",
        type=float,
        default=80.0,
        help="质量阈值"
    )
    parser.add_argument(
        "--skip-do",
        action="store_true",
        help="跳过Do阶段"
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="跳过Check阶段"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出"
    )
    parser.add_argument(
        "--memory-dir",
        type=Path,
        default=Path(".pdca_memory"),
        help="记忆系统存储目录"
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="禁用记忆系统（不使用历史经验）"
    )
    parser.add_argument(
        "--component-library-dir",
        type=Path,
        default=Path(".pdca_components"),
        help="组件库存储目录"
    )
    parser.add_argument(
        "--no-component-library",
        action="store_true",
        help="禁用组件库"
    )

    return parser.parse_args()


def plan_phase(
    input_file: Path,
    workflow_name: str = None,
    verbose: bool = False,
    llm: Any = None,
    memory_context: MemoryContext = None,
    component_library: Any = None
):
    """Plan阶段：记忆增强的结构化抽取与配置生成

    与 run_pdca.py 的区别：
    - 读取 memory_context 中的历史经验
    - 将历史经验注入到 LLM prompt 中
    - 抽取时参考历史成功/失败模式
    - 支持组件库查找复用（新增）

    Args:
        memory_context: 来自记忆系统的历史上下文
        component_library: 可复用组件库（新增）

    Returns:
        (StructuredDocument, WorkflowConfig, enhanced_prompt)
    """
    logger = get_logger(__name__)
    print("\n" + "="*60)
    print("[Plan] PLAN 阶段：记忆增强的结构化抽取")
    print("="*60)

    # 1. 读取输入文件
    print(f"\n[Read] 读取输入文件: {input_file}")
    input_text = input_file.read_text(encoding='utf-8')
    print(f"   文本长度: {len(input_text)} 字符")

    # 2. 读取记忆上下文（新增）
    if memory_context and not memory_context.reusable_experiences:
        print(f"\n[Memory] 无历史经验，从头开始")
    elif memory_context:
        print(f"\n[Memory] 读取历史经验:")
        print(f"   - 成功模式: {len(memory_context.success_patterns)} 条")
        print(f"   - 失败教训: {len(memory_context.failure_warnings)} 条")
        print(f"   - 可复用经验: {len(memory_context.reusable_experiences)} 条")

    # 3. LLM结构化抽取（带记忆增强）
    print(f"\n[Extract] 执行记忆增强的LLM结构化抽取...")
    extractor = StructuredExtractor(llm=llm)
    
    # 如果有记忆上下文，将其传给抽取器
    enhanced_prompt = ""
    if memory_context:
        enhanced_prompt = memory_context.prompt_additions
        # 增强输入文本
        input_text = f"""{input_text}

{enhanced_prompt}

请参考以上历史经验，在抽取节点时避免重复历史上的问题。
"""
    
    document = extractor.extract(input_text)

    print(f"   [OK] 抽取完成:")
    print(f"     - 节点数: {len(document.nodes)}")
    print(f"     - 边数: {len(document.edges)}")
    print(f"     - 状态数: {len(document.states)}")

    if verbose and memory_context:
        print(f"\n   记忆增强提示已注入")

    # 4. 使用LLM生成工作流配置
    print(f"\n[Config] 使用LLM生成工作流配置...")
    generator = ConfigGenerator(component_library=component_library)

    config = generator.generate_with_refinement(
        document,
        llm=llm,
        workflow_name=workflow_name
    )

    print(f"   [OK] 配置生成完成:")
    print(f"     - 工作流ID: {config.meta.workflow_id}")
    print(f"     - 名称: {config.meta.name}")
    print(f"     - 版本: {config.meta.version}")

    return document, config, enhanced_prompt


def do_phase(config, output_dir: Path, verbose: bool = False, llm: Any = None):
    """Do阶段：根据配置生成可运行的代码工程（与 run_pdca.py 相同）"""
    logger = get_logger(__name__)
    print("\n" + "="*60)
    print("[Do] DO 阶段：LLM代码生成")
    print("="*60)

    print(f"\n[Dir] 输出目录: {output_dir}")

    print(f"\n[Generate] 使用LLM生成项目代码...")
    generator = CodeGenerator(llm=llm)
    generated_files = generator.generate_project(config, output_dir)

    print(f"   [OK] 代码生成完成，共生成 {len(generated_files)} 个文件:")
    for filename, filepath in list(generated_files.items())[:5]:
        rel_path = filepath.relative_to(output_dir)
        print(f"     - {rel_path}")

    # 保存配置JSON
    config_json_path = output_dir / "config" / "workflow_metadata.json"
    config_json_path.parent.mkdir(parents=True, exist_ok=True)
    
    nodes_info = [
        {"name": n.name, "type": n.type, "description": n.description}
        for n in config.nodes
    ]
    
    with open(config_json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "workflow_id": config.meta.workflow_id,
            "name": config.meta.name,
            "version": config.meta.version,
            "description": config.meta.description,
            "node_count": len(config.nodes),
            "edge_count": len(config.edges),
            "state_count": len(config.state),
            "nodes": nodes_info
        }, f, indent=1, ensure_ascii=False)

    print(f"\n[Check] DO阶段完成！项目已生成到: {output_dir}")

    return generated_files


def check_phase(config, output_dir: Path, verbose: bool = False, llm: Any = None):
    """Check阶段：运行测试并生成评估报告（与 run_pdca.py 相同）"""
    logger = get_logger(__name__)
    print("\n" + "="*60)
    print("[Check] CHECK 阶段：LLM测试与评估")
    print("="*60)

    class MockWorkflowRunner:
        def run(self, input_data=None, timeout=30):
            import time
            time.sleep(0.1)
            import random
            success = random.random() < 0.8
            if success:
                return {"success": True, "outputs": {"result": "模拟执行成功"}}
            else:
                return {"success": False, "error": "模拟执行失败（示例）"}

    runner = MockWorkflowRunner()

    nodes_info = [
        {"name": n.name, "type": n.type, "description": n.description}
        for n in config.nodes
    ]

    print(f"\n[Test] 使用LLM运行测试评估...")
    print(f"   工作流: {config.meta.name}")
    print(f"   节点数: {len(config.nodes)}")

    report = run_evaluation(
        workflow_name=config.meta.name,
        workflow_description=config.meta.description,
        node_count=len(config.nodes),
        workflow_runner=runner,
        llm=llm,
        nodes=nodes_info
    )

    print(f"\n[Report] 评估结果:")
    print(f"   总用例数: {report.total_cases}")
    print(f"   通过: {report.passed}")
    print(f"   失败: {report.failed}")
    print(f"   错误: {report.errors}")
    print(f"   通过率: {report.pass_rate:.1f}%")

    if report.issues:
        print(f"\n[Warning] 发现问题:")
        for issue in report.issues[:5]:
            print(f"   - {issue}")

    # 保存报告
    report_path = output_dir / "evaluation_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report.model_dump(), f, indent=2, ensure_ascii=False)

    print(f"\n[File] 评估报告已保存: {report_path}")

    return report


def act_phase(
    config, 
    report, 
    original_goals, 
    output_dir: Path, 
    verbose: bool = False, 
    llm: Any = None
):
    """Act阶段：复盘分析并生成优化方案（与 run_pdca.py 相同）"""
    logger = get_logger(__name__)
    print("\n" + "="*60)
    print("[Act] ACT 阶段：LLM复盘与优化")
    print("="*60)

    print(f"\n[Review] 使用LLM执行GR/RAVP复盘...")
    reviewer = GRBARPReviewer(llm=llm)

    review_result = reviewer.review(
        workflow_name=config.meta.name,
        original_goals=original_goals,
        evaluation_report=report
    )

    print(f"\n[Analysis] 复盘结果:")
    print(f"   总体评分: {review_result.overall_score:.1f}/100")
    print(f"   复盘日期: {review_result.review_date}")

    # 保存复盘结果
    review_path = output_dir / "review_result.json"
    with open(review_path, 'w', encoding='utf-8') as f:
        json.dump(review_result.model_dump(), f, indent=2, ensure_ascii=False)

    # 生成优化方案
    print(f"\n[Suggestion] 使用LLM生成优化方案...")
    opt_generator = OptimizationGenerator(llm=llm)
    proposals = opt_generator.generate_from_review(review_result)
    proposals = opt_generator.prioritize_proposals(proposals)

    print(f"   [OK] 生成了 {len(proposals)} 个优化方案:")
    for i, proposal in enumerate(proposals[:3], 1):
        print(f"\n   方案 {i}: {proposal.title}")
        print(f"     优先级: {proposal.priority}")

    proposals_path = output_dir / "optimization_proposals.json"
    with open(proposals_path, 'w', encoding='utf-8') as f:
        json.dump([p.model_dump() for p in proposals], f, indent=2, ensure_ascii=False)

    print(f"\n[File] 复盘结果已保存: {review_path}")
    print(f"[File] 优化方案已保存: {proposals_path}")

    return review_result, proposals


def act_phase_with_memory(
    config,
    report,
    original_goals,
    output_dir: Path,
    iteration: int,
    verbose: bool = False,
    llm: Any = None,
    memory: PDCAMemory = None,
    component_library: Any = None
):
    """Act阶段（记忆增强版）：复盘 + 存入记忆 + 知识固化

    与普通 act_phase 的区别：
    - 完成后自动将经验存入 PDCAMemory
    - 保存成功因素、失败教训、优化方案到记忆系统
    - 组件库知识固化（新增）
    """
    logger = get_logger(__name__)
    print("\n" + "="*60)
    print("[Act] ACT 阶段：LLM复盘与记忆沉淀")
    print("="*60)

    # 1. 执行复盘（与普通版相同）
    print(f"\n[Review] 使用LLM执行GR/RAVP复盘...")
    reviewer = GRBARPReviewer(llm=llm, component_library=component_library)

    review_result = reviewer.review(
        workflow_name=config.meta.name,
        original_goals=original_goals,
        evaluation_report=report
    )

    print(f"\n[Analysis] 复盘结果:")
    print(f"   总体评分: {review_result.overall_score:.1f}/100")

    # 2. 生成优化方案
    print(f"\n[Suggestion] 使用LLM生成优化方案...")
    opt_generator = OptimizationGenerator(llm=llm, component_library=component_library)
    proposals = opt_generator.generate_from_review(review_result, config=config)
    proposals = opt_generator.prioritize_proposals(proposals)

    print(f"   [OK] 生成了 {len(proposals)} 个优化方案")

    # 3. 【新增】存入记忆系统
    if memory:
        print(f"\n[Memory] 存入记忆系统...")
        memory.record_iteration_experience(
            iteration=iteration,
            workflow_name=config.meta.name,
            review_result=review_result,
            proposals=proposals,
            evaluation_report=report
        )
        print(f"   经验已沉淀到记忆系统")

        # 打印记忆统计
        stats = memory.get_statistics()
        print(f"   记忆统计: {stats['total_memories']} 条记忆, {stats['workflows_tracked']} 个工作流")

    # 3.5 【新增】组件库知识固化
    if component_library:
        print(f"\n[Library] 执行知识固化...")
        discoveries = component_library.discover_reusable_components(
            review_result, config, config.meta.name
        )
        if discoveries:
            print(f"   发现 {len(discoveries)} 个可复用组件，已保存到组件库")

    # 4. 保存结果
    review_path = output_dir / "review_result.json"
    with open(review_path, 'w', encoding='utf-8') as f:
        json.dump(review_result.model_dump(), f, indent=2, ensure_ascii=False)

    proposals_path = output_dir / "optimization_proposals.json"
    with open(proposals_path, 'w', encoding='utf-8') as f:
        json.dump([p.model_dump() for p in proposals], f, indent=2, ensure_ascii=False)

    print(f"\n[File] 复盘结果已保存: {review_path}")
    print(f"[File] 优化方案已保存: {proposals_path}")

    return review_result, proposals


def run_pdca_cycle(args):
    """运行完整的PDCA循环（记忆增强版）"""
    log_config = LogConfig(log_level="DEBUG" if args.verbose else "INFO")
    set_log_config(log_config)
    logger = get_logger(__name__)

    print("\n" + "="*60)
    print("[PDCA] PDCA-LangGraph-SOP 记忆增强版")
    print("="*60)
    print(f"输入文件: {args.input}")
    print(f"输出目录: {args.output}")
    print(f"最大迭代: {args.max_iterations}")
    print(f"质量阈值: {args.quality_threshold}%")

    # 初始化LLM（双模型）
    setup_llm(name="planner", provider="zhipu", model=os.getenv("ZHIPU_MODEL", "glm-4.7"))
    setup_llm(name="executor", provider="minimax", model=os.getenv("MINIMAX_MODEL", "MiniMax-Text-01"))
    planner_llm = get_llm_for_task("extract")
    executor_llm = get_llm_for_task("code")

    # 【新增】初始化记忆系统
    use_memory = not args.no_memory
    memory = None
    memory_context = None
    
    if use_memory:
        print(f"\n[Memory] 初始化记忆系统: {args.memory_dir}")
        memory = PDCAMemory(memory_dir=str(args.memory_dir))
        stats = memory.get_statistics()
        print(f"   已积累: {stats['total_memories']} 条记忆")
        
        # 如果有历史，显示总结
        if stats['total_memories'] > 0:
            print(f"   记忆系统已就绪，将用于增强本轮迭代")

    # 初始化组件库
    component_library = None
    if not args.no_component_library:
        component_library = ComponentLibrary(
            library_dir=str(args.component_library_dir),
            llm=planner_llm,
            enable_llm_matching=False,
        )
        lib_stats = component_library.get_statistics()
        print(f"\n[Library] 组件库初始化: {lib_stats['total_templates']} 个模板")

    # 定义目标
    original_goals = [
        "成功生成可运行的工作流代码",
        "测试通过率达到80%以上",
        "工作流能够正常执行完成"
    ]

    # 创建循环控制器（纯规则判断）
    loop_controller = create_loop_controller(
        max_iterations=args.max_iterations,
        quality_threshold=args.quality_threshold
    )
    loop_controller.start("PDCA循环")

    # 迭代执行PDCA
    for iteration in range(1, args.max_iterations + 1):
        print(f"\n{'='*60}")
        print(f"[PDCA] 第 {iteration} 次PDCA迭代")
        print(f"{'='*60}")

        # 【关键变化】获取记忆上下文
        workflow_name_for_memory = args.workflow_name or "default"
        if memory and iteration > 1:
            print(f"\n[Memory] 读取第 {iteration-1} 轮的经验...")
            memory_context = memory.get_context_for_next_iteration(
                iteration=iteration - 1,
                workflow_name=workflow_name_for_memory
            )
            if memory_context.reusable_experiences:
                print(f"   找到 {len(memory_context.reusable_experiences)} 条可用经验")
        else:
            memory_context = None

        # === PLAN ===
        document, config, enhanced_prompt = plan_phase(
            args.input,
            args.workflow_name,
            args.verbose,
            llm=planner_llm,
            memory_context=memory_context,
            component_library=component_library
        )

        # === DO ===
        if not args.skip_do:
            output_dir = args.output / f"iteration_{iteration}"
            generated_files = do_phase(config, output_dir, args.verbose, llm=executor_llm)
        else:
            output_dir = args.output / f"iteration_{iteration}"
            output_dir.mkdir(parents=True, exist_ok=True)

        # === CHECK ===
        if not args.skip_check:
            report = check_phase(config, output_dir, args.verbose, llm=executor_llm)
        else:
            print("\n⏭️  跳过CHECK阶段")
            continue

        # === ACT ===
        # 使用记忆增强版的 act_phase
        if memory:
            review_result, proposals = act_phase_with_memory(
                config,
                report,
                original_goals,
                output_dir,
                iteration,
                args.verbose,
                llm=planner_llm,
                memory=memory,
                component_library=component_library
            )
        else:
            review_result, proposals = act_phase(
                config,
                report,
                original_goals,
                output_dir,
                args.verbose,
                llm=planner_llm
            )

        # 记录迭代
        loop_controller.record_iteration(
            iteration_number=iteration,
            status="completed",
            pass_rate=report.pass_rate,
            issues_found=len(report.issues)
        )

        # 检查是否达到质量阈值
        if report.pass_rate >= args.quality_threshold:
            print(f"\n✅ 达到质量阈值 ({args.quality_threshold}%)，PDCA循环完成！")
            break
        elif iteration < args.max_iterations:
            print(f"\n⚠️ 未达到质量阈值，继续下一次迭代...")
        else:
            print(f"\n⚠️ 已达到最大迭代次数，PDCA循环结束")

    print(f"\n{'='*60}")
    print("[Complete] PDCA循环执行完成！")
    print(f"{'='*60}")
    print(f"结果保存在: {args.output}")
    
    # 打印记忆系统统计
    if memory:
        print(f"\n[Memory] 记忆系统统计:")
        stats = memory.get_statistics()
        for category, count in stats['by_category'].items():
            print(f"   - {category}: {count} 条")
        print(f"   总计: {stats['total_memories']} 条经验")


def main():
    """主入口"""
    args = parse_args()
    run_pdca_cycle(args)


if __name__ == "__main__":
    main()