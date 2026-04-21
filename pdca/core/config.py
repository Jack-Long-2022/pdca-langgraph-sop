"""配置管理模块

负责配置文件的加载、验证和版本管理
"""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator
import copy


class WorkflowMeta(BaseModel):
    """工作流元信息"""
    workflow_id: str = Field(..., description="工作流唯一标识，UUID格式")
    name: str = Field(..., description="工作流名称")
    version: str = Field(default="0.1.0", description="版本号，语义化版本格式")
    description: Optional[str] = Field(default=None, description="工作流功能描述")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="最后更新时间")


class NodeDefinition(BaseModel):
    """节点定义"""
    node_id: str = Field(..., description="节点唯一标识")
    name: str = Field(..., description="节点名称")
    type: str = Field(..., description="节点类型: tool/thought/control")
    description: Optional[str] = Field(default=None, description="节点功能描述")
    inputs: list = Field(default_factory=list, description="输入参数定义列表")
    outputs: list = Field(default_factory=list, description="输出参数定义列表")
    config: Dict[str, Any] = Field(default_factory=dict, description="节点配置参数")

    @field_validator('type')
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        valid_types = {'tool', 'thought', 'control'}
        if v not in valid_types:
            raise ValueError(f"节点类型必须是 {valid_types} 之一")
        return v


class EdgeDefinition(BaseModel):
    """边定义"""
    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    condition: Optional[str] = Field(default=None, description="条件表达式")
    type: str = Field(default="sequential", description="边类型: sequential/conditional/parallel/error/loop")

    @field_validator('type')
    @classmethod
    def validate_edge_type(cls, v: str) -> str:
        valid_types = {'sequential', 'conditional', 'parallel', 'error', 'loop'}
        if v not in valid_types:
            raise ValueError(f"边类型必须是 {valid_types} 之一")
        return v


class StateDefinition(BaseModel):
    """状态定义"""
    field_name: str = Field(..., description="状态字段名称")
    type: str = Field(..., description="字段类型")
    default_value: Any = Field(default=None, description="默认值")
    description: Optional[str] = Field(default=None, description="字段描述")
    required: bool = Field(default=False, description="是否必填")


class WorkflowConfig(BaseModel):
    """工作流配置"""
    meta: WorkflowMeta = Field(..., description="工作流元信息")
    nodes: list[NodeDefinition] = Field(default_factory=list, description="节点定义列表")
    edges: list[EdgeDefinition] = Field(default_factory=list, description="边定义列表")
    state: list[StateDefinition] = Field(default_factory=list, description="状态定义列表")
    config: Dict[str, Any] = Field(default_factory=dict, description="配置参数")


class Config:
    """配置管理类"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent.parent.parent / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Any] = {}

    def load_json(self, filename: str) -> Dict[str, Any]:
        """加载JSON配置文件"""
        filepath = self.config_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"配置文件不存在: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_json(self, filename: str, data: Dict[str, Any], indent: int = 2) -> None:
        """保存JSON配置文件"""
        filepath = self.config_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)

    def load_yaml(self, filename: str) -> Dict[str, Any]:
        """加载YAML配置文件"""
        filepath = self.config_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"配置文件不存在: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def save_yaml(self, filename: str, data: Dict[str, Any]) -> None:
        """保存YAML配置文件"""
        filepath = self.config_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    def load_workflow_config(self, filename: str) -> WorkflowConfig:
        """加载工作流配置"""
        data = self.load_json(filename)
        return WorkflowConfig(**data)

    def save_workflow_config(self, filename: str, config: WorkflowConfig) -> None:
        """保存工作流配置"""
        data = config.model_dump()
        self.save_json(filename, data)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持缓存）"""
        if key not in self._cache:
            self._cache[key] = default
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        self._cache[key] = value

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()


# 全局配置实例
_config: Optional[Config] = None

def get_config() -> Config:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = Config()
    return _config
