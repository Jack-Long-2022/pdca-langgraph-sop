"""工作流运行器

负责执行生成的工作流代码
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from pdca.core.logger import get_logger

logger = get_logger(__name__)


class WorkflowRunner:
    """工作流运行器
    
    负责加载配置并执行工作流
    """
    
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
        self.state: Dict[str, Any] = {}
        self.config = None
        
        if config_path:
            self.config = self._load_config(config_path)
        else:
            self.config = self._create_default_config()
        
        self._init_state()
    
    def _load_config(self, config_path: str) -> Any:
        """加载配置"""
        from pdca.core.config import Config, WorkflowConfig
        
        cfg = Config()
        path = Path(config_path)
        
        if path.suffix == '.json':
            return cfg.load_workflow_config(str(path))
        else:
            # 尝试在config子目录中查找
            config_file = path / "config" / "workflow.json"
            if config_file.exists():
                return cfg.load_workflow_config(str(config_file))
        
        return self._create_default_config()
    
    def _create_default_config(self) -> Any:
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
        if self.config and hasattr(self.config, 'state'):
            for state_def in self.config.state:
                self.state[state_def.field_name] = state_def.default_value
    
    def run(
        self,
        input_path: Optional[str] = None,
        output_path: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """运行工作流
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            input_data: 直接传入的输入数据
            timeout: 超时时间（秒）
        
        Returns:
            执行结果
        """
        try:
            # 加载输入
            if input_path:
                with open(input_path, 'r', encoding='utf-8') as f:
                    self.state['input'] = f.read()
            elif input_data:
                self.state.update(input_data)
            else:
                self.state['input'] = ""
            
            # 执行工作流节点
            execution_order = self._get_execution_order()
            
            for node in execution_order:
                if self.verbose:
                    logger.info(f"执行节点: {node.name}")
                    print(f"[{node.name}]")
                
                # 调用节点处理函数
                result = self._execute_node(node)
                self.state[node.node_id] = result
                
                if self.verbose:
                    print(f"  -> {result}")
            
            # 保存输出
            output = self.state.get('result', '')
            if output_path:
                Path(output_path).write_text(str(output), encoding='utf-8')
            
            return {
                "success": True,
                "output": output,
                "state": self.state
            }
        
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_execution_order(self) -> list:
        """获取执行顺序（拓扑排序）"""
        if not self.config:
            return []
        
        nodes = {n.node_id: n for n in self.config.nodes}
        in_degree = {n.node_id: 0 for n in self.config.nodes}
        
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
            # 尝试动态导入节点模块
            module_name = f"nodes.{node.node_id}"
            handler_name = f"handle_{node.node_id}"
            
            module = __import__(module_name, fromlist=[handler_name])
            return getattr(module, handler_name)
        except (ImportError, AttributeError):
            # 返回默认处理器
            return self._default_node_handler
    
    def _default_node_handler(self, state: Dict, config: Dict) -> Any:
        """默认节点处理器"""
        return f"节点执行完成"
    
    def get_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        return self.state
    
    def reset_state(self):
        """重置状态"""
        self.state = {}
        self._init_state()