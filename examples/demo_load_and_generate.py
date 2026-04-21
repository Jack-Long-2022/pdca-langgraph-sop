"""示例1: 加载 JSON 配置 -> 生成 LangGraph 工作流代码

演示完整的加载-转换-生成流程:
  JSONLoader -> StructuredDocument -> ConfigGenerator -> WorkflowConfig -> CodeGenerator

使用方法:
    cd pdca-langgraph-sop
    python examples/demo_load_and_generate.py
"""

import sys
import json
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from pdca.plan.extractor import JSONLoader
from pdca.plan.config_generator import ConfigGenerator
from pdca.do_.code_generator import CodeGenerator, WorkflowBuilder


def main():
    # ── 1. 加载 JSON 配置 ──────────────────────────────────────────
    json_path = Path("config/extractions/wf_data_analysis.json")
    print(f"[1] 加载 JSON 配置: {json_path}")

    loader = JSONLoader()
    document = loader.load(json_path)

    print(f"    节点数: {len(document.nodes)}")
    print(f"    边数:   {len(document.edges)}")
    print(f"    状态数: {len(document.states)}")
    print()

    # 打印节点概览
    for node in document.nodes:
        print(f"    [{node.type}] {node.name} ({node.node_id})")
        if node.inputs:
            print(f"        inputs:  {node.inputs}")
        if node.outputs:
            print(f"        outputs: {node.outputs}")
    print()

    # ── 2. 转换为 WorkflowConfig ────────────────────────────────────
    print("[2] 转换为 WorkflowConfig")

    generator = ConfigGenerator()
    config = generator.generate(
        document,
        workflow_name="自动化数据分析工作流",
    )

    print(f"    workflow_id:  {config.meta.workflow_id}")
    print(f"    name:         {config.meta.name}")
    print(f"    version:      {config.meta.version}")
    print(f"    node_count:   {len(config.nodes)}")
    print(f"    edge_count:   {len(config.edges)}")
    print(f"    state_count:  {len(config.state)}")
    print()

    # ── 3A. 方式A: 生成完整项目 ─────────────────────────────────────
    output_dir = Path("examples/demo_output")
    print(f"[3A] 生成完整项目 -> {output_dir}")

    code_gen = CodeGenerator()
    generated_files = code_gen.generate_project(config, output_dir)

    print(f"    生成 {len(generated_files)} 个文件:")
    for name, path in generated_files.items():
        rel = path.relative_to(output_dir) if path.is_relative_to(output_dir) else path
        print(f"      {rel}")
    print()

    # ── 3B. 方式B: 生成纯 LangGraph StateGraph 代码 ─────────────────
    print("[3B] 生成纯 LangGraph StateGraph 代码")
    print("-" * 60)

    builder = WorkflowBuilder()
    langgraph_code = builder.build_state_graph_code(config)
    print(langgraph_code)
    print("-" * 60)
    print()

    # 保存 LangGraph 代码到文件
    langgraph_path = output_dir / "langgraph_workflow.py"
    langgraph_path.parent.mkdir(parents=True, exist_ok=True)
    langgraph_path.write_text(langgraph_code, encoding="utf-8")
    print(f"    LangGraph 代码已保存: {langgraph_path}")
    print()

    # ── 4. 打印配置 JSON 摘要 ───────────────────────────────────────
    print("[4] 配置 JSON 摘要")
    print("-" * 60)
    summary = {
        "workflow_id": config.meta.workflow_id,
        "name": config.meta.name,
        "nodes": [{"id": n.node_id, "name": n.name, "type": n.type} for n in config.nodes],
        "edges": [{"source": e.source, "target": e.target, "type": e.type} for e in config.edges],
        "states": [s.field_name for s in config.state],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("-" * 60)

    print(f"\n[完成] 输出目录: {output_dir}")


if __name__ == "__main__":
    main()
