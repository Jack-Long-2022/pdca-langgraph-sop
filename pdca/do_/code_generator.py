"""代码生成模块

将WorkflowConfig转换为可运行的Python项目
使用LLM进行智能代码生成
"""

import os
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from pdca.core.config import WorkflowConfig, NodeDefinition, EdgeDefinition
from pdca.core.logger import get_logger
from pdca.core.llm import get_llm_manager, BaseLLM

logger = get_logger(__name__)


# ============== LLM代码生成器 ==============

class LLMCodeGenerator:
    """使用LLM生成高质量的节点代码"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm or get_llm_manager().get_llm()
    
    def generate_node_code(self, node: NodeDefinition, context: dict) -> str:
        """使用LLM生成单个节点的代码
        
        Args:
            node: 节点定义
            context: 上下文信息（包含工作流其他节点信息）
        
        Returns:
            生成的节点代码
        """
        prompt = self._build_node_code_prompt(node, context)
        
        try:
            response = self.llm.generate(prompt)
            # 尝试提取代码块
            return self._extract_code(response)
        except Exception as e:
            logger.warning("llm_node_code_generation_failed", 
                         node_id=node.node_id, 
                         error=str(e))
            return self._fallback_node_code(node)
    
    def _build_node_code_prompt(self, node: NodeDefinition, context: dict) -> str:
        """构建节点代码生成prompt"""
        other_nodes = context.get("other_nodes", [])
        other_nodes_info = "\n".join([
            f"- {n.name}: {n.description or '无'}"
            for n in other_nodes
        ]) if other_nodes else "无"
        
        inputs_str = ", ".join(node.inputs) if node.inputs else "state"
        outputs_str = ", ".join(node.outputs) if node.outputs else "result"
        
        return f"""你是一个Python代码专家，需要为工作流节点生成LangGraph代码。

节点信息：
- 节点ID: {node.node_id}
- 节点名称: {node.name}
- 节点类型: {node.type}
- 描述: {node.description or '无'}
- 输入参数: {inputs_str}
- 输出参数: {outputs_str}

工作流中其他节点：
{other_nodes_info}

请生成这个节点的LangGraph处理函数代码。要求：
1. 函数签名: def {node.node_id}_handler(state: WorkflowState) -> WorkflowState
2. 使用LangGraph风格，与WorkflowState配合
3. 输入输出参数要合理处理
4. 添加详细的docstring
5. 处理异常情况
6. 代码要健壮，不能有硬编码

请只输出Python代码（带```python标记）：
```python
# 节点处理函数
def {node.node_id}_handler(state: WorkflowState) -> WorkflowState:
    '''
    节点: {node.name}
    类型: {node.type}
    描述: {node.description or '无'}
    '''
    # 你的实现代码
    pass
