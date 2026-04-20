"""配置生成模块

将结构化抽取结果转换为WorkflowConfig
"""

import uuid
from datetime import datetime
from typing import Any, Optional
from pdca.core.config import (
    WorkflowConfig,
    WorkflowMeta,
    NodeDefinition,
    EdgeDefinition,
    StateDefinition
)
from pdca.plan.extractor import StructuredDocument
from pdca.core.logger import get_logger

logger = get_logger(__name__)


# ============== Prompt模板 ==============

class PromptTemplates:
    """Prompt模板集合"""
    
    # 节点细化prompt
    NODE_REFINEMENT_TEMPLATE = """请细化以下节点描述，使其更加精确和可执行。

节点信息：
- 名称: {node_name}
- 当前描述: {node_description}
- 节点类型: {node_type}

请生成：
1. 更精确的节点名称（如果是中文，保持中文）
2. 详细的节点描述
3. 输入参数列表
4. 输出参数列表
5. 建议的配置参数

请以JSON格式输出：
{{
    "name": "细化后的名称",
    "description": "详细描述",
    "inputs": ["参数1", "参数2"],
    "outputs": ["输出1"],
    "config": {{"建议的配置": "值"}}
}}
"""

    # 工作流优化prompt
    WORKFLOW_OPTIMIZATION_TEMPLATE = """请分析并优化以下工作流设计。

工作流描述：
{workflow_description}

当前节点：
{nodes}

当前边：
{edges}

请检查并优化：
1. 节点是否完整
2. 边连接是否正确
3. 是否缺少必要的控制节点（如条件分支、循环）
4. 状态定义是否完整

请以JSON格式输出优化后的工作流：
{{
    "suggestions": ["优化建议1", "优化建议2"],
    "additional_nodes": [...],
    "additional_edges": [...]
}}
"""

    # 配置生成prompt
    CONFIG_GENERATION_TEMPLATE = """请为以下工作流生成完整的配置定义。

工作流名称: {workflow_name}
工作流描述: {workflow_description}

节点列表：
{nodes}

边列表：
{edges}

状态列表：
{states}

请生成符合WorkflowConfig规范的完整配置，包括：
1. 元信息（UUID、版本号等）
2. 完整的节点定义
3. 边定义
4. 状态定义
5. 全局配置参数

请以JSON格式输出完整配置。
"""

    @classmethod
    def get_node_refinement_prompt(
        cls,
        node_name: str,
        node_description: str,
        node_type: str
    ) -> str:
        """获取节点细化prompt"""
        return cls.NODE_REFINEMENT_TEMPLATE.format(
            node_name=node_name,
            node_description=node_description or "无",
            node_type=node_type
        )
    
    @classmethod
    def get_workflow_optimization_prompt(
        cls,
        workflow_description: str,
        nodes: list[dict],
        edges: list[dict]
    ) -> str:
        """获取工作流优化prompt"""
        nodes_str = "\n".join([
            f"- {n.get('name', '未知')}: {n.get('description', '无描述')}"
            for n in nodes
        ])
        edges_str = "\n".join([
            f"- {e.get('source')} -> {e.get('target')}"
            for e in edges
        ])
        
        return cls.WORKFLOW_OPTIMIZATION_TEMPLATE.format(
            workflow_description=workflow_description,
            nodes=nodes_str,
            edges=edges_str
        )
    
    @classmethod
    def get_config_generation_prompt(
        cls,
        workflow_name: str,
        workflow_description: str,
        nodes: list[dict],
        edges: list[dict],
        states: list[dict]
    ) -> str:
        """获取配置生成prompt"""
        nodes_str = "\n".join([
            f"- {n.get('name', '未知')} ({n.get('type', 'unknown')})"
            for n in nodes
        ])
        edges_str = "\n".join([
            f"- {e.get('source')} --{e.get('type', 'sequential')}--> {e.get('target')}"
            for e in edges
        ])
        states_str = "\n".join([
            f"- {s.get('field_name', '未知')}: {s.get('type', 'string')}"
            for s in states
        ])
        
        return cls.CONFIG_GENERATION_TEMPLATE.format(
            workflow_name=workflow_name,
            workflow_description=workflow_description or "无",
            nodes=nodes_str,
            edges=edges_str,
            states=states_str
        )


# ============== 配置生成器 ==============

