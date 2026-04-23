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

from nodes.workflow_graph import build_workflow, WorkflowState


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
    1. config_path 指定的JSON文件
    2. input_path 读取为文本输入到 'input' 字段
    3. 返回空字典（让节点自行初始化）
    """
    initial_state = {{}}

    if config_path:
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                initial_state.update(json.load(f))
            print(f"已加载配置文件: {{config_path}}")
        else:
            print(f"警告: 配置文件不存在: {{config_path}}")

    if input_path:
        input_file = Path(input_path)
        if input_file.exists():
            with open(input_file, 'r', encoding='utf-8') as f:
                initial_state['input'] = f.read()
            print(f"已读取输入文件: {{input_path}}")
        else:
            print(f"警告: 输入文件不存在: {{input_path}}")

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

    WORKFLOW_RUNNER_TEMPLATE = '''"""工作流运行器

自动生成的工作流运行代码
"""

from typing import Any, Dict, Optional
from pathlib import Path
import json

from pdca.core.config import WorkflowConfig
from pdca.core.logger import get_logger

logger = get_logger(__name__)


class WorkflowRunner:

    def __init__(self, config_path: Optional[str] = None, verbose: bool = False):
        self.verbose = verbose
        self.state: Dict[str, Any] = {{}}
        if config_path:
            self.config = self._load_config(config_path)
        else:
            self.config = self._create_default_config()
        self._init_state()

    def _load_config(self, config_path: str) -> WorkflowConfig:
        from pdca.core.config import Config
        return Config().load_workflow_config(config_path)

    def _create_default_config(self) -> WorkflowConfig:
        from pdca.core.config import WorkflowMeta, WorkflowConfig
        return WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="default", name="默认工作流",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ),
            nodes=[], edges=[], state=[]
        )

    def _init_state(self):
        for state_def in self.config.state:
            self.state[state_def.field_name] = state_def.default_value

    def run(self, input_path: Optional[str] = None, output_path: Optional[str] = None) -> Dict[str, Any]:
        try:
            if input_path:
                with open(input_path, 'r', encoding='utf-8') as f:
                    self.state['input'] = f.read()
            else:
                self.state['input'] = ""

            for node in self._get_execution_order():
                logger.info(f"执行节点: {{node.name}}")
                if self.verbose:
                    print(f"[{{node.name}}]")
                result = self._execute_node(node)
                self.state[node.node_id] = result
                if self.verbose:
                    print(f"  -> {{result}}")

            output = self.state.get('result', '')
            if output_path:
                Path(output_path).write_text(str(output), encoding='utf-8')
            return {{"success": True, "output": output}}
        except Exception as e:
            logger.error(f"工作流执行失败: {{e}}")
            return {{"success": False, "error": str(e)}}

    def _get_execution_order(self):
        nodes = {{n.node_id: n for n in self.config.nodes}}
        in_degree = {{n.node_id: 0 for n in self.config.nodes}}
        for edge in self.config.edges:
            if edge.source in in_degree:
                in_degree[edge.target] += 1
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []
        while queue:
            nid = queue.pop(0)
            result.append(nodes[nid])
            for edge in self.config.edges:
                if edge.source == nid:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] == 0:
                        queue.append(edge.target)
        return result

    def _execute_node(self, node) -> Any:
        node_handler = self._get_node_handler(node)
        return node_handler(self.state, node.config)

    def _get_node_handler(self, node) -> callable:
        try:
            module_name = f"nodes.{{node.node_id}}"
            handler_name = f"handle_{{node.node_id}}"
            module = __import__(module_name, fromlist=[handler_name])
            return getattr(module, handler_name)
        except (ImportError, AttributeError):
            return self._default_node_handler

    def _default_node_handler(self, state: Dict, config: Dict) -> Any:
        return "节点执行完成"
'''

    TEST_TEMPLATE = '''"""测试模块 - {workflow_name}

自动生成的工作流测试
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from pdca.do_.workflow_runner import WorkflowRunner


class TestWorkflow:

    @pytest.fixture
    def runner(self):
        return WorkflowRunner(verbose=True)

    def test_workflow_basic(self, runner):
        result = runner.run()
        assert result.get("success") is True

    def test_workflow_with_input(self, runner, tmp_path):
        input_file = tmp_path / "input.txt"
        input_file.write_text("测试输入")
        result = runner.run(input_path=str(input_file))
        assert result.get("success") is True


class TestNodes:
{node_tests}
'''

    README_TEMPLATE = '''# {workflow_name}

自动生成的工作流项目

## 描述

{description}

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