```
"""
    
    def _extract_code(self, response: str) -> str:
        """从LLM响应中提取代码"""
        import re
        
        # 尝试提取python代码块
        match = re.search(r'```python\s*([\s\S]*?)\s*```', response)
        if match:
            return match.group(1).strip()
        
        # 如果没有代码块标记，直接返回
        match = re.search(r'(def\s+\w+_handler[\s\S]*?)(?=\n\n|\Z)', response)
        if match:
            return match.group(1).strip()
        
        return response.strip()
    
    def _fallback_node_code(self, node: NodeDefinition) -> str:
        """备用节点代码"""
        return f'''def {node.node_id}_handler(state: WorkflowState) -> WorkflowState:
    """
    节点: {node.name}
    类型: {node.type}
    描述: {node.description or '无'}
    """
    # TODO: 实现{node.name}的逻辑
    result = {{"message": "{node.name}执行完成"}}
    return {{**state, **result}}
'''


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
            return self._default_node_handler
    
    def _default_node_handler(self, state: Dict, config: Dict) -> Any:
        """默认节点处理器"""
        return f"节点执行完成"
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
        """注册工具"""
        cls._tools[name] = func
    
    @classmethod
    def get(cls, name: str) -> callable:
        """获取工具"""
        return cls._tools.get(name)
    
    @classmethod
    def list_tools(cls) -> List[str]:
        """列出所有工具"""
        return list(cls._tools.keys())


# 内置工具

def tool_http_request(url: str, method: str = "GET", **kwargs) -> Any:
    """HTTP请求工具"""
    import requests
    response = requests.request(method, url, **kwargs)
    return response.text


def tool_json_parser(text: str) -> Any:
    """JSON解析工具"""
    return json.loads(text)


def tool_text_template(template: str, **kwargs) -> str:
    """文本模板工具"""
    return template.format(**kwargs)


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

sys.path.insert(0, str(Path(__file__).parent.parent))

from pdca.do_.workflow_runner import WorkflowRunner


class TestWorkflow:
    """工作流测试"""
    
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
        return cls.MAIN_TEMPLATE.format(
            workflow_name=workflow_name,
            version=version,
            generated_at=datetime.now().isoformat()
        )
    
    @classmethod
    def get_workflow_runner_template(cls) -> str:
        return cls.WORKFLOW_RUNNER_TEMPLATE
    
    @classmethod
    def get_tool_template(cls) -> str:
        return cls.TOOL_TEMPLATE
    
    @classmethod
    def get_test_template(
        cls,
        workflow_name: str,
        node_tests: str
    ) -> str:
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
        return cls.REQUIREMENTS_TEMPLATE


# ============== 节点代码生成器 ==============

class NodeCodeGenerator:
    """节点代码生成器 - 使用LLM生成高质量代码"""
    
    def __init__(self, llm: Optional[BaseLLM] = None, template: ProjectTemplate = None):
        self.llm = llm
        self.template = template or ProjectTemplate()
        self.llm_generator = LLMCodeGenerator(llm) if llm else None
    
    def generate(self, node: NodeDefinition, context: dict = None) -> str:
        """生成节点代码
        
        Args:
            node: 节点定义
            context: 上下文（包含其他节点）
        
        Returns:
            节点代码字符串
        """
        context = context or {}
        
        # 如果有LLM，使用LLM生成
        if self.llm_generator:
            try:
                return self.llm_generator.generate_node_code(node, context)
            except Exception as e:
                logger.warning("llm_generation_failed_using_template", 
                             node_id=node.node_id, error=str(e))
        
        # 备用模板生成
        return self._template_generate(node)
    
    def _template_generate(self, node: NodeDefinition) -> str:
        """模板生成"""
        inputs_str = str(node.inputs) if node.inputs else "[]"
        outputs_str = str(node.outputs) if node.outputs else "[]"
        
        return f'''def {node.node_id}_handler(state: WorkflowState) -> WorkflowState:
    """
    节点: {node.name}
    类型: {node.type}
    描述: {node.description or '无'}
    """
    # TODO: 实现{node.name}的逻辑
    
    result = {{"message": "{node.name}执行完成"}}
    return {{**state, **result}}
'''
    
    def generate_all(self, nodes: list[NodeDefinition]) -> dict[str, str]:
        """生成所有节点代码
        
        Args:
            nodes: 节点定义列表
        
        Returns:
            {{node_id: code}} 字典
        """
        # 构建上下文：每个节点都能看到其他节点
        result = {}
        for i, node in enumerate(nodes):
            other_nodes = [n for j, n in enumerate(nodes) if j != i]
            context = {"other_nodes": other_nodes}
            result[node.node_id] = self.generate(node, context)
        
        return result


# ============== 代码生成器 ==============

class CodeGenerator:
    """代码生成器 - 使用LLM将WorkflowConfig转换为Python项目"""
    
    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        template: ProjectTemplate = None,
        node_generator: NodeCodeGenerator = None
    ):
        self.template = template or ProjectTemplate()
        self.llm = llm
        self.node_generator = node_generator or NodeCodeGenerator(llm, self.template)
    
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
        
        # 3. 生成节点代码（使用LLM）
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
        
        # 构建上下文
        for i, node in enumerate(nodes):
            other_nodes = [n for j, n in enumerate(nodes) if j != i]
            context = {"other_nodes": other_nodes}
            
            code = self.node_generator.generate(node, context)
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
    """LangGraph工作流构建器 - 使用LLM构建高质量的StateGraph"""
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm
        self.llm_generator = LLMCodeGenerator(llm) if llm else None
    
    def build_state_graph_code(self, config: WorkflowConfig) -> str:
        """生成StateGraph构建代码
        
        Args:
            config: 工作流配置
        
        Returns:
            LangGraph代码字符串
        """
        # 如果有LLM，使用LLM生成更智能的代码
        if self.llm_generator:
            try:
                return self._llm_build_graph_code(config)
            except Exception as e:
                logger.warning("llm_graph_build_failed", error=str(e))
        
        # 备用：使用模板生成
        return self._template_build_graph_code(config)
    
    def _llm_build_graph_code(self, config: WorkflowConfig) -> str:
        """使用LLM生成图构建代码"""
        # 先生成所有节点函数
        node_functions = {}
        for node in config.nodes:
            context = {"other_nodes": [n for n in config.nodes if n.node_id != node.node_id]}
            try:
                code = self.llm_generator.generate_node_code(node, context)
                node_functions[node.node_id] = code
            except:
                node_functions[node.node_id] = self._default_node_function(node)
        
        # 构建图代码
        prompt = f"""你是一个LangGraph专家，需要生成完整的工作流图构建代码。

工作流信息：
- 名称: {config.meta.name}
- 节点数: {len(config.nodes)}
- 边数: {len(config.edges)}

节点列表：
{chr(10).join([f"- {n.node_id}: {n.name} ({n.type})" for n in config.nodes])}

边列表：
{chr(10).join([f"- {e.source} -> {e.target} ({e.type})" for e in config.edges])}

请生成完整的LangGraph工作流代码，包括：
1. State定义
2. 所有节点处理函数
3. 图的构建（添加节点和边）
4. 条件边处理

请只输出Python代码：
```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class WorkflowState(TypedDict):
    # 状态定义
    pass

