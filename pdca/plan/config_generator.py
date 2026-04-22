"""配置生成模块

将结构化抽取结果转换为WorkflowConfig。
使用单次LLM调用完成优化+配置生成（原3步合并为1步）。
"""

import json
import uuid
from datetime import datetime
from typing import Any, Optional
from pdca.core.config import (
    WorkflowConfig, WorkflowMeta, NodeDefinition, EdgeDefinition, StateDefinition
)
from pdca.plan.extractor import StructuredDocument, ExtractedNode
from pdca.core.logger import get_logger
from pdca.core.llm import OpenAILLM, get_llm_for_task
from pdca.core.utils import parse_json_response
from pdca.core.prompts import SYSTEM_PROMPTS, CONFIG_PROMPT

logger = get_logger(__name__)


def _basic_convert(document: StructuredDocument, workflow_name: Optional[str] = None) -> WorkflowConfig:
    """将StructuredDocument基础转换为WorkflowConfig（不调LLM）"""
    workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat() + "Z"

    nodes = [
        NodeDefinition(
            node_id=n.node_id, name=n.name, type=n.type,
            description=n.description, inputs=n.inputs,
            outputs=n.outputs, config=n.config,
        )
        for n in document.nodes
    ]

    edges = [
        EdgeDefinition(
            source=e.source, target=e.target,
            condition=e.condition, type=e.type,
        )
        for e in document.edges
    ]

    states = [
        StateDefinition(
            field_name=s.field_name, type=s.type,
            default_value=s.default_value, description=s.description,
            required=s.required,
        )
        for s in document.states
    ]

    return WorkflowConfig(
        meta=WorkflowMeta(
            workflow_id=workflow_id,
            name=workflow_name or f"工作流_{workflow_id}",
            version="0.1.0",
            description=document.raw_text[:100].strip() if len(document.raw_text) > 100 else document.raw_text.strip(),
            created_at=now, updated_at=now,
        ),
        nodes=nodes, edges=edges, state=states,
        config={
            "extraction_version": "2.0",
            "has_missing_info": len(document.missing_info) > 0,
            **({"warnings": document.missing_info} if document.missing_info else {}),
        },
    )


def _format_nodes_for_prompt(nodes: list[NodeDefinition]) -> str:
    return "\n".join([
        f"- {n.name} ({n.type}): {n.description or '无描述'}"
        f"  输入: {n.inputs}  输出: {n.outputs}"
        for n in nodes
    ])


def _format_edges_for_prompt(edges: list[EdgeDefinition]) -> str:
    return "\n".join([
        f"- {e.source} --{e.type}--> {e.target}"
        + (f"  条件: {e.condition}" if e.condition else "")
        for e in edges
    ])


def _format_states_for_prompt(states: list[StateDefinition]) -> str:
    return "\n".join([
        f"- {s.field_name}: {s.type} ({'必填' if s.required else '可选'})"
        for s in states
    ])


def _merge_llm_config(base: WorkflowConfig, llm_data: dict) -> WorkflowConfig:
    """将LLM优化结果合并回基础配置"""
    # 更新描述
    if llm_data.get("description"):
        base.meta.description = llm_data["description"]

    # 建立节点名称映射
    node_by_name = {n.name: n for n in base.nodes}

    # 更新节点
    for node_data in llm_data.get("nodes", []):
        name = node_data.get("name", "")
        if name in node_by_name:
            node = node_by_name[name]
            if node_data.get("description"):
                node.description = node_data["description"]
            if node_data.get("inputs"):
                node.inputs = node_data["inputs"]
            if node_data.get("outputs"):
                node.outputs = node_data["outputs"]
            if node_data.get("config"):
                node.config.update(node_data["config"])
        else:
            # 新增节点
            new_node = NodeDefinition(
                node_id=f"node_{uuid.uuid4().hex[:8]}",
                name=name,
                type=node_data.get("type", "tool"),
                description=node_data.get("description", ""),
                inputs=node_data.get("inputs", []),
                outputs=node_data.get("outputs", []),
                config={"added_by": "llm_optimization"},
            )
            base.nodes.append(new_node)
            node_by_name[name] = new_node
            logger.info("node_added_by_optimization", name=name)

    # 更新边
    for edge_data in llm_data.get("edges", []):
        source_name = edge_data.get("source", "")
        target_name = edge_data.get("target", "")
        if source_name in node_by_name and target_name in node_by_name:
            source_id = node_by_name[source_name].node_id
            target_id = node_by_name[target_name].node_id
            # 检查是否已存在
            existing = any(
                e.source == source_id and e.target == target_id
                for e in base.edges
            )
            if not existing:
                base.edges.append(EdgeDefinition(
                    source=source_id, target=target_id,
                    type=edge_data.get("type", "sequential"),
                    condition=edge_data.get("condition"),
                ))
                logger.info("edge_added_by_optimization", source=source_name, target=target_name)

    # 更新状态
    state_by_name = {s.field_name: s for s in base.state}
    for state_data in llm_data.get("states", []):
        field_name = state_data.get("field_name", "")
        if field_name in state_by_name:
            s = state_by_name[field_name]
            if state_data.get("description"):
                s.description = state_data["description"]
            if "required" in state_data:
                s.required = state_data["required"]
        else:
            base.state.append(StateDefinition(
                field_name=field_name,
                type=state_data.get("type", "string"),
                default_value=state_data.get("default_value"),
                description=state_data.get("description"),
                required=state_data.get("required", False),
            ))

    base.meta.updated_at = datetime.utcnow().isoformat() + "Z"
    return base


