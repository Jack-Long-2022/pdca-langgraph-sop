#!/usr/bin/env python3
"""工作流主程序 - ECU信号一致性测试参数生成

自动生成的工作流代码
版本: 1.0.0
生成时间: 2026-04-23T22:28:25.624176

执行流程：
1. 导入 nodes/workflow_graph.py 中的 LangGraph 图
2. 初始化工作流状态
3. 按照定义的边关系执行各个节点
4. 输出最终结果
"""

import argparse
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nodes.workflow_graph import build_workflow, WorkflowState, create_initial_state


def parse_args():
    parser = argparse.ArgumentParser(description="ECU信号一致性测试参数生成")
    parser.add_argument("--input", "-i", help="输入文件路径")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--config", "-c", help="初始状态配置文件路径(JSON)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    return parser.parse_args()


def load_initial_state(config_path: str = None, input_path: str = None) -> dict:
    """加载初始工作流状态

    优先级:
    1. config_path 指定的JSON文件 -> 作为 raw_input
    2. input_path 读取为文本 -> 作为 raw_input
    3. 返回默认初始化状态
    """
    initial_state = create_initial_state()

    if input_path:
        input_file = Path(input_path)
        if input_file.exists():
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            try:
                initial_state['raw_input'] = json.loads(content)
            except json.JSONDecodeError:
                initial_state['raw_input'] = content
            print(f"已读取输入文件: {input_path}")
        else:
            print(f"警告: 输入文件不存在: {input_path}")

    if config_path:
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                initial_state['raw_input'] = json.load(f)
            print(f"已加载配置文件: {config_path}")
        else:
            print(f"警告: 配置文件不存在: {config_path}")

    return initial_state


def save_output(result: dict, output_path: str = None):
    """保存工作流执行结果"""
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 将结果序列化为JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"结果已保存到: {output_path}")


def main():
    args = parse_args()

    print("=" * 60)
    print("工作流执行: ECU信号一致性测试参数生成")
    print("=" * 60)

    # 1. 加载初始状态
    initial_state = load_initial_state(args.config, args.input)

    # 2. 构建工作流图
    app = build_workflow()
    print("工作流图已构建")

    # 3. 执行工作流
    print("\n开始执行工作流...")
    try:
        result = app.invoke(initial_state)
        print("\n工作流执行成功!")

        # 4. 输出结果
        if args.verbose:
            print("\n最终状态:")
            for key, value in result.items():
                print(f"  {key}: {value}")

        # 5. 保存结果
        save_output(result, args.output)

        return 0

    except Exception as e:
        print(f"\n工作流执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
