"""PDCA完整循环执行脚本

使用方法：
    python run_pdca.py --input examples/input.md --output examples/output

工作流程：
1. Plan: 读取输入文件 -> 结构化抽取 -> 生成工作流配置
2. Do: 根据配置生成可运行的代码工程
3. Check: 运行测试验收，生成评估报告
4. Act: 复盘分析，生成优化方案
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from typing import Any
from pdca.core.llm import setup_llm, get_llm_manager, get_llm_for_task
from pdca.core.logger import setup_logging, get_logger, LogConfig, set_log_config
from pdca.plan.extractor import StructuredExtractor
from pdca.plan.config_generator import ConfigGenerator
from pdca.do_.code_generator import CodeGenerator
from pdca.check.evaluator import run_evaluation
from pdca.act.reviewer import GRRAVPReviewer, OptimizationGenerator
from pdca.act.loop_controller import create_loop_controller


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="PDCA-LangGraph-SOP - 完整PDCA循环执行"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="输入文件路径（markdown格式的语音转文字内容）"
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
        help="工作流名称（默认从输入文件推断）"
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
        help="质量阈值（通过率百分比）"
    )
    parser.add_argument(
        "--skip-do",
        action="store_true",
        help="跳过Do阶段（代码生成）"
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="跳过Check阶段（测试评估）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出"
    )

    return parser.parse_args()


def plan_phase(input_file: Path, workflow_name: str = None, verbose: bool = False, llm: Any = None):
    """Plan阶段：从输入文本生成工作流配置

    步骤：
    1. 读取输入文件
    2. 使用StructuredExtractor进行LLM结构化抽取
    3. 使用ConfigGenerator生成WorkflowConfig

    Args:
        input_file: 输入文件路径
        workflow_name: 工作流名称
        verbose: 是否详细输出
        llm: LLM实例

    Returns:
        (StructuredDocument, WorkflowConfig)
    """
    logger = get_logger(__name__)
    print("\n" + "="*60)
    print("[Plan] PLAN 阶段：LLM结构化抽取与配置生成")
    print("="*60)

    # 1. 读取输入文件
    print(f"\n[Read] 读取输入文件: {input_file}")
    input_text = input_file.read_text(encoding='utf-8')
    print(f"   文本长度: {len(input_text)} 字符")

    if verbose:
        print(f"\n[File] 输入内容预览:")
        print("   " + input_text[:200] + "..." if len(input_text) > 200 else "   " + input_text)

    # 2. LLM结构化抽取
    print(f"\n[Extract] 执行LLM结构化抽取...")
    extractor = StructuredExtractor(llm=llm)
    document = extractor.extract(input_text)

    print(f"   [OK] 抽取完成:")
    print(f"     - 节点数: {len(document.nodes)}")
    print(f"     - 边数: {len(document.edges)}")
    print(f"     - 状态数: {len(document.states)}")

    if verbose:
        print(f"\n   节点详情:")
        for node in document.nodes:
            print(f"     - {node.name} ({node.type}): {node.description}")

    # 3. 使用LLM生成工作流配置
    print(f"\n[Config] 使用LLM生成工作流配置...")
    generator = ConfigGenerator()

    # 使用LLM细化生成
    config = generator.generate_with_refinement(
        document,
        llm=llm,
        workflow_name=workflow_name
    )

    print(f"   [OK] 配置生成完成:")
    print(f"     - 工作流ID: {config.meta.workflow_id}")
    print(f"     - 名称: {config.meta.name}")
    print(f"     - 版本: {config.meta.version}")

    return document, config


def do_phase(config, output_dir: Path, verbose: bool = False, llm: Any = None):
    """Do阶段：根据配置生成可运行的代码工程

    步骤：
    1. 创建输出目录
    2. 使用LLM CodeGenerator生成项目代码
    3. 保存配置文件

    Args:
        config: WorkflowConfig实例
        output_dir: 输出目录
        verbose: 是否详细输出
        llm: LLM实例

    Returns:
        生成的文件映射字典
    """
    logger = get_logger(__name__)
    print("\n" + "="*60)
    print("[Do] DO 阶段：LLM代码生成")
    print("="*60)

    print(f"\n[Dir] 输出目录: {output_dir}")

    # 使用LLM生成代码
    print(f"\n[Generate] 使用LLM生成项目代码...")
    generator = CodeGenerator(llm=llm)
    generated_files = generator.generate_project(config, output_dir)

    print(f"   [OK] 代码生成完成，共生成 {len(generated_files)} 个文件:")
    for filename, filepath in generated_files.items():
        rel_path = filepath.relative_to(output_dir)
        print(f"     - {rel_path}")

    # 保存配置JSON
    config_json_path = output_dir / "config" / "workflow_metadata.json"
    config_json_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 构建节点信息用于传递
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
    """Check阶段：运行测试并生成评估报告

    步骤：
    1. 使用LLM生成测试用例
    2. 执行测试
    3. 使用LLM生成评估报告

    Args:
        config: WorkflowConfig实例
        output_dir: 输出目录
        verbose: 是否详细输出
        llm: LLM实例

    Returns:
        EvaluationReport实例
    """
    logger = get_logger(__name__)
    print("\n" + "="*60)
    print("[Check] CHECK 阶段：LLM测试与评估")
    print("="*60)

    # 创建模拟的工作流运行器
    class MockWorkflowRunner:
        """模拟工作流运行器（用于演示）"""

        def run(self, input_data=None, timeout=30):
            """模拟运行"""
            import time
            time.sleep(0.1)

            import random
            success = random.random() < 0.8

            if success:
                return {
                    "success": True,
                    "outputs": {"result": "模拟执行成功"}
                }
            else:
                return {
                    "success": False,
                    "error": "模拟执行失败（示例）"
                }

    runner = MockWorkflowRunner()

    # 构建节点信息
    nodes_info = [
        {"name": n.name, "type": n.type, "description": n.description}
        for n in config.nodes
    ]
    edges_info = [
        {"source": e.source, "target": e.target, "type": e.type}
        for e in config.edges
    ]

    print(f"\n[Test] 使用LLM运行测试评估...")
    print(f"   工作流: {config.meta.name}")
    print(f"   节点数: {len(config.nodes)}")

    # 运行LLM增强的评估
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
    print(f"   执行时间: {report.execution_time:.2f}秒")

    if report.issues:
        print(f"\n[Warning] 发现问题:")
        for issue in report.issues[:5]:
            print(f"   - {issue}")

    if report.suggestions:
        print(f"\n[Suggestion] 改进建议:")
        for suggestion in report.suggestions[:5]:
            print(f"   - {suggestion}")

    # 保存报告
    report_path = output_dir / "evaluation_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report.model_dump(), f, indent=2, ensure_ascii=False)

    print(f"\n[File] 评估报告已保存: {report_path}")

    return report


def act_phase(config, report, original_goals, output_dir: Path, verbose: bool = False, llm: Any = None):
    """Act阶段：复盘分析并生成优化方案

    步骤：
    1. 使用LLM执行GR/RAVP复盘
    2. 使用LLM生成优化方案
    3. 输出改进建议

    Args:
        config: WorkflowConfig实例
        report: EvaluationReport实例
        original_goals: 原始目标列表
        output_dir: 输出目录
        verbose: 是否详细输出
        llm: LLM实例

    Returns:
        (GRRAVPReviewResult, list[OptimizationProposal])
    """
    logger = get_logger(__name__)
    print("\n" + "="*60)
    print("[Act] ACT 阶段：LLM复盘与优化")
    print("="*60)

    # 使用LLM执行复盘
    print(f"\n[Review] 使用LLM执行GR/RAVP复盘...")
    reviewer = GRRAVPReviewer(llm=llm)

    review_result = reviewer.review(
        workflow_name=config.meta.name,
        original_goals=original_goals,
        evaluation_report=report
    )

    print(f"\n[Analysis] 复盘结果:")
    print(f"   总体评分: {review_result.overall_score:.1f}/100")
    print(f"   复盘日期: {review_result.review_date}")

    print(f"\n[Goal] 目标回顾:")
    goal_review = review_result.goal_review
    if isinstance(goal_review, dict):
        if goal_review.get("achieved_goals"):
            print(f"   已达成: {len(goal_review.get('achieved_goals', []))} 个")
        if goal_review.get("partial_goals"):
            print(f"   部分达成: {len(goal_review.get('partial_goals', []))} 个")
        if goal_review.get("missed_goals"):
            print(f"   未达成: {len(goal_review.get('missed_goals', []))} 个")

    print(f"\n[Report] 结果分析:")
    result_analysis = review_result.result_analysis
    if isinstance(result_analysis, dict):
        if result_analysis.get("success_factors"):
            print(f"   成功因素:")
            for factor in result_analysis.get("success_factors", [])[:3]:
                print(f"     [OK] {factor}")
        if result_analysis.get("failure_factors"):
            print(f"   失败因素:")
            for factor in result_analysis.get("failure_factors", [])[:3]:
                print(f"     [FAIL] {factor}")

    # 使用LLM生成优化方案
    print(f"\n[Suggestion] 使用LLM生成优化方案...")
    opt_generator = OptimizationGenerator(llm=llm)
    proposals = opt_generator.generate_from_review(review_result)
    proposals = opt_generator.prioritize_proposals(proposals)

    print(f"   [OK] 生成了 {len(proposals)} 个优化方案:")
    for i, proposal in enumerate(proposals[:3], 1):
        print(f"\n   方案 {i}: {proposal.title}")
        print(f"     优先级: {proposal.priority}")
        print(f"     预期收益: {', '.join(proposal.expected_benefits[:2]) if proposal.expected_benefits else '无'}")
        if proposal.implementation_steps:
            print(f"     实施步骤:")
            for step in proposal.implementation_steps[:3]:
                print(f"       - {step}")

    print(f"\n[Plan] 总体建议:")
    for rec in review_result.recommendations[:3]:
        print(f"   - {rec}")

    print(f"\n[Next]  下一步行动:")
    for step in review_result.next_steps[:3]:
        print(f"   - {step}")

    # 保存复盘结果
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
    """运行完整的PDCA循环

    Args:
        args: 命令行参数
    """
    # 设置日志
    log_config = LogConfig(log_level="DEBUG" if args.verbose else "INFO")
    set_log_config(log_config)
    logger = get_logger(__name__)

    print("\n" + "="*60)
    print("[PDCA] PDCA-LangGraph-SOP LLM驱动的自动化工作流生成")
    print("="*60)
    print(f"输入文件: {args.input}")
    print(f"输出目录: {args.output}")
    print(f"最大迭代: {args.max_iterations}")
    print(f"质量阈值: {args.quality_threshold}%")

    # 初始化LLM（双模型：Planner用智谱强模型，Executor用MiniMax轻模型）
    setup_llm(name="planner", provider="zhipu", model="glm-4.7")
    setup_llm(name="executor", provider="minimax", model="MiniMax-Text-01")

    planner_llm = get_llm_for_task("extract")  # 会路由到 planner
    executor_llm = get_llm_for_task("code")    # 会路由到 executor

    # 定义目标
    original_goals = [
        "成功生成可运行的工作流代码",
        "测试通过率达到80%以上",
        "工作流能够正常执行完成"
    ]

    # 创建循环控制器（纯规则判断，不调LLM）
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

        # === PLAN ===
        document, config = plan_phase(
            args.input,
            args.workflow_name,
            args.verbose,
            llm=planner_llm
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


def main():
    """主入口"""
    args = parse_args()
    run_pdca_cycle(args)


if __name__ == "__main__":
    main()