# ============== 公共 API ==============

class ConfigGenerator:
    """配置生成器 — 单次LLM调用完成优化+配置"""

    def __init__(self, config_template: Optional[dict[str, Any]] = None,
                 component_library: Optional[Any] = None):
        self.config_template = config_template or {}
        self.component_library = component_library

    def generate(
        self,
        document: StructuredDocument,
        workflow_name: Optional[str] = None,
    ) -> WorkflowConfig:
        """基础转换（不调LLM）"""
        config = _basic_convert(document, workflow_name)
        if self.config_template:
            config.config.update(self.config_template)
        return config

    def generate_with_refinement(
        self,
        document: StructuredDocument,
        llm: Optional[OpenAILLM] = None,
        workflow_name: Optional[str] = None,
    ) -> WorkflowConfig:
        """基础转换 + 组件库增强 + 单次LLM优化"""
        config = self.generate(document, workflow_name)

        # 组件库增强：优先 LLM 批量语义匹配，回退到关键词匹配
        if self.component_library:
            config = self._enhance_with_library(config, llm, workflow_name or "unknown")

        if llm is None:
            # LLM 不可用时，仍保存组件到库
            if self.component_library:
                self.component_library.save_workflow_config(config, workflow_name or "unknown")
            return config

        logger.info("optimizing_config_with_llm")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["config"]},
            {"role": "user", "content": CONFIG_PROMPT.format(
                workflow_name=config.meta.name,
                workflow_description=config.meta.description or "",
                nodes=_format_nodes_for_prompt(config.nodes),
                edges=_format_edges_for_prompt(config.edges),
                states=_format_states_for_prompt(config.state),
            )},
        ]

        try:
            response = llm.generate_messages(messages)
            data = parse_json_response(response)
            if data:
                config = _merge_llm_config(config, data)
                logger.info("config_optimized_with_llm")
        except Exception as e:
            logger.warning("config_optimization_failed", error=str(e))

        # 保存组件到库
        if self.component_library:
            self.component_library.save_workflow_config(config, workflow_name or "unknown")

        return config

    def _enhance_with_library(
        self,
        config: WorkflowConfig,
        llm: Optional[OpenAILLM] = None,
        workflow_name: str = "unknown",
    ) -> WorkflowConfig:
        """用组件库增强配置（优先 LLM 批量匹配，回退关键词匹配）"""
        # 优先：LLM 批量语义匹配
        if self.component_library._llm:
            return self.component_library.batch_enhance(config, llm)

        # 回退：旧的关键词逐个匹配（LLM 不可用时）
        return self._legacy_enhance_with_library(config, workflow_name)

    def _legacy_enhance_with_library(self, config: WorkflowConfig, workflow_name: str) -> WorkflowConfig:
        """旧的关键词匹配增强（LLM 不可用时的回退方案）"""
        for node in config.nodes:
            match = self.component_library.lookup_node(
                node.name, node.description or "", node_type=node.type
            )
            if match:
                if not node.description and match.description:
                    node.description = match.description
                if not node.inputs and match.inputs:
                    node.inputs = match.inputs
                if not node.outputs and match.outputs:
                    node.outputs = match.outputs
                if match.config:
                    for k, v in match.config.items():
                        if k not in node.config:
                            node.config[k] = v
                logger.info("node_enhanced_from_library",
                           node=node.name, template=match.template_id)

        for state in config.state:
            match = self.component_library.lookup_state(state.field_name, state.type)
            if match:
                if not state.description and match.description:
                    state.description = match.description
                logger.info("state_enhanced_from_library",
                           state=state.field_name, template=match.template_id)

        return config


def generate_config(
    document: StructuredDocument,
    workflow_name: Optional[str] = None,
) -> WorkflowConfig:
    """快速生成配置（不调LLM）"""
    return ConfigGenerator().generate(document, workflow_name)


def generate_config_with_refinement(
    document: StructuredDocument,
    llm: Optional[OpenAILLM] = None,
    workflow_name: Optional[str] = None,
) -> WorkflowConfig:
    """带LLM优化的配置生成（推荐）"""
    return ConfigGenerator().generate_with_refinement(document, llm, workflow_name)
