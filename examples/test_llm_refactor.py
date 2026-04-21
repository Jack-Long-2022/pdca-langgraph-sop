#!/usr/bin/env python3
"""验证脚本 - 测试LLM重构后的代码是否能正常运行

场景1: 测试结构化抽取 (Plan阶段)
场景2: 测试配置生成 (Plan阶段)  
场景3: 测试代码生成 (Do阶段)
场景4: 测试评估器 (Check阶段)
场景5: 测试复盘器 (Act阶段)
场景6: 测试完整PDCA循环

使用方法:
    cd pdca-langgraph-sop
    python examples/test_llm_refactor.py
"""

import sys
import os
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

# 尝试加载dotenv，如果失败则跳过
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 设置必要的环境变量（如果.env不存在）
os.environ.setdefault("ZHIPU_API_KEY", os.environ.get("ZHIPU_API_KEY", ""))
os.environ.setdefault("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")

from pdca.core.llm import setup_llm, get_llm_manager


def setup_llm_once():
    """初始化LLM"""
    setup_llm(
        name="default",
        provider="zhipu",
        model="glm-4.7",
    )
    return get_llm_manager().get_llm()


def test_1_extractor():
    """场景1: 测试结构化抽取"""
    print("\n" + "=" * 60)
    print("[场景1] 测试LLM结构化抽取")
    print("=" * 60)
    
    from pdca.plan.extractor import StructuredExtractor
    
    llm = setup_llm_once()
    extractor = StructuredExtractor(llm=llm)
    
    # 测试文本
    test_text = """
    我想创建一个自动化工作流：
    1. 首先调用API获取用户数据
    2. 然后分析用户行为数据
    3. 接着生成用户画像
    4. 最后发送报告邮件
    """
    
    print("\n输入文本:")
    print(test_text)
    print("\n正在调用LLM进行结构化抽取...")
    
    try:
        document = extractor.extract(test_text)
        
        print(f"\n✅ 抽取成功!")
        print(f"   节点数: {len(document.nodes)}")
        print(f"   边数: {len(document.edges)}")
        print(f"   状态数: {len(document.states)}")
        
        print("\n节点详情:")
        for node in document.nodes:
            print(f"   - {node.name} ({node.type})")
        
        return True, document
    except Exception as e:
        print(f"\n❌ 抽取失败: {e}")
        return False, None


def test_2_config_generator(document):
    """场景2: 测试配置生成"""
    print("\n" + "=" * 60)
    print("[场景2] 测试LLM配置生成")
    print("=" * 60)
    
    from pdca.plan.config_generator import ConfigGenerator
    
    llm = setup_llm_once()
    generator = ConfigGenerator()
    
    print("\n正在调用LLM生成工作流配置...")
    
    try:
        config = generator.generate_with_refinement(
            document,
            llm=llm,
            workflow_name="测试工作流"
        )
        
        print(f"\n✅ 配置生成成功!")
        print(f"   工作流ID: {config.meta.workflow_id}")
        print(f"   名称: {config.meta.name}")
        print(f"   版本: {config.meta.version}")
        print(f"   节点数: {len(config.nodes)}")
        print(f"   边数: {len(config.edges)}")
        
        return True, config
    except Exception as e:
        print(f"\n❌ 配置生成失败: {e}")
        return False, None


