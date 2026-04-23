"""代码生成模块

将WorkflowConfig转换为可运行的Python项目。
使用单次LLM调用完成全部代码生成（原N次节点生成+图构建合并为1次）。
"""

import re
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from pdca.core.config import WorkflowConfig, NodeDefinition, EdgeDefinition
from pdca.core.logger import get_logger
from pdca.core.llm import OpenAILLM, get_llm_for_task
from pdca.core.utils import parse_json_response
from pdca.core.prompts import SYSTEM_PROMPTS, CODE_PROMPT

logger = get_logger(__name__)


# ============== 项目模板 ==============

class ProjectTemplate:
    """项目模板定义"""

    MAIN_TEMPLATE = '''#!/usr/bin/env python3
"""工作流主程序 - {workflow_name}

自动生成的工作流代码
版本: {version}
生成时间: {generated_at}

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
    parser = argparse.ArgumentParser(description="{workflow_name}")
    parser.add_argument("--input", "-i", help="输入文件路径")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--config", "-c", help="初始状态配置文件路径(JSON)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    return parser.parse_args()


def load_initial_state(config_path: str = None, input_path: str = None) -> dict:
    """加载初始工作流状态

    优先级:
    1. 使用 create_initial_state() 初始化默认字段
    2. input_path 读取为JSON/文本 -> 作为 raw_input
    3. config_path 指定的JSON文件 -> 作为 raw_input
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
            print(f"已读取输入文件: {{input_path}}")
        else:
            print(f"警告: 输入文件不存在: {{input_path}}")

    if config_path:
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                initial_state['raw_input'] = json.load(f)
            print(f"已加载配置文件: {{config_path}}")
        else:
            print(f"警告: 配置文件不存在: {{config_path}}")

    return initial_state


def save_output(result: dict, output_path: str = None):
    """保存工作流执行结果"""
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 将结果序列化为JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"结果已保存到: {{output_path}}")


def main():
    args = parse_args()

    print("=" * 60)
    print("工作流执行: {workflow_name}")
    print("=" * 60)

    # 1. 加载初始状态
    initial_state = load_initial_state(args.config, args.input)

    # 2. 构建工作流图
    app = build_workflow()
    print("工作流图已构建")

    # 3. 执行工作流
    print("\\n开始执行工作流...")
    try:
        result = app.invoke(initial_state)
        print("\\n工作流执行成功!")

        # 4. 输出结果
        if args.verbose:
            print("\\n最终状态:")
            for key, value in result.items():
                print(f"  {{key}}: {{value}}")

        # 5. 保存结果
        save_output(result, args.output)

        return 0

    except Exception as e:
        print(f"\\n工作流执行失败: {{e}}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
'''

    @classmethod
    def get_main_template(cls, workflow_name: str, version: str) -> str:
        return cls.MAIN_TEMPLATE.format(
            workflow_name=workflow_name, version=version,
            generated_at=datetime.now().isoformat()
        )


# ============== 代码生成器 ==============

def _default_node_function(node: NodeDefinition) -> str:
    return f'''
def {node.node_id}_handler(state: WorkflowState) -> WorkflowState:
    """节点: {node.name}

    类型: {node.type}
    描述: {node.description or '无'}
    """
    # TODO: 实现节点逻辑
    result = {{"message": "{node.name}执行完成"}}
    return {{**state, **result}}
'''


def _python_type(type_str: str) -> str:
    return {"string": "str", "integer": "int", "float": "float",
            "boolean": "bool", "array": "list", "object": "dict", "any": "Any"}.get(type_str, "Any")


def _generate_edges_code(edges: list[EdgeDefinition]) -> str:
    lines = []
    for edge in edges:
        if edge.type == "sequential":
            lines.append(f'    graph.add_edge("{edge.source}", "{edge.target}")')
        elif edge.type == "conditional":
            lines.append(f'    graph.add_conditional_edges("{edge.source}", {edge.condition})')
    return "\n".join(lines)


def _template_build_graph_code(config: WorkflowConfig) -> str:
    """模板方式生成LangGraph代码（不调LLM）"""
    imports = "from typing import TypedDict, Annotated\nfrom langgraph.graph import StateGraph, END\nimport operator"
    state_fields = "\n".join([f"    {s.field_name}: {_python_type(s.type)}"
                              for s in config.state]) or "    pass"
    node_funcs = "\n\n".join([_default_node_function(n) for n in config.nodes])
    edges_code = _generate_edges_code(config.edges)
    add_nodes = "\n".join([f'    graph.add_node("{n.node_id}", {n.node_id}_handler)' for n in config.nodes])

    return f"""{imports}


class WorkflowState(TypedDict):
    \"\"\"工作流状态定义\"\"\"
{state_fields}


# 节点函数
{node_funcs}


def build_workflow_graph():
    \"\"\"构建工作流图\"\"\"
    graph = StateGraph(WorkflowState)

    # 添加节点
{add_nodes}

    # 添加边
{edges_code}

    return graph.compile()
"""


