"""配置生成模块

将结构化抽取结果转换为WorkflowConfig
使用LLM进行深度优化和配置生成
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
from pdca.core.llm import get_llm_manager, BaseLLM

logger = get_logger(__name__)


# ============== Prompt模板 ==============

class PromptTemplates:
    """Prompt模板集合 - 用于LLM生成优化"""
    
    # 节点细化prompt
    NODE_REFINEMENT_TEMPLATE = """你是一个代码专家，需要细化工作流节点的定义。

当前节点信息：
- 名称: {node_name}
- 当前描述: {node_description}
- 节点类型: {node_type}

请生成更完善的节点定义，包括：
1. 更精确的节点名称
2. 详细的节点描述（说明具体做什么）
3. 输入参数列表（如果有）
4. 输出参数列表（如果有）
5. 建议的配置参数

请以JSON格式输出：
{{
    "name": "细化后的名称",
    "description": "详细描述",
    "inputs": ["参数1: 类型: 描述"],
    "outputs": ["输出1: 类型: 描述"],
    "config": {{"建议的配置": "值"}}
}}
"""

    # 工作流优化prompt
    WORKFLOW_OPTIMIZATION_TEMPLATE = """你是一个工作流架构师，需要分析和优化工作流设计。

工作流描述：
{workflow_description}

当前节点：
{nodes}

当前边：
{edges}

请分析并优化：
1. 节点是否完整？有没有遗漏的节点？
2. 边连接是否正确？逻辑是否通顺？
3. 是否缺少必要的控制节点（开始/结束/条件分支）？
4. 状态定义是否完整？
5. 有什么潜在的执行问题？

请以JSON格式输出优化建议：
{{
    "analysis": "整体分析",
    "suggestions": ["优化建议1", "优化建议2"],
    "potential_issues": ["潜在问题1"],
    "additional_nodes": [
        {{
            "name": "节点名称",
            "type": "tool|thought|control",
            "description": "描述",
            "reason": "为什么需要这个节点"
        }}
    ],
    "additional_edges": [
        {{
            "source": "源节点",
            "target": "目标节点",
            "type": "sequential|conditional",
            "reason": "为什么需要这条边"
        }}
    ]
}}
"""

    # 配置生成prompt
    CONFIG_GENERATION_TEMPLATE = """你是一个配置工程师，需要为工作流生成完整的配置定义。

工作流名称: {workflow_name}
工作流描述: {workflow_description}

节点列表：
{nodes}

边列表：
{edges}

状态列表：
{states}

请生成符合WorkflowConfig规范的完整配置。确保：
1. 所有节点都有完整定义
2. 所有边都正确连接
3. 状态定义包含必要的字段
4. 配置参数合理

请以JSON格式输出完整配置：
{{
    "workflow_id": "工作流ID",
    "name": "工作流名称",
    "version": "0.1.0",
    "description": "工作流描述",
    "nodes": [
        {{
            "node_id": "节点ID",
            "name": "节点名称",
            "type": "tool|thought|control",
            "description": "描述",
            "inputs": ["参数列表"],
            "outputs": ["输出列表"],
            "config": {{}}
        }}
    ],
    "edges": [
        {{
            "source": "源节点ID",
            "target": "目标节点ID",
            "type": "sequential|conditional|parallel",
            "condition": "条件表达式（可选）"
        }}
    ],
    "states": [
        {{
            "field_name": "字段名",
            "type": "string|integer|boolean|array|object|any",
            "default_value": null,
            "description": "描述",
            "required": true|false
        }}
    ]
}}
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
            f"- {n.get('name', '未知')} ({n.get('type', 'unknown')}): {n.get('description', '无描述')}"
            for n in nodes
        ])
        edges_str = "\n".join([
            f"- {e.get('source')} -> {e.get('target')} ({e.get('type', 'sequential')})"
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
            f"- {n.get('name', '未知')} ({n.get('type', 'unknown')}): {n.get('description', '')}"
            for n in nodes
        ])
        edges_str = "\n".join([
            f"- {e.get('source')} --{e.get('type', 'sequential')}--> {e.get('target')}"
            for e in edges
        ])
        states_str = "\n".join([
            f"- {s.get('field_name', '未知')}: {s.get('type', 'string')} ({'必填' if s.get('required') else '可选'})"
            for s in states
        ])
        
        return cls.CONFIG_GENERATION_TEMPLATE.format(
            workflow_name=workflow_name,
            workflow_description=workflow_description or "无",
            nodes=nodes_str,
            edges=edges_str,
            states=states_str
        )