def test_3_code_generator(config):
    """场景3: 测试代码生成"""
    print("\n" + "=" * 60)
    print("[场景3] 测试LLM代码生成")
    print("=" * 60)
    
    from pdca.do_.code_generator import CodeGenerator
    
    llm = setup_llm_once()
    generator = CodeGenerator(llm=llm)
    
    output_dir = Path(__file__).parent / "test_output"
    
    print(f"\n正在调用LLM生成项目代码到: {output_dir}")
    
    try:
        files = generator.generate_project(config, output_dir)
        
        print(f"\n✅ 代码生成成功!")
        print(f"   生成文件数: {len(files)}")
        for filename, filepath in list(files.items())[:5]:
            print(f"   - {filename}")
        if len(files) > 5:
            print(f"   ... 还有 {len(files) - 5} 个文件")
        
        return True, files
    except Exception as e:
        print(f"\n❌ 代码生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_4_evaluator():
    """场景4: 测试评估器"""
    print("\n" + "=" * 60)
    print("[场景4] 测试LLM评估器")
    print("=" * 60)
    
    from pdca.check.evaluator import (
        CriteriaGenerator,
        TestCaseGenerator,
        EvaluationReportGenerator
    )
    
    llm = setup_llm_once()
    
    workflow_description = "自动化数据分析工作流"
    node_count = 5
    
    print("\n正在调用LLM生成验收标准和测试用例...")
    
    try:
        # 1. 生成验收标准
        criteria_gen = CriteriaGenerator(llm)
        criteria = criteria_gen.generate_criteria(
            workflow_description,
            node_count,
            [],
            []
        )
        print(f"\n✅ 验收标准生成成功!")
        print(f"   功能标准: {len(criteria.get('functional', []))} 条")
        print(f"   质量标准: {len(criteria.get('quality', []))} 条")
        
        # 2. 生成测试用例
        case_gen = TestCaseGenerator(llm, criteria_gen)
        cases = case_gen.generate_all_cases(
            workflow_description,
            node_count,
            [],
            criteria
        )
        print(f"\n✅ 测试用例生成成功!")
        print(f"   生成用例数: {len(cases)}")
        for case in cases[:3]:
            print(f"   - {case.name} ({case.category})")
        
        # 3. 生成评估报告
        report_gen = EvaluationReportGenerator(llm)
        
        # 模拟测试结果
        from pdca.check.evaluator import TestResult, TestStatus
        
        mock_results = []
        for case in cases:
            mock_results.append(TestResult(
                case_id=case.case_id,
                status=TestStatus.PASSED,
                execution_time=0.1,
                actual_outputs={"result": "ok"},
                timestamp="2026-04-21T00:00:00Z"
            ))
        
        report = report_gen.generate(
            "测试工作流",
            mock_results,
            cases,
            workflow_description,
            []
        )
        
        print(f"\n✅ 评估报告生成成功!")
        print(f"   通过率: {report.pass_rate:.1f}%")
        print(f"   通过: {report.passed}, 失败: {report.failed}")
        
        return True, report
    except Exception as e:
        print(f"\n❌ 评估器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_5_reviewer():
    """场景5: 测试复盘器"""
    print("\n" + "=" * 60)
    print("[场景5] 测试LLM复盘器")
    print("=" * 60)
    
    from pdca.act.reviewer import GRRAVPReviewer, OptimizationGenerator
    from pdca.check.evaluator import EvaluationReport
    
    llm = setup_llm_once()
    
    # 创建模拟的评估报告
    mock_report = EvaluationReport(
        workflow_name="测试工作流",
        total_cases=10,
        passed=8,
        failed=2,
        skipped=0,
        errors=0,
        pass_rate=80.0,
        execution_time=5.0,
        test_results=[],
        issues=["部分边界情况未覆盖", "错误处理可以更完善"],
        suggestions=["增加更多测试用例", "改进错误处理逻辑"]
    )
    
    original_goals = [
        "成功生成可运行的工作流代码",
        "测试通过率达到80%以上",
        "工作流能够正常执行完成"
    ]
    
    print("\n正在调用LLM进行复盘分析...")
    
    try:
        # 1. GR/RAVP复盘
        reviewer = GRRAVPReviewer(llm)
        review_result = reviewer.review(
            "测试工作流",
            original_goals,
            mock_report
        )
        
        print(f"\n✅ 复盘分析成功!")
        print(f"   总体评分: {review_result.overall_score:.1f}/100")
        print(f"   建议数: {len(review_result.recommendations)}")
        for rec in review_result.recommendations[:3]:
            print(f"   - {rec}")
        
        # 2. 生成优化方案
        opt_gen = OptimizationGenerator(llm)
        proposals = opt_gen.generate_from_review(review_result)
        proposals = opt_gen.prioritize_proposals(proposals)
        
        print(f"\n✅ 优化方案生成成功!")
        print(f"   生成方案数: {len(proposals)}")
        for prop in proposals[:3]:
            print(f"   - {prop.title} ({prop.priority})")
        
        return True, review_result
    except Exception as e:
        print(f"\n❌ 复盘器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_6_loop_controller():
    """场景6: 测试循环控制器"""
    print("\n" + "=" * 60)
    print("[场景6] 测试LLM循环控制器")
    print("=" * 60)
    
    from pdca.act.loop_controller import create_loop_controller
    from pdca.check.evaluator import EvaluationReport
    
    llm = setup_llm_once()
    
    mock_report = EvaluationReport(
        workflow_name="测试工作流",
        total_cases=10,
        passed=7,
        failed=2,
        skipped=1,
        errors=0,
        pass_rate=70.0,
        execution_time=5.0,
        test_results=[],
        issues=["测试覆盖不足"],
        suggestions=[]
    )
    
    print("\n正在调用LLM进行循环决策...")
    
    try:
        controller = create_loop_controller(
            llm=llm,
            max_iterations=3,
            quality_threshold=80.0
        )
        
        controller.start("测试工作流")
        
        print(f"\n✅ 循环控制器初始化成功!")
        print(f"   最大迭代: {controller.max_iterations}")
        print(f"   质量阈值: {controller.quality_threshold}%")
        
        # 测试LLM决策
        should_continue = controller.should_continue(mock_report)
        
        print(f"\n✅ LLM决策结果: {'继续迭代' if should_continue else '终止循环'}")
        
        return True, controller
    except Exception as e:
        print(f"\n❌ 循环控制器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("PDCA-LangGraph-SOP LLM重构验证测试")
    print("=" * 60)
    
    results = []
    
    # 场景1: 抽取
    success, document = test_1_extractor()
    results.append(("场景1: LLM结构化抽取", success))
    
    if success and document:
        # 场景2: 配置生成
        success, config = test_2_config_generator(document)
        results.append(("场景2: LLM配置生成", success))
        
        if success and config:
            # 场景3: 代码生成
            success, files = test_3_code_generator(config)
            results.append(("场景3: LLM代码生成", success))
        else:
            results.append(("场景3: LLM代码生成", False))
    else:
        results.append(("场景2: LLM配置生成", False))
        results.append(("场景3: LLM代码生成", False))
    
    # 场景4: 评估器
    success, report = test_4_evaluator()
    results.append(("场景4: LLM评估器", success))
    
    # 场景5: 复盘器
    success, review = test_5_reviewer()
    results.append(("场景5: LLM复盘器", success))
    
    # 场景6: 循环控制器
    success, controller = test_6_loop_controller()
    results.append(("场景6: LLM循环控制器", success))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"   {status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！LLM重构验证成功！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查日志")
        return 1


if __name__ == "__main__":
    sys.exit(main())