class CodeGenerator:
    """代码生成器 — 单次LLM调用完成全部代码生成"""

    def __init__(self, llm: Optional[OpenAILLM] = None, template: ProjectTemplate = None):
        self.template = template or ProjectTemplate()
        self.llm = llm

    def generate_project(self, config: WorkflowConfig, output_dir: Path) -> dict[str, Path]:
        """生成精简SOP项目（仅核心执行文件）

        产出物结构：
        output_dir/
        ├── main.py              # 入口程序
        ├── nodes/
        │   └── workflow_graph.py # LangGraph 图代码
        └── config/
            └── workflow.json     # 工作流定义
        """
        logger.info("project_generation_start", workflow=config.meta.name, output_dir=str(output_dir))

        self._create_directories(output_dir)
        generated_files = {}

        # 1. 主程序
        main_code = self.template.get_main_template(config.meta.name, config.meta.version)
        main_path = output_dir / "main.py"
        self._write_file(main_path, main_code)
        generated_files["main.py"] = main_path

        # 2. LangGraph图代码
        graph_code = self._generate_graph_code(config)
        graph_path = output_dir / "nodes" / "workflow_graph.py"
        self._write_file(graph_path, graph_code)
        generated_files["workflow_graph.py"] = graph_path

        # 3. 工作流配置
        config_path = output_dir / "config" / "workflow.json"
        self._save_config(config, config_path)
        generated_files["workflow.json"] = config_path

        logger.info("project_generation_complete", file_count=len(generated_files))
        return generated_files

    def _generate_graph_code(self, config: WorkflowConfig) -> str:
        """生成LangGraph图代码（单次LLM调用）"""
        if self.llm is None:
            return _template_build_graph_code(config)

        nodes_info = "\n".join([f"- {n.node_id}: {n.name} ({n.type}) - {n.description or '无'}"
                                for n in config.nodes])
        edges_info = "\n".join([f"- {e.source} -> {e.target} ({e.type})"
                                for e in config.edges])
        states_info = "\n".join([f"- {s.field_name}: {s.type}"
                                 for s in config.state])

        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["code"]},
            {"role": "user", "content": CODE_PROMPT.format(
                workflow_name=config.meta.name,
                nodes=nodes_info, edges=edges_info, states=states_info,
            )},
        ]

        try:
            response = self.llm.generate_messages(messages)
            code = self._extract_code(response)
            if code:
                return code
        except Exception as e:
            logger.warning("llm_code_generation_failed", error=str(e))

        return _template_build_graph_code(config)

    def _extract_code(self, response: str) -> str:
        match = re.search(r'```python\s*([\s\S]*?)\s*```', response)
        if match:
            return match.group(1).strip()
        match = re.search(r'(def\s+\w+_handler[\s\S]*?)(?=\n\n|\Z)', response)
        if match:
            return match.group(1).strip()
        return response.strip()

    def _create_directories(self, base_dir: Path):
        for d in [base_dir, base_dir / "nodes", base_dir / "config"]:
            d.mkdir(parents=True, exist_ok=True)

    def _save_config(self, config: WorkflowConfig, path: Path):
        from pdca.core.config import Config
        Config(config_dir=path.parent).save_workflow_config(path.name, config)

    def _write_file(self, path: Path, content: str):
        path.write_text(content, encoding='utf-8')
        logger.debug("file_generated", path=str(path))


# ============== LangGraph工作流构建器 ==============

class WorkflowBuilder:
    """LangGraph工作流构建器 — 单次LLM调用"""

    def __init__(self, llm: Optional[OpenAILLM] = None):
        self.llm = llm

    def build_state_graph_code(self, config: WorkflowConfig) -> str:
        """生成StateGraph构建代码"""
        if self.llm is None:
            return _template_build_graph_code(config)

        generator = CodeGenerator(llm=self.llm)
        return generator._generate_graph_code(config)


# ============== 便捷函数 ==============

def generate_code(
    config: WorkflowConfig,
    output_dir: Path,
    llm: Optional[OpenAILLM] = None
) -> dict[str, Path]:
    """快速生成代码"""
    return CodeGenerator(llm=llm).generate_project(config, output_dir)


def build_langgraph_code(
    config: WorkflowConfig,
    llm: Optional[OpenAILLM] = None
) -> str:
    """快速构建LangGraph代码"""
    return WorkflowBuilder(llm=llm).build_state_graph_code(config)