# ============== LLM配置生成器 ==============

class ConfigGenerator:
    """配置生成器 - 使用LLM将结构化文档转换为工作流配置"""
    
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
    
    def generate(
        self,
        document: StructuredDocument,
        workflow_name: Optional[str] = None
    ) -> WorkflowConfig:
        """从结构化文档生成工作流配置（基础转换）
        
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
        """从原始文本推断描述"""
        if len(raw_text) <= 100:
            return raw_text.strip()
        return raw_text[:97].strip() + "..."
    
    def _generate_global_config(
        self,
        document: StructuredDocument
    ) -> dict[str, Any]:
        """生成全局配置"""
        config = {
            "extraction_version": "1.0",
            "has_missing_info": len(document.missing_info) > 0
        }
        
        if document.missing_info:
            config["warnings"] = document.missing_info
        
        if self.config_template:
            config.update(self.config_template)
        
        return config
    
    def _convert_node(self, extracted_node) -> NodeDefinition:
        """转换节点"""
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
        """转换边"""
        return EdgeDefinition(
            source=extracted_edge.source,
            target=extracted_edge.target,
            condition=extracted_edge.condition,
            type=extracted_edge.type
        )
    
    def _convert_state(self, extracted_state) -> StateDefinition:
        """转换状态"""
        return StateDefinition(
            field_name=extracted_state.field_name,
            type=extracted_state.type,
            default_value=extracted_state.default_value,
            description=extracted_state.description,
            required=extracted_state.required
        )
    
    def generate_with_refinement(
        self,
        document: StructuredDocument,
        llm: Optional[Any] = None,
        workflow_name: Optional[str] = None
    ) -> WorkflowConfig:
        """使用LLM细化生成配置（主要方法，质量优先）
        
        Args:
            document: 结构化文档
            llm: LLM实例
            workflow_name: 工作流名称
        
        Returns:
            细化后的WorkflowConfig
        """
        # 先进行基础生成
        config = self.generate(document, workflow_name)
        
        # 如果有LLM，进行全面优化
        if llm is not None:
            config = self._optimize_with_llm(config, llm, document)
        
        return config
    
    def _optimize_with_llm(
        self,
        config: WorkflowConfig,
        llm: Any,
        document: StructuredDocument
    ) -> WorkflowConfig:
        """使用LLM优化工作流配置
        
        Args:
            config: 原始配置
            llm: LLM实例
            document: 原始文档
        
        Returns:
            优化后的配置
        """
        logger.info("optimizing_config_with_llm")
        
        # 1. 首先用LLM优化工作流整体结构
        optimization = self._get_workflow_optimization(config, llm, document.raw_text)
        
        # 2. 应用优化建议
        if optimization:
            self._apply_optimization(config, optimization)
        
        # 3. 细化每个节点
        config = self._refine_nodes_with_llm(config, llm)
        
        # 4. 用LLM生成完整的配置定义
        config = self._generate_complete_config_with_llm(config, llm, document)
        
        config.meta.updated_at = self._generate_timestamp()
        
        return config
    
    def _get_workflow_optimization(
        self,
        config: WorkflowConfig,
        llm: Any,
        raw_text: str
    ) -> Optional[dict]:
        """获取工作流优化建议"""
        nodes_data = [
            {"name": n.name, "type": n.type, "description": n.description}
            for n in config.nodes
        ]
        edges_data = [
            {"source": e.source, "target": e.target, "type": e.type}
            for e in config.edges
        ]
        
        prompt = PromptTemplates.get_workflow_optimization_prompt(
            workflow_description=raw_text,
            nodes=nodes_data,
            edges=edges_data
        )
        
        try:
            response = llm.generate(prompt)
            return self._parse_json_response(response)
        except Exception as e:
            logger.warning("workflow_optimization_failed", error=str(e))
            return None
    
    def _apply_optimization(self, config: WorkflowConfig, optimization: dict):
        """应用优化建议"""
        if not optimization:
            return
        
        # 添加缺失的节点
        for node_info in optimization.get("additional_nodes", []):
            new_node = NodeDefinition(
                node_id=f"node_{uuid.uuid4().hex[:8]}",
                name=node_info.get("name", "新节点"),
                type=node_info.get("type", "tool"),
                description=node_info.get("description", ""),
                inputs=[],
                outputs=[],
                config={"added_by": "llm_optimization"}
            )
            config.nodes.append(new_node)
            logger.info("node_added_by_optimization", name=new_node.name)
        
        # 添加缺失的边
        node_names = {n.name for n in config.nodes}
        for edge_info in optimization.get("additional_edges", []):
            source_name = edge_info.get("source", "")
            target_name = edge_info.get("target", "")
            
            if source_name in node_names and target_name in node_names:
                source_id = next(n.node_id for n in config.nodes if n.name == source_name)
                target_id = next(n.node_id for n in config.nodes if n.name == target_name)
                
                new_edge = EdgeDefinition(
                    source=source_id,
                    target=target_id,
                    type=edge_info.get("type", "sequential"),
                    condition=None
                )
                config.edges.append(new_edge)
                logger.info("edge_added_by_optimization", 
                           source=source_name, target=target_name)
    
    def _refine_nodes_with_llm(
        self,
        config: WorkflowConfig,
        llm: Any
    ) -> WorkflowConfig:
        """使用LLM细化每个节点"""
        refined_nodes = []
        
        for node in config.nodes:
            prompt = PromptTemplates.get_node_refinement_prompt(
                node_name=node.name,
                node_description=node.description or "",
                node_type=node.type
            )
            
            try:
                response = llm.generate(prompt)
                refined_data = self._parse_json_response(response)
                
                if refined_data:
                    # 更新节点信息
                    if refined_data.get("name"):
                        node.name = refined_data["name"]
                    if refined_data.get("description"):
                        node.description = refined_data["description"]
                    if refined_data.get("inputs"):
                        node.inputs = refined_data["inputs"]
                    if refined_data.get("outputs"):
                        node.outputs = refined_data["outputs"]
                    if refined_data.get("config"):
                        node.config.update(refined_data["config"])
                    
                    logger.debug("node_refined", node_id=node.node_id)
            except Exception as e:
                logger.warning("node_refinement_failed", 
                             node_id=node.node_id, 
                             error=str(e))
            
            refined_nodes.append(node)
        
        config.nodes = refined_nodes
        return config
    
    def _generate_complete_config_with_llm(
        self,
        config: WorkflowConfig,
        llm: Any,
        document: StructuredDocument
    ) -> WorkflowConfig:
        """使用LLM生成完整的配置定义"""
        nodes_data = [
            {
                "name": n.name,
                "type": n.type,
                "description": n.description,
                "inputs": n.inputs,
                "outputs": n.outputs
            }
            for n in config.nodes
        ]
        edges_data = [
            {"source": e.source, "target": e.target, "type": e.type, "condition": e.condition}
            for e in config.edges
        ]
        states_data = [
            {
                "field_name": s.field_name,
                "type": s.type,
                "default_value": s.default_value,
                "description": s.description,
                "required": s.required
            }
            for s in config.state
        ]
        
        prompt = PromptTemplates.get_config_generation_prompt(
            workflow_name=config.meta.name,
            workflow_description=config.meta.description or "",
            nodes=nodes_data,
            edges=edges_data,
            states=states_data
        )
        
        try:
            response = llm.generate(prompt)
            llm_config = self._parse_json_response(response)
            
            if llm_config:
                # 更新配置
                if llm_config.get("description"):
                    config.meta.description = llm_config["description"]
                
                # 更新节点
                node_map = {n.node_id: n for n in config.nodes}
                for node_data in llm_config.get("nodes", []):
                    node_id = node_data.get("node_id")
                    if node_id in node_map:
                        node = node_map[node_id]
                        if node_data.get("description"):
                            node.description = node_data["description"]
                        if node_data.get("inputs"):
                            node.inputs = node_data["inputs"]
                        if node_data.get("outputs"):
                            node.outputs = node_data["outputs"]
                
                logger.info("config_enhanced_with_llm")
        except Exception as e:
            logger.warning("config_enhancement_failed", error=str(e))
        
        return config
    
    def _parse_json_response(self, response: str) -> Optional[dict]:
        """解析LLM的JSON响应"""
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
    """带细化的配置生成（推荐使用）
    
    Args:
        document: 结构化文档
        llm: LLM实例
        workflow_name: 工作流名称
    
    Returns:
        WorkflowConfig实例
    """
    generator = ConfigGenerator()
    return generator.generate_with_refinement(document, llm, workflow_name)