class ConfigGenerator:
    """配置生成器 - 将结构化文档转换为工作流配置"""
    
    def __init__(self, config_template: Optional[dict[str, Any]] = None):
        """初始化配置生成器
        
        Args:
            config_template: 可选的默认配置模板
        """
        self.config_template = config_template or {}
    
    def _generate_workflow_id(self) -> str:
        """生成工作流ID"""
        return f"wf_{uuid.uuid4().hex[:12]}"
    
    def _generate_version(self) -> str:
        """生成版本号"""
        return "0.1.0"
    
    def _generate_timestamp(self) -> str:
        """生成时间戳"""
        return datetime.utcnow().isoformat() + "Z"
    
    def _convert_node(self, extracted_node) -> NodeDefinition:
        """转换节点
        
        Args:
            extracted_node: ExtractedNode实例
        
        Returns:
            NodeDefinition实例
        """
        return NodeDefinition(
            node_id=extracted_node.node_id,
            name=extracted_node.name,
            type=extracted_node.type,
            description=extracted_node.description,
            inputs=extracted_node.inputs,
            outputs=extracted_node.outputs,
            config=extracted_node.config
        )
    
    def _convert_edge(self, extracted_edge) -> EdgeDefinition:
        """转换边
        
        Args:
            extracted_edge: ExtractedEdge实例
        
        Returns:
            EdgeDefinition实例
        """
        return EdgeDefinition(
            source=extracted_edge.source,
            target=extracted_edge.target,
            condition=extracted_edge.condition,
            type=extracted_edge.type
        )
    
    def _convert_state(self, extracted_state) -> StateDefinition:
        """转换状态
        
        Args:
            extracted_state: ExtractedState实例
        
        Returns:
            StateDefinition实例
        """
        return StateDefinition(
            field_name=extracted_state.field_name,
            type=extracted_state.type,
            default_value=extracted_state.default_value,
            description=extracted_state.description,
            required=extracted_state.required
        )
    
    def generate(
        self,
        document: StructuredDocument,
        workflow_name: Optional[str] = None
    ) -> WorkflowConfig:
        """从结构化文档生成工作流配置
        
        Args:
            document: 结构化文档
            workflow_name: 可选的工作流名称
        
        Returns:
            WorkflowConfig实例
        """
        logger.info("config_generation_start", 
                   node_count=len(document.nodes),
                   edge_count=len(document.edges))
        
        # 生成元信息
        workflow_id = self._generate_workflow_id()
        now = self._generate_timestamp()
        
        # 转换节点
        nodes = [self._convert_node(n) for n in document.nodes]
        
        # 转换边
        edges = [self._convert_edge(e) for e in document.edges]
        
        # 转换状态
        states = [self._convert_state(s) for s in document.states]
        
        # 构建配置
        config = WorkflowConfig(
            meta=WorkflowMeta(
                workflow_id=workflow_id,
                name=workflow_name or f"工作流_{workflow_id}",
                version=self._generate_version(),
                description=self._infer_description(document.raw_text),
                created_at=now,
                updated_at=now
            ),
            nodes=nodes,
            edges=edges,
            state=states,
            config=self._generate_global_config(document)
        )
        
        logger.info("config_generation_complete",
                   workflow_id=workflow_id,
                   node_count=len(nodes),
                   edge_count=len(edges))
        
        return config
    
    def _infer_description(self, raw_text: str) -> str:
        """从原始文本推断描述
        
        Args:
            raw_text: 原始输入文本
        
        Returns:
            推断的描述
        """
        # 取前100个字符作为描述
        if len(raw_text) <= 100:
            return raw_text.strip()
        return raw_text[:97].strip() + "..."
    
    def _generate_global_config(
        self,
        document: StructuredDocument
    ) -> dict[str, Any]:
        """生成全局配置
        
        Args:
            document: 结构化文档
        
        Returns:
            全局配置字典
        """
        config = {
            "extraction_version": "1.0",
            "has_missing_info": len(document.missing_info) > 0
        }
        
        # 添加缺失信息作为警告
        if document.missing_info:
            config["warnings"] = document.missing_info
        
        # 合并模板配置
        if self.config_template:
            config.update(self.config_template)
        
        return config
    
    def generate_with_refinement(
        self,
        document: StructuredDocument,
        llm: Optional[Any] = None,
        workflow_name: Optional[str] = None
    ) -> WorkflowConfig:
        """使用LLM细化生成配置
        
        Args:
            document: 结构化文档
            llm: LLM实例
            workflow_name: 工作流名称
        
        Returns:
            细化后的WorkflowConfig
        """
        # 先进行基础生成
        config = self.generate(document, workflow_name)
        
        # 如果有LLM，进行节点细化
        if llm is not None:
            config = self._refine_nodes_with_llm(config, llm)
        
        return config
    
    def _refine_nodes_with_llm(
        self,
        config: WorkflowConfig,
        llm: Any
    ) -> WorkflowConfig:
        """使用LLM细化节点
        
        Args:
            config: 原始配置
            llm: LLM实例
        
        Returns:
            细化后的配置
        """
        refined_nodes = []
        
        for node in config.nodes:
            prompt = PromptTemplates.get_node_refinement_prompt(
                node_name=node.name,
                node_description=node.description or "",
                node_type=node.type
            )
            
            try:
                response = llm.generate(prompt)
                refined_data = self._parse_llm_json_response(response)
                
                if refined_data:
                    node.name = refined_data.get("name", node.name)
                    node.description = refined_data.get("description", node.description)
                    node.inputs = refined_data.get("inputs", node.inputs)
                    node.outputs = refined_data.get("outputs", node.outputs)
                    node.config.update(refined_data.get("config", {}))
                    
                    logger.debug("node_refined", node_id=node.node_id)
            except Exception as e:
                logger.warning("node_refinement_failed", 
                             node_id=node.node_id, 
                             error=str(e))
            
            refined_nodes.append(node)
        
        config.nodes = refined_nodes
        config.meta.updated_at = self._generate_timestamp()
        
        return config
    
    def _parse_llm_json_response(self, response: str) -> Optional[dict]:
        """解析LLM的JSON响应
        
        Args:
            response: LLM响应文本
        
        Returns:
            解析后的字典，如果解析失败返回None
        """
        import json
        import re
        
        # 尝试提取JSON块
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        return None


# ============== 便捷函数 ==============

def generate_config(
    document: StructuredDocument,
    workflow_name: Optional[str] = None
) -> WorkflowConfig:
    """快速生成配置
    
    Args:
        document: 结构化文档
        workflow_name: 工作流名称
    
    Returns:
        WorkflowConfig实例
    """
    generator = ConfigGenerator()
    return generator.generate(document, workflow_name)


def generate_config_with_refinement(
    document: StructuredDocument,
    llm: Any,
    workflow_name: Optional[str] = None
) -> WorkflowConfig:
    """带细化的配置生成
    
    Args:
        document: 结构化文档
        llm: LLM实例
        workflow_name: 工作流名称
    
    Returns:
        WorkflowConfig实例
    """
    generator = ConfigGenerator()
    return generator.generate_with_refinement(document, llm, workflow_name)