# 节点函数...
# 图构建...
```
"""
        try:
            response = self.llm.generate(prompt)
            return self._extract_code(response)
        except Exception as e:
            logger.warning("llm_graph_code_generation_failed", error=str(e))
            return self._template_build_graph_code(config)
    
    def _extract_code(self, response: str) -> str:
        """提取代码"""
        import re
        match = re.search(r'```python\s*([\s\S]*?)\s*```', response)
        if match:
            return match.group(1).strip()
        return response.strip()
    
    def _template_build_graph_code(self, config: WorkflowConfig) -> str:
        """模板方式生成图构建代码"""
        imports = [
            "from typing import TypedDict, Annotated",
            "from langgraph.graph import StateGraph, END",
            "import operator"
        ]
        
        # State定义
        state_fields = []
        for state_def in config.state:
            state_fields.append(f"    {state_def.field_name}: {self._python_type(state_def.type)}")
        
        # 节点函数
        node_funcs = []
        for node in config.nodes:
            func_code = self._default_node_function(node)
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
    
    def _default_node_function(self, node: NodeDefinition) -> str:
        """生成默认节点函数"""
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
    output_dir: Path,
    llm: Optional[BaseLLM] = None
) -> dict[str, Path]:
    """快速生成代码（支持LLM）
    
    Args:
        config: 工作流配置
        output_dir: 输出目录
        llm: LLM实例（可选）
    
    Returns:
        生成的文件映射
    """
    generator = CodeGenerator(llm=llm)
    return generator.generate_project(config, output_dir)


def build_langgraph_code(
    config: WorkflowConfig,
    llm: Optional[BaseLLM] = None
) -> str:
    """快速构建LangGraph代码（支持LLM）
    
    Args:
        config: 工作流配置
        llm: LLM实例（可选）
    
    Returns:
        LangGraph代码
    """
    builder = WorkflowBuilder(llm=llm)
    return builder.build_state_graph_code(config)