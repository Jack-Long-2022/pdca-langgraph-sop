"""代码生成模块

将WorkflowConfig转换为可运行的Python项目
"""

import os
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from pdca.core.config import WorkflowConfig, NodeDefinition, EdgeDefinition
from pdca.core.logger import get_logger

logger = get_logger(__name__)


# ============== 项目模板 ==============

class ProjectTemplate:
    """项目模板定义"""
    
    # 主程序模板
    MAIN_TEMPLATE = '''#!/usr/bin/env python3
"""工作流主程序 - {workflow_name}

自动生成的工作流代码
版本: {version}
生成时间: {generated_at}
"""

import argparse
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from pdca.do_.workflow_runner import WorkflowRunner


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="{workflow_name}")
    parser.add_argument("--input", "-i", help="输入文件路径")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    # 初始化工作流
    runner = WorkflowRunner(
        config_path=args.config,
        verbose=args.verbose
    )
    
    # 执行工作流
    run_result = runner.run(
        input_path=args.input,
        output_path=args.output
    )
    
    if run_result.get("success"):
        print("工作流执行成功!")
        if run_result.get("output"):
            print(f"输出: {{run_result['output']}}")
        return 0
    else:
        print(f"工作流执行失败: {{run_result.get('error')}}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
'''

    # 工作流运行器模板
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
    """工作流运行器"""
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        verbose: bool = False
    ):
        """初始化运行器
        
        Args:
            config_path: 配置文件路径
            verbose: 是否详细输出
        """
        self.verbose = verbose
        self.state: Dict[str, Any] = {{}}
        
        if config_path:
            self.config = self._load_config(config_path)
        else:
            # 使用默认配置
            self.config = self._create_default_config()
        
        self._init_state()
    
    def _load_config(self, config_path: str) -> WorkflowConfig:
        """加载配置"""
        from pdca.core.config import Config
        cfg = Config()
        return cfg.load_workflow_config(config_path)
    
    def _create_default_config(self) -> WorkflowConfig:
        """创建默认配置"""
        from pdca.core.config import WorkflowMeta, WorkflowConfig
        
        return WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id="default",
                name="默认工作流",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ),
            nodes=[],
            edges=[],
            state=[]
        )
    
    def _init_state(self):
        """初始化状态"""
        for state_def in self.config.state:
            self.state[state_def.field_name] = state_def.default_value
    
    def run(
        self,
        input_path: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """运行工作流
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
        
        Returns:
            执行结果
        """
        try:
            # 加载输入
            if input_path:
                with open(input_path, 'r', encoding='utf-8') as f:
                    self.state['input'] = f.read()
            else:
                self.state['input'] = ""
            
            # 执行工作流节点
            for node in self._get_execution_order():
                logger.info(f"执行节点: {{node.name}}")
                if self.verbose:
                    print(f"[{{node.name}}]")
                
                # 调用节点处理函数
                result = self._execute_node(node)
                self.state[node.node_id] = result
                
                if self.verbose:
                    print(f"  -> {{result}}")
            
            # 保存输出
            output = self.state.get('result', '')
            if output_path:
                Path(output_path).write_text(str(output), encoding='utf-8')
            
            return {{
                "success": True,
                "output": output
            }}
        
        except Exception as e:
            logger.error(f"工作流执行失败: {{e}}")
            return {{
                "success": False,
                "error": str(e)
            }}
    
    def _get_execution_order(self):
        """获取执行顺序"""
        # 简单的拓扑排序
        nodes = {{n.node_id: n for n in self.config.nodes}}
        in_degree = {{n.node_id: 0 for n in self.config.nodes}}
        
        for edge in self.config.edges:
            if edge.source in in_degree:
                in_degree[edge.target] += 1
        
        # Kahn算法
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
        """执行单个节点"""
        # 动态导入并调用节点模块
        node_handler = self._get_node_handler(node)
        return node_handler(self.state, node.config)
    
    def _get_node_handler(self, node) -> callable:
        """获取节点处理函数"""
        try:
            module_name = f"nodes.{{node.node_id}}"
            handler_name = f"handle_{{node.node_id}}"
            
            module = __import__(module_name, fromlist=[handler_name])
            return getattr(module, handler_name)
        except (ImportError, AttributeError):
            # 返回默认处理器
            return self._default_node_handler
    
    def _default_node_handler(self, state: Dict, config: Dict) -> Any:
        """默认节点处理器"""
        return f"节点执行完成"
'''

    # 节点处理模板
    NODE_HANDLER_TEMPLATE = '''"""节点处理模块 - {node_name}

节点类型: {node_type}
描述: {description}
"""

from typing import Any, Dict


def handle_{node_id}(state: Dict[str, Any], config: Dict[str, Any]) -> Any:
    """处理{node_name}节点
    
    Args:
        state: 工作流状态
        config: 节点配置
    
    Returns:
        节点执行结果
    """
    # 节点输入
    inputs = {inputs_str}
    
    # 节点逻辑
    # TODO: 实现{node_name}的具体逻辑
    
    result = f"{{node_name}}执行完成"
    
    # 节点输出
    outputs = {outputs_str}
    
    return result


if __name__ == "__main__":
    # 测试节点
    test_state = {{}}
    test_config = {{}}
    result = handle_{node_id}(test_state, test_config)
    print(f"测试结果: {{result}}")
'''

    # __init__.py模板
    INIT_TEMPLATE = '''"""节点包

自动生成的节点处理模块
"""

from .base import NodeBase

__all__ = ["NodeBase"]
'''

    # 工具模块模板
    TOOL_TEMPLATE = '''"""工具模块

自动生成的工作流工具集
"""

from typing import Any, Dict, List
import json


class ToolRegistry:
    """工具注册表"""
    
    _tools: Dict[str, callable] = {{}}
    
    @classmethod
    def register(cls, name: str, func: callable):
        """注册工具
        
        Args:
            name: 工具名称
            func: 工具函数
        """
        cls._tools[name] = func
    
    @classmethod
    def get(cls, name: str) -> callable:
        """获取工具
        
        Args:
            name: 工具名称
        
        Returns:
            工具函数
        """
        return cls._tools.get(name)
    
    @classmethod
    def list_tools(cls) -> List[str]:
        """列出所有工具"""
        return list(cls._tools.keys())


# 内置工具

def tool_http_request(url: str, method: str = "GET", **kwargs) -> Any:
    """HTTP请求工具
    
    Args:
        url: 请求URL
        method: 请求方法
        **kwargs: 其他参数
    
    Returns:
        响应内容
    """
    import requests
    
    response = requests.request(method, url, **kwargs)
    return response.text


def tool_json_parser(text: str) -> Any:
    """JSON解析工具
    
    Args:
        text: JSON文本
    
    Returns:
        解析后的对象
    """
    return json.loads(text)


def tool_text_template(template: str, **kwargs) -> str:
    """文本模板工具
    
    Args:
        template: 模板字符串
        **kwargs: 模板变量
    
    Returns:
        渲染后的文本
    """
    return template.format(**kwargs)


# 注册内置工具
ToolRegistry.register("http_request", tool_http_request)
ToolRegistry.register("json_parser", tool_json_parser)
ToolRegistry.register("text_template", tool_text_template)
'''

    # 测试模板
    TEST_TEMPLATE = '''"""测试模块 - {workflow_name}

自动生成的工作流测试
"""

import pytest
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdca.do_.workflow_runner import WorkflowRunner


class TestWorkflow:
    """工作流测试"""
    
    @pytest.fixture
    def runner(self):
        """创建运行器"""
        return WorkflowRunner(verbose=True)
    
    def test_workflow_basic(self, runner):
        """测试基本执行"""
        result = runner.run()
        assert result.get("success") is True
    
    def test_workflow_with_input(self, runner, tmp_path):
        """测试带输入的执行"""
        input_file = tmp_path / "input.txt"
        input_file.write_text("测试输入")
        
        result = runner.run(input_path=str(input_file))
        assert result.get("success") is True


class TestNodes:
    """节点测试"""
{node_tests}
'''

    # README模板
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

    # requirements模板
    REQUIREMENTS_TEMPLATE = '''# 工作流依赖

pdca>=0.1.0
langgraph>=0.0.20
'''

    @classmethod
    def get_main_template(cls, workflow_name: str, version: str) -> str:
        """获取主程序模板"""
        return cls.MAIN_TEMPLATE.format(
            workflow_name=workflow_name,
            version=version,
            generated_at=datetime.now().isoformat()
        )
    
    @classmethod
    def get_node_handler_template(
        cls,
        node_id: str,
        node_name: str,
        node_type: str,
        description: str,
        inputs: list,
        outputs: list
    ) -> str:
        """获取节点处理模板"""
        inputs_str = str(inputs) if inputs else "[]"
        outputs_str = str(outputs) if outputs else "[]"
        
        return cls.NODE_HANDLER_TEMPLATE.format(
            node_id=node_id,
            node_name=node_name,
            node_type=node_type,
            description=description or "无",
            inputs_str=inputs_str,
            outputs_str=outputs_str
        )
    
    @classmethod
    def get_workflow_runner_template(cls) -> str:
        """获取工作流运行器模板"""
        return cls.WORKFLOW_RUNNER_TEMPLATE
    
    @classmethod
    def get_tool_template(cls) -> str:
        """获取工具模板"""
        return cls.TOOL_TEMPLATE
    
    @classmethod
    def get_test_template(
        cls,
        workflow_name: str,
        node_tests: str
    ) -> str:
        """获取测试模板"""
        return cls.TEST_TEMPLATE.format(
            workflow_name=workflow_name,
            node_tests=node_tests
        )
    
    @classmethod
    def get_readme_template(
        cls,
        workflow_name: str,
        description: str,
        node_descriptions: str,
        edge_descriptions: str,
        version: str
    ) -> str:
        """获取README模板"""
        return cls.README_TEMPLATE.format(
            workflow_name=workflow_name,
            description=description or "无",
            node_descriptions=node_descriptions,
            edge_descriptions=edge_descriptions,
            version=version,
            generated_at=datetime.now().isoformat()
        )
    
    @classmethod
    def get_requirements_template(cls) -> str:
        """获取requirements模板"""
        return cls.REQUIREMENTS_TEMPLATE


# ============== 节点代码生成器 ==============

class NodeCodeGenerator:
    """节点代码生成器"""
    
    def __init__(self, template: ProjectTemplate = None):
        self.template = template or ProjectTemplate()
    
    def generate(self, node: NodeDefinition) -> str:
        """生成节点代码
        
        Args:
            node: 节点定义
        
        Returns:
            节点代码字符串
        """
        return self.template.get_node_handler_template(
            node_id=node.node_id,
            node_name=node.name,
            node_type=node.type,
            description=node.description,
            inputs=node.inputs,
            outputs=node.outputs
        )
    
    def generate_all(self, nodes: list[NodeDefinition]) -> dict[str, str]:
        """生成所有节点代码
        
        Args:
            nodes: 节点定义列表
        
        Returns:
            {node_id: code} 字典
        """
        return {node.node_id: self.generate(node) for node in nodes}


# ============== 代码生成器 ==============

class CodeGenerator:
    """代码生成器 - 将WorkflowConfig转换为Python项目"""
    
    def __init__(
        self,
        template: ProjectTemplate = None,
        node_generator: NodeCodeGenerator = None
    ):
        self.template = template or ProjectTemplate()
        self.node_generator = node_generator or NodeCodeGenerator(self.template)
    
    def generate_project(
        self,
        config: WorkflowConfig,
        output_dir: Path
    ) -> dict[str, Path]:
        """生成完整项目
        
        Args:
            config: 工作流配置
            output_dir: 输出目录
        
        Returns:
            生成的文件映射 {filename: path}
        """
        logger.info("project_generation_start",
                   workflow=config.meta.name,
                   output_dir=str(output_dir))
        
        # 创建目录结构
        self._create_directories(output_dir)
        
        # 生成文件
        generated_files = {}
        
        # 1. 生成主程序
        main_code = self.template.get_main_template(
            config.meta.name,
            config.meta.version
        )
        main_path = output_dir / "main.py"
        self._write_file(main_path, main_code)
        generated_files["main.py"] = main_path
        
        # 2. 生成工作流运行器
        runner_code = self.template.get_workflow_runner_template()
        runner_path = output_dir / "pdca" / "do_" / "workflow_runner.py"
        self._write_file(runner_path, runner_code)
        generated_files["workflow_runner.py"] = runner_path
        
        # 3. 生成节点代码
        nodes_dir = output_dir / "nodes"
        node_files = self._generate_node_files(config.nodes, nodes_dir)
        generated_files.update(node_files)
        
        # 4. 生成工具模块
        tool_code = self.template.get_tool_template()
        tool_path = output_dir / "pdca" / "tools.py"
        self._write_file(tool_path, tool_code)
        generated_files["tools.py"] = tool_path
        
        # 5. 生成配置
        config_path = output_dir / "config" / "workflow.json"
        self._save_config(config, config_path)
        generated_files["workflow.json"] = config_path
        
        # 6. 生成README
        readme_code = self._generate_readme(config)
        readme_path = output_dir / "README.md"
        self._write_file(readme_path, readme_code)
        generated_files["README.md"] = readme_path
        
        # 7. 生成requirements.txt
        req_code = self.template.get_requirements_template()
        req_path = output_dir / "requirements.txt"
        self._write_file(req_path, req_code)
        generated_files["requirements.txt"] = req_path
        
        # 8. 生成测试
        test_code = self._generate_tests(config)
        test_path = output_dir / "tests" / "test_workflow.py"
        self._write_file(test_path, test_code)
        generated_files["test_workflow.py"] = test_path
        
        # 9. 生成__init__.py文件
        self._generate_init_files(output_dir)
        
        logger.info("project_generation_complete",
                   file_count=len(generated_files))
        
        return generated_files
    
    def _create_directories(self, base_dir: Path):
        """创建目录结构"""
        dirs = [
            base_dir,
            base_dir / "nodes",
            base_dir / "tests",
            base_dir / "config",
            base_dir / "pdca" / "do_",
            base_dir / "prompts",
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def _generate_node_files(
        self,
        nodes: list[NodeDefinition],
        nodes_dir: Path
    ) -> dict[str, Path]:
        """生成节点文件"""
        files = {}
        
        for node in nodes:
            code = self.node_generator.generate(node)
            path = nodes_dir / f"{node.node_id}.py"
            self._write_file(path, code)
            files[f"nodes/{node.node_id}.py"] = path
        
        return files
    
    def _generate_readme(self, config: WorkflowConfig) -> str:
        """生成README"""
        node_descriptions = "\n".join([
            f"- **{n.name}** ({n.type}): {n.description or '无描述'}"
            for n in config.nodes
        ])
        
        edge_descriptions = "\n".join([
            f"- `{e.source}` --{e.type}--> `{e.target}`"
            for e in config.edges
        ])
        
        return self.template.get_readme_template(
            workflow_name=config.meta.name,
            description=config.meta.description,
            node_descriptions=node_descriptions,
            edge_descriptions=edge_descriptions,
            version=config.meta.version
        )
    
    def _generate_tests(self, config: WorkflowConfig) -> str:
        """生成测试代码"""
        node_tests = "\n".join([
            f'''
    def test_node_{n.node_id}(self, runner):
        """测试{n.name}节点"""
        # TODO: 添加{n.name}的具体测试
        pass'''
            for n in config.nodes
        ])
        
        return self.template.get_test_template(
            workflow_name=config.meta.name,
            node_tests=node_tests
        )
    
    def _generate_init_files(self, base_dir: Path):
        """生成__init__.py文件"""
        init_files = [
            base_dir / "nodes" / "__init__.py",
            base_dir / "tests" / "__init__.py",
            base_dir / "prompts" / "__init__.py",
        ]
        
        for init_file in init_files:
            init_file.write_text('"""包初始化"""\n', encoding='utf-8')
    
    def _save_config(self, config: WorkflowConfig, path: Path):
        """保存配置"""
        from pdca.core.config import Config
        cfg = Config(config_dir=path.parent)
        cfg.save_workflow_config(path.name, config)
    
    def _write_file(self, path: Path, content: str):
        """写入文件"""
        path.write_text(content, encoding='utf-8')
        logger.debug("file_generated", path=str(path))


# ============== LangGraph工作流构建器 ==============

class WorkflowBuilder:
    """LangGraph工作流构建器"""
    
    def build_state_graph_code(self, config: WorkflowConfig) -> str:
        """生成StateGraph构建代码
        
        Args:
            config: 工作流配置
        
        Returns:
            LangGraph代码字符串
        """
        imports = [
            "from typing import TypedDict, Annotated",
            "from langgraph.graph import StateGraph, END",
            "import operator"
        ]
        
        # State定义
        state_fields = []
        for state_def in config.state:
            state_fields.append(f"    {state_def.field_name}: {self._python_type(state_def.type)}")
        
        # 节点函数定义
        node_funcs = []
        for node in config.nodes:
            func_code = self._generate_node_function(node)
            node_funcs.append(func_code)
        
        # 边定义
        edges_code = self._generate_edges(config.edges)
        
        # 组装代码
        code_parts = [
            "\n".join(imports),
            "",
            "",
            "class WorkflowState(TypedDict):",
            "    \"\"\"工作流状态定义\"\"\"",
            "\n".join(state_fields) if state_fields else "    pass",
            "",
            "",
            "# 节点函数",
            "\n\n".join(node_funcs),
            "",
            "",
            "def build_workflow_graph():",
            "    \"\"\"构建工作流图\"\"\"",
            "    # 创建图",
            "    graph = StateGraph(WorkflowState)",
            "",
            "    # 添加节点",
        ]
        
        for node in config.nodes:
            code_parts.append(f'    graph.add_node("{node.node_id}", {node.node_id}_handler)')
        
        code_parts.extend([
            "",
            "    # 添加边",
            edges_code,
            "",
            "    # 编译图",
            "    return graph.compile()",
        ])
        
        return "\n".join(code_parts)
    
    def _python_type(self, type_str: str) -> str:
        """转换类型"""
        type_map = {
            "string": "str",
            "integer": "int",
            "float": "float",
            "boolean": "bool",
            "array": "list",
            "object": "dict",
            "any": "Any"
        }
        return type_map.get(type_str, "Any")
    
    def _generate_node_function(self, node: NodeDefinition) -> str:
        """生成节点函数"""
        return f'''def {node.node_id}_handler(state: WorkflowState) -> WorkflowState:
    """节点: {node.name}
    
    类型: {node.type}
    描述: {node.description or '无'}
    """
    # TODO: 实现节点逻辑
    result = {{"message": "{node.name}执行完成"}}
    return {{**state, **result}}
'''
    
    def _generate_edges(self, edges: list[EdgeDefinition]) -> str:
        """生成边定义代码"""
        lines = []
        
        for edge in edges:
            if edge.type == "sequential":
                lines.append(f'    graph.add_edge("{edge.source}", "{edge.target}")')
            elif edge.type == "conditional":
                lines.append(f'    graph.add_conditional_edges("{edge.source}", {edge.condition})')
        
        return "\n".join(lines)


# ============== 便捷函数 ==============

def generate_code(
    config: WorkflowConfig,
    output_dir: Path
) -> dict[str, Path]:
    """快速生成代码
    
    Args:
        config: 工作流配置
        output_dir: 输出目录
    
    Returns:
        生成的文件映射
    """
    generator = CodeGenerator()
    return generator.generate_project(config, output_dir)


def build_langgraph_code(config: WorkflowConfig) -> str:
    """快速构建LangGraph代码
    
    Args:
        config: 工作流配置
    
    Returns:
        LangGraph代码
    """
    builder = WorkflowBuilder()
    return builder.build_state_graph_code(config)