```bash
python main.py --input input.txt --output output.txt
```

## 工作流结构

### 节点

{node_descriptions}

### 边

{edge_descriptions}

## 版本

- 版本: {version}
- 生成时间: {generated_at}

## 配置

配置文件位于 `config/workflow.json`
'''

    REQUIREMENTS_TEMPLATE = '''# 工作流依赖

pdca>=0.1.0
langgraph>=0.0.20
'''

    @classmethod
    def get_main_template(cls, workflow_name: str, version: str) -> str:
        return cls.MAIN_TEMPLATE.format(
            workflow_name=workflow_name, version=version,
            generated_at=datetime.now().isoformat()
        )

    @classmethod
    def get_workflow_runner_template(cls) -> str:
        return cls.WORKFLOW_RUNNER_TEMPLATE

    @classmethod
    def get_test_template(cls, workflow_name: str, node_tests: str) -> str:
        return cls.TEST_TEMPLATE.format(workflow_name=workflow_name, node_tests=node_tests)

    @classmethod
    def get_readme_template(cls, workflow_name: str, description: str,
                           node_descriptions: str, edge_descriptions: str,
                           version: str) -> str:
        return cls.README_TEMPLATE.format(
            workflow_name=workflow_name, description=description or "无",
            node_descriptions=node_descriptions, edge_descriptions=edge_descriptions,
            version=version, generated_at=datetime.now().isoformat()
        )

    @classmethod
    def get_requirements_template(cls) -> str:
        return cls.REQUIREMENTS_TEMPLATE


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
        """生成完整项目"""
        logger.info("project_generation_start", workflow=config.meta.name, output_dir=str(output_dir))

        self._create_directories(output_dir)
        generated_files = {}

        # 1. 主程序
        main_code = self.template.get_main_template(config.meta.name, config.meta.version)
        main_path = output_dir / "main.py"
        self._write_file(main_path, main_code)
        generated_files["main.py"] = main_path

        # 2. 工作流运行器
        runner_code = self.template.get_workflow_runner_template()
        runner_path = output_dir / "pdca" / "do_" / "workflow_runner.py"
        self._write_file(runner_path, runner_code)
        generated_files["workflow_runner.py"] = runner_path

        # 3. 节点代码 + LangGraph图代码（单次LLM或模板）
        graph_code = self._generate_graph_code(config)
        nodes_dir = output_dir / "nodes"
        nodes_dir.mkdir(exist_ok=True)
        graph_path = nodes_dir / "workflow_graph.py"
        self._write_file(graph_path, graph_code)
        generated_files["workflow_graph.py"] = graph_path

        # 4. 配置
        config_path = output_dir / "config" / "workflow.json"
        self._save_config(config, config_path)
        generated_files["workflow.json"] = config_path

        # 5. README
        readme_code = self._generate_readme(config)
        readme_path = output_dir / "README.md"
        self._write_file(readme_path, readme_code)
        generated_files["README.md"] = readme_path

        # 6. requirements.txt
        req_path = output_dir / "requirements.txt"
        self._write_file(req_path, self.template.get_requirements_template())
        generated_files["requirements.txt"] = req_path

        # 7. 测试
        test_code = self._generate_tests(config)
        test_path = output_dir / "tests" / "test_workflow.py"
        self._write_file(test_path, test_code)
        generated_files["test_workflow.py"] = test_path

        # 8. __init__.py
        for init_file in [output_dir / "nodes" / "__init__.py",
                          output_dir / "tests" / "__init__.py"]:
            init_file.write_text('"""包初始化"""\n', encoding='utf-8')

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
        for d in [base_dir, base_dir / "nodes", base_dir / "tests",
                  base_dir / "config", base_dir / "pdca" / "do_"]:
            d.mkdir(parents=True, exist_ok=True)

    def _generate_readme(self, config: WorkflowConfig) -> str:
        node_desc = "\n".join([f"- **{n.name}** ({n.type}): {n.description or '无描述'}" for n in config.nodes])
        edge_desc = "\n".join([f"- `{e.source}` --{e.type}--> `{e.target}`" for e in config.edges])
        return self.template.get_readme_template(
            config.meta.name, config.meta.description,
            node_desc, edge_desc, config.meta.version
        )

    def _generate_tests(self, config: WorkflowConfig) -> str:
        node_tests = "\n".join([
            f'\n    def test_node_{n.node_id}(self, runner):\n        """测试{n.name}节点"""\n        pass'
            for n in config.nodes
        ])
        return self.template.get_test_template(config.meta.name, node_tests)

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
