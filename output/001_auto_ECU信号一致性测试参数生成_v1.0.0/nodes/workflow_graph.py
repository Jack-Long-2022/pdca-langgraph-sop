"""
ECU信号一致性测试参数生成工作流
LangGraph StateGraph Implementation
"""

from typing import TypedDict, Annotated, Sequence, Union, Any, Optional
import json
import logging
from datetime import datetime
from enum import Enum

from langgraph.graph import StateGraph, END, START
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """信号类型枚举"""
    ENUM = "enum"
    PHYSICAL = "physical"
    UNKNOWN = "unknown"


class SignalState(int, Enum):
    """信号状态枚举"""
    INVALID = 0
    SENDER_ERROR = 1
    VALID = 2
    NOT_UPDATE = 3
    SENDER_ERROR_STATE = 4


class WorkflowState(TypedDict):
    """工作流状态定义"""
    raw_input: Any
    validated_input: Optional[dict]
    parsed_signal: Optional[dict]
    signal_type: Optional[str]
    can_signal_exists: Optional[bool]
    is_timestamp_signal: Optional[bool]
    has_error_condition: Optional[bool]
    out_of_range_applicable: Optional[bool]
    mapping_rules: Optional[list]
    valid_values: Optional[list]
    test_parameters: list
    diagnostics_types: list
    current_phase: str
    final_output: Optional[dict]
    errors: list
    warnings: list
    metadata: dict


def create_initial_state() -> WorkflowState:
    """创建初始状态"""
    return {
        "raw_input": None,
        "validated_input": None,
        "parsed_signal": None,
        "signal_type": None,
        "can_signal_exists": None,
        "is_timestamp_signal": None,
        "has_error_condition": None,
        "out_of_range_applicable": None,
        "mapping_rules": None,
        "valid_values": None,
        "test_parameters": [],
        "diagnostics_types": [],
        "current_phase": "initialized",
        "final_output": None,
        "errors": [],
        "warnings": [],
        "metadata": {}
    }


# ==================== Control Nodes ====================

def node_control_001_input_parsing(state: WorkflowState) -> WorkflowState:
    """
    输入解析节点
    接收并验证输入JSON信号配置，检查必要字段的完整性和类型正确性
    """
    logger.info("执行节点: node_control_001 - 输入解析")
    state["current_phase"] = "input_parsing"
    
    try:
        raw_input = state.get("raw_input")
        
        if raw_input is None:
            raise ValueError("输入数据不能为空")
        
        if isinstance(raw_input, str):
            try:
                validated_input = json.loads(raw_input)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON格式错误: {str(e)}")
        elif isinstance(raw_input, dict):
            validated_input = raw_input
        else:
            raise ValueError(f"不支持的输入类型: {type(raw_input)}")
        
        # 验证必要字段
        required_fields = ["signal_name", "can_signal_exists"]
        missing_fields = [f for f in required_fields if f not in validated_input]
        
        if missing_fields:
            raise ValueError(f"缺少必要字段: {', '.join(missing_fields)}")
        
        # 验证字段类型
        if not isinstance(validated_input.get("signal_name"), str):
            raise TypeError("signal_name必须为字符串")
        
        if not isinstance(validated_input.get("can_signal_exists"), bool):
            raise TypeError("can_signal_exists必须为布尔值")
        
        # 验证can_signal_params
        if validated_input.get("can_signal_exists"):
            if "can_signal_params" not in validated_input:
                raise ValueError("当can_signal_exists为true时，必须提供can_signal_params")
            
            can_params = validated_input["can_signal_params"]
            required_params = ["bit_length", "start_bit", "byte_order"]
            missing_params = [p for p in required_params if p not in can_params]
            
            if missing_params:
                raise ValueError(f"can_signal_params缺少字段: {', '.join(missing_params)}")
        
        state["validated_input"] = validated_input
        state["metadata"]["input_validation_time"] = datetime.now().isoformat()
        logger.info(f"输入验证成功: {validated_input.get('signal_name')}")
        
    except (ValueError, TypeError) as e:
        logger.error(f"输入验证失败: {str(e)}")
        state["errors"].append({
            "node": "node_control_001",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["validated_input"] = None
    
    return state


def node_control_002_signal_existence_routing(state: WorkflowState) -> WorkflowState:
    """
    信号存在性路由节点
    根据can_signal_exists字段决定执行路径
    """
    logger.info("执行节点: node_control_002 - 信号存在性路由")
    state["current_phase"] = "signal_existence_routing"
    
    try:
        validated_input = state.get("validated_input")
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过路由")
        
        can_signal_exists = validated_input.get("can_signal_exists", False)
        state["can_signal_exists"] = can_signal_exists
        
        state["metadata"]["routing_decision"] = {
            "node": "node_control_002",
            "can_signal_exists": can_signal_exists,
            "route": "initial_value_check" if not can_signal_exists else "timestamp_check"
        }
        
        logger.info(f"路由决策: can_signal_exists={can_signal_exists}")
        
    except Exception as e:
        logger.error(f"路由决策失败: {str(e)}")
        state["errors"].append({
            "node": "node_control_002",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
    
    return state


def node_control_003_timestamp_routing(state: WorkflowState) -> WorkflowState:
    """
    Timestamp信号路由节点
    检查信号名是否以Timestamp结尾，决定走精简策略还是完整测试流程
    """
    logger.info("执行节点: node_control_003 - Timestamp信号路由")
    state["current_phase"] = "timestamp_routing"
    
    try:
        validated_input = state.get("validated_input")
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过路由")
        
        signal_name = validated_input.get("signal_name", "")
        is_timestamp_signal = signal_name.endswith("Timestamp") or signal_name.endswith("timestamp")
        
        state["is_timestamp_signal"] = is_timestamp_signal
        
        state["metadata"]["timestamp_routing"] = {
            "signal_name": signal_name,
            "is_timestamp_signal": is_timestamp_signal,
            "route": "message_arrival" if is_timestamp_signal else "setup_generation"
        }
        
        logger.info(f"Timestamp路由: signal_name={signal_name}, is_timestamp={is_timestamp_signal}")
        
    except Exception as e:
        logger.error(f"Timestamp路由失败: {str(e)}")
        state["errors"].append({
            "node": "node_control_003",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
    
    return state


def node_control_004_error_condition_routing(state: WorkflowState) -> WorkflowState:
    """
    错误条件路由节点
    检查error_state_trigged_condition是否定义
    """
    logger.info("执行节点: node_control_004 - 错误条件路由")
    state["current_phase"] = "error_condition_routing"
    
    try:
        validated_input = state.get("validated_input")
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过路由")
        
        error_condition = validated_input.get("error_state_trigged_condition")
        has_error_condition = error_condition is not None and error_condition != {}
        
        state["has_error_condition"] = has_error_condition
        
        state["metadata"]["error_routing"] = {
            "has_error_condition": has_error_condition,
            "condition_value": error_condition,
            "route": "sender_error_generation" if has_error_condition else "valid2_recovery"
        }
        
        logger.info(f"错误条件路由: has_error_condition={has_error_condition}")
        
    except Exception as e:
        logger.error(f"错误条件路由失败: {str(e)}")
        state["errors"].append({
            "node": "node_control_004",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
    
    return state


def node_control_005_out_of_range_routing(state: WorkflowState) -> WorkflowState:
    """
    OutOfRange适用性路由节点
    比较bit_length计算的物理范围与用户输入的range_min/range_max
    """
    logger.info("执行节点: node_control_005 - OutOfRange路由")
    state["current_phase"] = "out_of_range_routing"
    
    try:
        validated_input = state.get("validated_input")
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过路由")
        
        can_params = validated_input.get("can_signal_params", {})
        bit_length = can_params.get("bit_length", 0)
        
        # 计算DBC理论范围
        dbc_max = (2 ** bit_length) - 1
        dbc_min = 0
        
        # 获取用户定义范围
        user_range_min = validated_input.get("range_min")
        user_range_max = validated_input.get("range_max")
        
        # 判断out-of-range测试是否适用
        out_of_range_applicable = False
        
        if user_range_min is not None and user_range_max is not None:
            # 当用户定义的边界小于DBC理论边界时，需要out-of-range测试
            if user_range_min > dbc_min or user_range_max < dbc_max:
                out_of_range_applicable = True
        
        state["out_of_range_applicable"] = out_of_range_applicable
        
        state["metadata"]["out_of_range_routing"] = {
            "bit_length": bit_length,
            "dbc_range": {"min": dbc_min, "max": dbc_max},
            "user_range": {"min": user_range_min, "max": user_range_max},
            "out_of_range_applicable": out_of_range_applicable,
            "route": "notupdate_out_of_range" if out_of_range_applicable else "final_teardown"
        }
        
        logger.info(f"OutOfRange路由: applicable={out_of_range_applicable}, dbc_max={dbc_max}")
        
    except Exception as e:
        logger.error(f"OutOfRange路由失败: {str(e)}")
        state["errors"].append({
            "node": "node_control_005",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
    
    return state


def node_control_006_output_formatting(state: WorkflowState) -> WorkflowState:
    """
    输出格式化节点
    将test_parameters和diagnostics_types组装为标准JSON输出格式
    """
    logger.info("执行节点: node_control_006 - 输出格式化")
    state["current_phase"] = "output_formatting"
    
    try:
        test_parameters = state.get("test_parameters", [])
        diagnostics_types = state.get("diagnostics_types", [])
        
        # 构建标准输出格式
        final_output = {
            "workflow_name": "ECU信号一致性测试参数生成",
            "generation_time": datetime.now().isoformat(),
            "signal_name": state.get("validated_input", {}).get("signal_name", "unknown"),
            "test_parameters": test_parameters,
            "diagnostics_types": diagnostics_types,
            "metadata": {
                "signal_type": state.get("signal_type"),
                "can_signal_exists": state.get("can_signal_exists"),
                "is_timestamp_signal": state.get("is_timestamp_signal"),
                "has_error_condition": state.get("has_error_condition"),
                "out_of_range_applicable": state.get("out_of_range_applicable"),
                "phases_completed": state.get("metadata", {}).get("phases", [])
            },
            "validation": {
                "errors": state.get("errors", []),
                "warnings": state.get("warnings", []),
                "is_valid": len(state.get("errors", [])) == 0
            }
        }
        
        state["final_output"] = final_output
        logger.info(f"输出格式化完成: 生成{len(test_parameters)}个测试参数")
        
    except Exception as e:
        logger.error(f"输出格式化失败: {str(e)}")
        state["errors"].append({
            "node": "node_control_006",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["final_output"] = {"error": str(e)}
    
    return state


# ==================== Thinking Nodes ====================

def node_thinking_001_signal_analyzer(state: WorkflowState) -> WorkflowState:
    """
    信号分析器节点
    解析信号类型、映射规则、CAN信号参数，计算有效值范围和测试值列表
    """
    logger.info("执行节点: node_thinking_001 - 信号分析器")
    state["current_phase"] = "signal_analysis"
    
    try:
        validated_input = state.get("validated_input")
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过分析")
        
        signal_name = validated_input.get("signal_name")
        
        # 分析信号类型
        mapping_rules = validated_input.get("mapping_rules", [])
        
        if mapping_rules and isinstance(mapping_rules, list):
            # 检查是否为枚举类型（映射规则定义明确的值映射）
            signal_type = SignalType.ENUM.value
            state["signal_type"] = signal_type
        else:
            # 物理值类型（连续值）
            signal_type = SignalType.PHYSICAL.value
            state["signal_type"] = signal_type
        
        state["mapping_rules"] = mapping_rules
        
        # 解析CAN信号参数
        can_params = validated_input.get("can_signal_params", {})
        bit_length = can_params.get("bit_length", 8)
        
        # 计算物理值范围
        physical_max = (2 ** bit_length) - 1
        physical_min = 0
        
        # 获取用户定义范围
        range_min = validated_input.get("range_min", 0)
        range_max = validated_input.get("range_max", physical_max)
        
        # 计算有效值范围
        effective_min = max(range_min, physical_min)
        effective_max = min(range_max, physical_max)
        
        # 生成测试值列表
        valid_values = []
        
        if state["signal_type"] == SignalType.ENUM.value:
            # 枚举类型：使用映射规则中的所有值
            for rule in mapping_rules:
                if "raw_value" in rule:
                    valid_values.append(rule["raw_value"])
                if "physical_value" in rule:
                    valid_values.append(rule["physical_value"])
            valid_values = list(set(valid_values))
        else:
            # 物理值类型：生成边界值和中间值
            valid_values = [effective_min]
            
            if effective_max > effective_min:
                mid_value = (effective_min + effective_max) // 2
                valid_values.append(mid_value)
                valid_values.append(effective_max)
                
                # 最小值-中间值-最大值-最小值序列
                valid_values.extend([effective_min, mid_value, effective_max, effective_min])
        
        state["valid_values"] = valid_values
        
        # 设置控制标志位
        state["parsed_signal"] = {
            "name": signal_name,
            "type": state["signal_type"],
            "bit_length": bit_length,
            "range_min": effective_min,
            "range_max": effective_max,
            "valid_values": valid_values,
            "mapping_rules_count": len(mapping_rules)
        }
        
        state["metadata"]["signal_analysis"] = {
            "signal_type": state["signal_type"],
            "valid_values_count": len(valid_values),
            "bit_length": bit_length
        }
        
        logger.info(f"信号分析完成: type={state['signal_type']}, values={len(valid_values)}")
        
    except Exception as e:
        logger.error(f"信号分析失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_001",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["diagnostics_types"].append({
            "type": "analysis_error",
            "node": "node_thinking_001",
            "description": f"信号分析过程中出现错误: {str(e)}",
            "severity": "error"
        })
    
    return state


def node_thinking_002_init_value_check_generator(state: WorkflowState) -> WorkflowState:
    """
    初始值检查生成器节点
    当CAN信号不存在时，生成check_init_value测试步骤
    """
    logger.info("执行节点: node_thinking_002 - 初始值检查生成器")
    state["current_phase"] = "init_value_check_generation"
    
    try:
        validated_input = state.get("validated_input")
        parsed_signal = state.get("parsed_signal", {})
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过生成")
        
        if not state.get("can_signal_exists", True):
            # 生成初始值检查测试步骤
            initial_value = validated_input.get("test_param_internal_signal_initial_value", 0)
            
            test_step = {
                "step_id": f"check_init_value_{int(datetime.now().timestamp())}",
                "step_type": "check_init_value",
                "description": "验证内部信号初始值",
                "action": {
                    "type": "verify_internal_signal",
                    "expected_value": initial_value,
                    "expected_status": SignalState.VALID.value,
                    "status_description": "valid"
                },
                "validation": {
                    "internal_signal_value_equals": initial_value,
                    "status_value_equals": SignalState.VALID.value
                },
                "timeout_ms": validated_input.get("timeout_ms", 5000),
                "metadata": {
                    "signal_name": parsed_signal.get("name", "unknown"),
                    "generated_at": datetime.now().isoformat()
                }
            }
            
            state["test_parameters"].append(test_step)
            
            state["diagnostics_types"].append({
                "type": "init_value_check_generated",
                "node": "node_thinking_002",
                "description": f"为非CAN信号生成初始值检查步骤，期望初始值={initial_value}",
                "severity": "info"
            })
            
            logger.info(f"初始值检查步骤已生成: initial_value={initial_value}")
        else:
            state["warnings"].append({
                "node": "node_thinking_002",
                "message": "CAN信号存在，跳过初始值检查生成",
                "timestamp": datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"初始值检查生成失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_002",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["diagnostics_types"].append({
            "type": "generation_error",
            "node": "node_thinking_002",
            "description": f"初始值检查生成失败: {str(e)}",
            "severity": "error"
        })
    
    return state


def node_thinking_003_message_arrival_handler(state: WorkflowState) -> WorkflowState:
    """
    消息到达处理器节点
    为Timestamp类型信号生成精简测试步骤
    """
    logger.info("执行节点: node_thinking_003 - 消息到达处理器")
    state["current_phase"] = "message_arrival_handling"
    
    try:
        validated_input = state.get("validated_input")
        parsed_signal = state.get("parsed_signal", {})
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过生成")
        
        if state.get("is_timestamp_signal", False):
            signal_name = parsed_signal.get("name", "unknown")
            
            # 生成消息到达测试步骤
            test_step = {
                "step_id": f"message_arrival_{int(datetime.now().timestamp())}",
                "step_type": "message_arrival",
                "description": f"验证{signal_name}报文到达后内部状态进入valid",
                "action": {
                    "type": "verify_message_arrival",
                    "expected_status": SignalState.VALID.value,
                    "status_description": "valid(2)",
                    "semantic": "内部值满足已更新语义"
                },
                "validation": {
                    "internal_status_equals": SignalState.VALID.value,
                    "value_updated": True
                },
                "timeout_ms": validated_input.get("timeout_ms", 5000),
                "metadata": {
                    "signal_name": signal_name,
                    "signal_type": "timestamp",
                    "generated_at": datetime.now().isoformat()
                }
            }
            
            state["test_parameters"].append(test_step)
            
            state["diagnostics_types"].append({
                "type": "message_arrival_step_generated",
                "node": "node_thinking_003",
                "description": f"为Timestamp信号{signal_name}生成精简消息到达测试步骤",
                "severity": "info"
            })
            
            logger.info(f"消息到达处理步骤已生成: signal={signal_name}")
        else:
            state["warnings"].append({
                "node": "node_thinking_003",
                "message": "非Timestamp信号，跳过消息到达处理",
                "timestamp": datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"消息到达处理失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_003",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["diagnostics_types"].append({
            "type": "generation_error",
            "node": "node_thinking_003",
            "description": f"消息到达处理失败: {str(e)}",
            "severity": "error"
        })
    
    return state


def node_thinking_004_setup_generator(state: WorkflowState) -> WorkflowState:
    """
    Setup生成器节点
    生成测试用例setup步骤
    """
    logger.info("执行节点: node_thinking_004 - Setup生成器")
    state["current_phase"] = "setup_generation"
    
    try:
        validated_input = state.get("validated_input")
        parsed_signal = state.get("parsed_signal", {})
        valid_values = state.get("valid_values", [])
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过生成")
        
        signal_name = parsed_signal.get("name", "unknown")
        
        # 使用有效范围内的值作为初始CAN信号值
        initial_can_value = valid_values[0] if valid_values else 0
        
        test_step = {
            "step_id": f"setup_{int(datetime.now().timestamp())}",
            "step_type": "setup",
            "description": f"设置{signal_name}的CAN信号使内部信号状态进入valid",
            "action": {
                "type": "set_can_signal",
                "can_signal_name": validated_input.get("can_signal_name", signal_name),
                "value": initial_can_value,
                "target_status": SignalState.VALID.value,
                "status_description": "valid(2)"
            },
            "setup": {
                "can_signal_value": initial_can_value,
                "expected_internal_status": SignalState.VALID.value
            },
            "metadata": {
                "signal_name": signal_name,
                "initial_value": initial_can_value,
                "generated_at": datetime.now().isoformat()
            }
        }
        
        state["test_parameters"].append(test_step)
        
        state["diagnostics_types"].append({
            "type": "setup_step_generated",
            "node": "node_thinking_004",
            "description": f"生成Setup步骤，初始CAN信号值={initial_can_value}",
            "severity": "info"
        })
        
        logger.info(f"Setup步骤已生成: initial_can_value={initial_can_value}")
        
    except Exception as e:
        logger.error(f"Setup生成失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_004",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["diagnostics_types"].append({
            "type": "generation_error",
            "node": "node_thinking_004",
            "description": f"Setup生成失败: {str(e)}",
            "severity": "error"
        })
    
    return state


def node_thinking_005_valid_scenario_generator(state: WorkflowState) -> WorkflowState:
    """
    Valid场景生成器节点
    生成valid场景测试步骤
    """
    logger.info("执行节点: node_thinking_005 - Valid场景生成器")
    state["current_phase"] = "valid_scenario_generation"
    
    try:
        validated_input = state.get("validated_input")
        parsed_signal = state.get("parsed_signal", {})
        mapping_rules = state.get("mapping_rules", [])
        signal_type = state.get("signal_type")
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过生成")
        
        signal_name = parsed_signal.get("name", "unknown")
        step_id_base = int(datetime.now().timestamp())
        
        if signal_type == SignalType.ENUM.value:
            # 枚举类型：遍历所有映射规则中的值
            if not mapping_rules:
                state["warnings"].append({
                    "node": "node_thinking_005",
                    "message": "枚举类型但映射规则为空",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                for idx, rule in enumerate(mapping_rules):
                    raw_value = rule.get("raw_value", idx)
                    physical_value = rule.get("physical_value", raw_value)
                    
                    test_step = {
                        "step_id": f"valid_enum_{step_id_base}_{idx}",
                        "step_type": "valid_scenario",
                        "description": f"验证{signal_name}枚举值{physical_value}",
                        "action": {
                            "type": "set_and_verify_enum",
                            "can_signal_value": raw_value,
                            "physical_value": physical_value,
                            "expected_status": SignalState.VALID.value
                        },
                        "validation": {
                            "internal_status_equals": SignalState.VALID.value,
                            "value_mapping": rule
                        },
                        "timeout_ms": validated_input.get("timeout_ms", 5000),
                        "metadata": {
                            "signal_name": signal_name,
                            "mapping_rule": rule,
                            "generated_at": datetime.now().isoformat()
                        }
                    }
                    
                    state["test_parameters"].append(test_step)
        else:
            # 物理值类型：最小值-中间值-最大值-最小值序列
            valid_values = state.get("valid_values", [])
            test_sequence = []
            
            # 生成完整序列
            if len(valid_values) >= 4:
                test_sequence = [
                    valid_values[0],  # 最小值
                    valid_values[1],  # 中间值
                    valid_values[2],  # 最大值
                    valid_values[3]   # 回到最小值
                ]
            elif len(valid_values) >= 2:
                test_sequence = [valid_values[0], valid_values[-1], valid_values[0]]
            else:
                test_sequence = valid_values * 3
            
            for idx, value in enumerate(test_sequence):
                test_step = {
                    "step_id": f"valid_physical_{step_id_base}_{idx}",
                    "step_type": "valid_scenario",
                    "description": f"验证{signal_name}物理值序列第{idx+1}步",
                    "action": {
                        "type": "set_and_verify_physical",
                        "can_signal_value": value,
                        "expected_status": SignalState.VALID.value
                    },
                    "validation": {
                        "internal_status_equals": SignalState.VALID.value,
                        "can_signal_value": value
                    },
                    "timeout_ms": validated_input.get("timeout_ms", 5000),
                    "metadata": {
                        "signal_name": signal_name,
                        "sequence_index": idx,
                        "total_steps": len(test_sequence),
                        "generated_at": datetime.now().isoformat()
                    }
                }
                
                state["test_parameters"].append(test_step)
        
        # 补充未覆盖值的独立步骤
        range_min = parsed_signal.get("range_min", 0)
        range_max = parsed_signal.get("range_max", 255)
        
        # 检查边界覆盖
        covered_values = [v for v in state.get("valid_values", []) if range_min <= v <= range_max]
        
        if len(covered_values) < 3 and signal_type == SignalType.PHYSICAL.value:
            # 补充边界值测试
            additional_values = []
            if range_min not in covered_values:
                additional_values.append(range_min)
            if range_max not in covered_values:
                additional_values.append(range_max)
            
            for idx, value in enumerate(additional_values):
                test_step = {
                    "step_id": f"valid_boundary_{step_id_base}_{idx}",
                    "step_type": "valid_scenario_boundary",
                    "description": f"补充验证{signal_name}边界值{value}",
                    "action": {
                        "type": "verify_boundary",
                        "can_signal_value": value,
                        "expected_status": SignalState.VALID.value
                    },
                    "validation": {
                        "internal_status_equals": SignalState.VALID.value,
                        "boundary_value": value
                    },
                    "metadata": {
                        "signal_name": signal_name,
                        "补充步骤": True,
                        "generated_at": datetime.now().isoformat()
                    }
                }
                
                state["test_parameters"].append(test_step)
        
        state["diagnostics_types"].append({
            "type": "valid_scenario_generated",
            "node": "node_thinking_005",
            "description": f"生成Valid场景测试步骤，信号类型={signal_type}",
            "severity": "info"
        })
        
        logger.info(f"Valid场景步骤已生成: {len(state['test_parameters'])}个步骤")
        
    except Exception as e:
        logger.error(f"Valid场景生成失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_005",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["diagnostics_types"].append({
            "type": "generation_error",
            "node": "node_thinking_005",
            "description": f"Valid场景生成失败: {str(e)}",
            "severity": "error"
        })
    
    return state


def node_thinking_006_notupdate_timeout_generator(state: WorkflowState) -> WorkflowState:
    """
    NotUpdate超时生成器节点
    生成notUpdate-timeout测试步骤
    """
    logger.info("执行节点: node_thinking_006 - NotUpdate超时生成器")
    state["current_phase"] = "notupdate_timeout_generation"
    
    try:
        validated_input = state.get("validated_input")
        parsed_signal = state.get("parsed_signal", {})
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过生成")
        
        signal_name = parsed_signal.get("name", "unknown")
        
        # 生成NotUpdate超时测试步骤
        test_step = {
            "step_id": f"notupdate_timeout_{int(datetime.now().timestamp())}",
            "step_type": "notupdate_timeout",
            "description": f"验证{signal_name}信号超时后状态变为notUpdate",
            "action": {
                "type": "set_signal_timeout",
                "primary_can_signal_value": [-1],  # 不发送
                "auxiliary_signal_status": f"!={SignalState.SENDER_ERROR.value}",
                "target_status": SignalState.NOT_UPDATE.value
            },
            "validation": {
                "internal_status_equals": SignalState.NOT_UPDATE.value,
                "status_description": "notUpdate(3)",
                "timeout_triggered": True
            },
            "timeout_ms": validated_input.get("notupdate_timeout_ms", 10000),
            "metadata": {
                "signal_name": signal_name,
                "timeout_value": validated_input.get("notupdate_timeout_ms", 10000),
                "generated_at": datetime.now().isoformat()
            }
        }
        
        state["test_parameters"].append(test_step)
        
        state["diagnostics_types"].append({
            "type": "notupdate_timeout_generated",
            "node": "node_thinking_006",
            "description": f"生成NotUpdate超时测试步骤，超时时间={test_step['timeout_ms']}ms",
            "severity": "info"
        })
        
        logger.info(f"NotUpdate超时步骤已生成: timeout={test_step['timeout_ms']}ms")
        
    except Exception as e:
        logger.error(f"NotUpdate超时生成失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_006",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["diagnostics_types"].append({
            "type": "generation_error",
            "node": "node_thinking_006",
            "description": f"NotUpdate超时生成失败: {str(e)}",
            "severity": "error"
        })
    
    return state


def node_thinking_007_sender_error_generator(state: WorkflowState) -> WorkflowState:
    """
    SenderError生成器节点
    根据error_state_trigged_condition生成senderError测试步骤
    """
    logger.info("执行节点: node_thinking_007 - SenderError生成器")
    state["current_phase"] = "sender_error_generation"
    
    try:
        validated_input = state.get("validated_input")
        parsed_signal = state.get("parsed_signal", {})
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过生成")
        
        error_condition = validated_input.get("error_state_trigged_condition")
        
        if error_condition and state.get("has_error_condition", False):
            signal_name = parsed_signal.get("name", "unknown")
            
            # 解析触发条件
            trigger_signal = error_condition.get("trigger_signal", signal_name)
            trigger_value = error_condition.get("trigger_value", -1)
            
            test_step = {
                "step_id": f"sender_error_{int(datetime.now().timestamp())}",
                "step_type": "sender_error",
                "description": f"验证{signal_name}触发senderError状态",
                "action": {
                    "type": "trigger_sender_error",
                    "trigger_signal": trigger_signal,
                    "trigger_value": trigger_value,
                    "target_status": SignalState.SENDER_ERROR.value
                },
                "validation": {
                    "internal_status_equals": SignalState.SENDER_ERROR.value,
                    "status_description": "senderError(4)",
                    "error_triggered": True
                },
                "timeout_ms": validated_input.get("timeout_ms", 5000),
                "metadata": {
                    "signal_name": signal_name,
                    "error_condition": error_condition,
                    "generated_at": datetime.now().isoformat()
                }
            }
            
            state["test_parameters"].append(test_step)
            
            state["diagnostics_types"].append({
                "type": "sender_error_generated",
                "node": "node_thinking_007",
                "description": f"生成SenderError测试步骤，触发条件={error_condition}",
                "severity": "info"
            })
            
            logger.info(f"SenderError步骤已生成: condition={error_condition}")
        else:
            state["warnings"].append({
                "node": "node_thinking_007",
                "message": "未定义错误触发条件，跳过SenderError生成",
                "timestamp": datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"SenderError生成失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_007",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["diagnostics_types"].append({
            "type": "generation_error",
            "node": "node_thinking_007",
            "description": f"SenderError生成失败: {str(e)}",
            "severity": "error"
        })
    
    return state


def node_thinking_008_valid2_recovery(state: WorkflowState) -> WorkflowState:
    """
    Valid2中间恢复节点
    生成valid2中间恢复步骤
    """
    logger.info("执行节点: node_thinking_008 - Valid2中间恢复")
    state["current_phase"] = "valid2_recovery"
    
    try:
        validated_input = state.get("validated_input")
        parsed_signal = state.get("parsed_signal", {})
        valid_values = state.get("valid_values", [])
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过生成")
        
        signal_name = parsed_signal.get("name", "unknown")
        
        # 使用最大值恢复状态
        recovery_value = max(valid_values) if valid_values else parsed_signal.get("range_max", 255)
        
        test_step = {
            "step_id": f"valid2_recovery_{int(datetime.now().timestamp())}",
            "step_type": "valid2_recovery",
            "description": f"恢复{signal_name}信号状态为valid，为后续测试做准备",
            "action": {
                "type": "recover_to_valid",
                "can_signal_value": recovery_value,
                "target_status": SignalState.VALID.value,
                "status_description": "valid(2)"
            },
            "validation": {
                "internal_status_equals": SignalState.VALID.value,
                "recovery_value": recovery_value,
                "preparation_for_out_of_range": True
            },
            "metadata": {
                "signal_name": signal_name,
                "recovery_value": recovery_value,
                "generated_at": datetime.now().isoformat()
            }
        }
        
        state["test_parameters"].append(test_step)
        
        state["diagnostics_types"].append({
            "type": "valid2_recovery_generated",
            "node": "node_thinking_008",
            "description": f"生成Valid2中间恢复步骤，恢复值={recovery_value}",
            "severity": "info"
        })
        
        logger.info(f"Valid2恢复步骤已生成: recovery_value={recovery_value}")
        
    except Exception as e:
        logger.error(f"Valid2恢复生成失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_008",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["diagnostics_types"].append({
            "type": "generation_error",
            "node": "node_thinking_008",
            "description": f"Valid2恢复生成失败: {str(e)}",
            "severity": "error"
        })
    
    return state


def node_thinking_009_notupdate_out_of_range_generator(state: WorkflowState) -> WorkflowState:
    """
    NotUpdate越界生成器节点
    生成notUpdate2越界测试步骤
    """
    logger.info("执行节点: node_thinking_009 - NotUpdate越界生成器")
    state["current_phase"] = "notupdate_out_of_range_generation"
    
    try:
        validated_input = state.get("validated_input")
        parsed_signal = state.get("parsed_signal", {})
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过生成")
        
        signal_name = parsed_signal.get("name", "unknown")
        user_range_min = validated_input.get("range_min", 0)
        user_range_max = validated_input.get("range_max", 255)
        dbc_range_max = parsed_signal.get("range_max", 255)
        
        # 生成超出用户定义范围但仍在DBC范围内的值
        out_of_range_value = None
        
        if user_range_max < dbc_range_max:
            # 超出上限
            out_of_range_value = user_range_max + 1
        elif user_range_min > 0:
            # 超出下限
            out_of_range_value = user_range_min - 1
        else:
            # 使用超出范围的最大值
            out_of_range_value = dbc_range_max + 1 if dbc_range_max < 255 else dbc_range_max
        
        if state.get("out_of_range_applicable", False):
            test_step = {
                "step_id": f"notupdate_out_of_range_{int(datetime.now().timestamp())}",
                "step_type": "notupdate_out_of_range",
                "description": f"验证{signal_name}信号越界后状态变为notUpdate",
                "action": {
                    "type": "set_out_of_range",
                    "can_signal_value": out_of_range_value,
                    "user_range": {"min": user_range_min, "max": user_range_max},
                    "dbc_range": {"min": 0, "max": dbc_range_max},
                    "target_status": SignalState.NOT_UPDATE.value
                },
                "validation": {
                    "internal_status_equals": SignalState.NOT_UPDATE.value,
                    "status_description": "notUpdate(3)",
                    "out_of_range_value": out_of_range_value
                },
                "timeout_ms": validated_input.get("timeout_ms", 5000),
                "metadata": {
                    "signal_name": signal_name,
                    "out_of_range_value": out_of_range_value,
                    "generated_at": datetime.now().isoformat()
                }
            }
            
            state["test_parameters"].append(test_step)
            
            state["diagnostics_types"].append({
                "type": "notupdate_out_of_range_generated",
                "node": "node_thinking_009",
                "description": f"生成NotUpdate越界测试步骤，越界值={out_of_range_value}",
                "severity": "info"
            })
            
            logger.info(f"NotUpdate越界步骤已生成: out_of_range_value={out_of_range_value}")
        else:
            state["warnings"].append({
                "node": "node_thinking_009",
                "message": "OutOfRange测试不适用，跳过越界生成",
                "timestamp": datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"NotUpdate越界生成失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_009",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["diagnostics_types"].append({
            "type": "generation_error",
            "node": "node_thinking_009",
            "description": f"NotUpdate越界生成失败: {str(e)}",
            "severity": "error"
        })
    
    return state


def node_thinking_010_final_teardown(state: WorkflowState) -> WorkflowState:
    """
    最终Teardown节点
    生成最终teardown步骤
    """
    logger.info("执行节点: node_thinking_010 - 最终Teardown")
    state["current_phase"] = "final_teardown"
    
    try:
        validated_input = state.get("validated_input")
        parsed_signal = state.get("parsed_signal", {})
        
        if validated_input is None:
            raise RuntimeError("validated_input不存在，跳过生成")
        
        signal_name = parsed_signal.get("name", "unknown")
        final_value = parsed_signal.get("range_min", 0)
        
        test_step = {
            "step_id": f"teardown_{int(datetime.now().timestamp())}",
            "step_type": "teardown",
            "description": f"最终Teardown: 恢复{signal_name}信号状态为valid",
            "action": {
                "type": "final_teardown",
                "can_signal_value": final_value,
                "target_status": SignalState.VALID.value,
                "status_description": "valid(2)"
            },
            "validation": {
                "internal_status_equals": SignalState.VALID.value,
                "final_value": final_value,
                "cleanup_complete": True
            },
            "metadata": {
                "signal_name": signal_name,
                "final_value": final_value,
                "generated_at": datetime.now().isoformat()
            }
        }
        
        state["test_parameters"].append(test_step)
        
        state["diagnostics_types"].append({
            "type": "teardown_generated",
            "node": "node_thinking_010",
            "description": f"生成最终Teardown步骤，最终值={final_value}",
            "severity": "info"
        })
        
        logger.info(f"最终Teardown步骤已生成: final_value={final_value}")
        
    except Exception as e:
        logger.error(f"Teardown生成失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_010",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        state["diagnostics_types"].append({
            "type": "generation_error",
            "node": "node_thinking_010",
            "description": f"Teardown生成失败: {str(e)}",
            "severity": "error"
        })
    
    return state


def node_thinking_011_diagnostics_generator(state: WorkflowState) -> WorkflowState:
    """
    诊断信息生成器节点
    汇总所有前序节点产生的诊断信息
    """
    logger.info("执行节点: node_thinking_011 - 诊断信息生成器")
    state["current_phase"] = "diagnostics_generation"
    
    try:
        validated_input = state.get("validated_input")
        parsed_signal = state.get("parsed_signal", {})
        errors = state.get("errors", [])
        warnings = state.get("warnings", [])
        
        # 整体推断
        overall_inference = {
            "workflow_completed": True,
            "total_steps_generated": len(state.get("test_parameters", [])),
            "total_errors": len(errors),
            "total_warnings": len(warnings),
            "signal_type_detected": state.get("signal_type"),
            "can_signal_exists": state.get("can_signal_exists"),
            "is_timestamp_signal": state.get("is_timestamp_signal"),
            "has_error_condition": state.get("has_error_condition"),
            "out_of_range_applicable": state.get("out_of_range_applicable")
        }
        
        state["diagnostics_types"].append({
            "type": "overall_inference",
            "node": "node_thinking_011",
            "description": "整体工作流推断",
            "details": overall_inference,
            "severity": "info"
        })
        
        # 疑问和建议
        questions_and_suggestions = []
        
        if parsed_signal:
            if parsed_signal.get("mapping_rules_count", 0) == 0 and state.get("signal_type") == SignalType.ENUM.value:
                questions_and_suggestions.append({
                    "type": "question",
                    "message": "信号被识别为枚举类型但未提供映射规则，是否需要补充映射规则？"
                })
            
            if not state.get("out_of_range_applicable", False):
                questions_and_suggestions.append({
                    "type": "suggestion",
                    "message": "OutOfRange测试不适用，可能需要检查DBC定义与用户输入范围是否一致"
                })
        
        if errors:
            questions_and_suggestions.append({
                "type": "warning",
                "message": f"工作流执行过程中出现{len(errors)}个错误，建议检查输入数据"
            })
        
        if questions_and_suggestions:
            state["diagnostics_types"].append({
                "type": "questions_and_suggestions",
                "node": "node_thinking_011",
                "description": "疑问和建议汇总",
                "details": questions_and_suggestions,
                "severity": "warning"
            })
        
        # 记录所有推断过程中的疑点
        all_diagnostics_summary = {
            "total_diagnostics": len(state["diagnostics_types"]),
            "diagnostic_types_present": list(set([d.get("type") for d in state["diagnostics_types"]])),
            "severity_levels": list(set([d.get("severity") for d in state["diagnostics_types"]]))
        }
        
        state["diagnostics_types"].append({
            "type": "diagnostics_summary",
            "node": "node_thinking_011",
            "description": "诊断信息汇总",
            "details": all_diagnostics_summary,
            "severity": "info"
        })
        
        state["metadata"]["diagnostics_generation"] = {
            "total_diagnostics": len(state["diagnostics_types"]),
            "questions_count": len(questions_and_suggestions)
        }
        
        logger.info(f"诊断信息生成完成: {len(state['diagnostics_types'])}条诊断记录")
        
    except Exception as e:
        logger.error(f"诊断信息生成失败: {str(e)}")
        state["errors"].append({
            "node": "node_thinking_011",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
    
    return state


# ==================== Routing Functions ====================

def route_from_control_002(state: WorkflowState) -> str:
    """从node_control_002路由"""
    if state.get("can_signal_exists") is False:
        return "initial_value_check"
    else:
        return "timestamp_check"


def route_from_control_003(state: WorkflowState) -> str:
    """从node_control_003路由"""
    if state.get("is_timestamp_signal", False):
        return "message_arrival"
    else:
        return "setup_generation"


def route_from_control_004(state: WorkflowState) -> str:
    """从node_control_004路由"""
    if state.get("has_error_condition", False):
        return "sender_error_generation"
    else:
        return "valid2_recovery"


def route_from_control_005(state: WorkflowState) -> str:
    """从node_control_005路由"""
    if state.get("out_of_range_applicable", False):
        return "notupdate_out_of_range"
    else:
        return "final_teardown"


# ==================== Workflow Builder ====================

def build_workflow() -> StateGraph:
    """
    构建ECU信号一致性测试参数生成工作流
    """
    # 创建状态图
    workflow = StateGraph(WorkflowState)
    
    # 添加所有节点
    # Control节点
    workflow.add_node("node_control_001", node_control_001_input_parsing)
    workflow.add_node("node_control_002", node_control_002_signal_existence_routing)
    workflow.add_node("node_control_003", node_control_003_timestamp_routing)
    workflow.add_node("node_control_004", node_control_004_error_condition_routing)
    workflow.add_node("node_control_005", node_control_005_out_of_range_routing)
    workflow.add_node("node_control_006", node_control_006_output_formatting)
    
    # Thinking节点
    workflow.add_node("node_thinking_001", node_thinking_001_signal_analyzer)
    workflow.add_node("node_thinking_002", node_thinking_002_init_value_check_generator)
    workflow.add_node("node_thinking_003", node_thinking_003_message_arrival_handler)
    workflow.add_node("node_thinking_004", node_thinking_004_setup_generator)
    workflow.add_node("node_thinking_005", node_thinking_005_valid_scenario_generator)
    workflow.add_node("node_thinking_006", node_thinking_006_notupdate_timeout_generator)
    workflow.add_node("node_thinking_007", node_thinking_007_sender_error_generator)
    workflow.add_node("node_thinking_008", node_thinking_008_valid2_recovery)
    workflow.add_node("node_thinking_009", node_thinking_009_notupdate_out_of_range_generator)
    workflow.add_node("node_thinking_010", node_thinking_010_final_teardown)
    workflow.add_node("node_thinking_011", node_thinking_011_diagnostics_generator)
    
    # 设置入口点
    workflow.set_entry_point("node_control_001")
    
    # 添加边 - 主流程
    workflow.add_edge("node_control_001", "node_thinking_001")
    workflow.add_edge("node_thinking_001", "node_control_002")
    
    # node_control_002的条件路由
    workflow.add_conditional_edges(
        "node_control_002",
        route_from_control_002,
        {
            "initial_value_check": "node_thinking_002",
            "timestamp_check": "node_control_003"
        }
    )
    
    # node_control_003的条件路由
    workflow.add_conditional_edges(
        "node_control_003",
        route_from_control_003,
        {
            "message_arrival": "node_thinking_003",
            "setup_generation": "node_thinking_004"
        }
    )
    
    # 后续顺序连接
    workflow.add_edge("node_thinking_004", "node_thinking_005")
    workflow.add_edge("node_thinking_005", "node_thinking_006")
    workflow.add_edge("node_thinking_006", "node_control_004")
    
    # node_control_004的条件路由
    workflow.add_conditional_edges(
        "node_control_004",
        route_from_control_004,
        {
            "sender_error_generation": "node_thinking_007",
            "valid2_recovery": "node_thinking_008"
        }
    )
    
    workflow.add_edge("node_thinking_007", "node_thinking_008")
    workflow.add_edge("node_thinking_008", "node_control_005")
    
    # node_control_005的条件路由
    workflow.add_conditional_edges(
        "node_control_005",
        route_from_control_005,
        {
            "notupdate_out_of_range": "node_thinking_009",
            "final_teardown": "node_thinking_010"
        }
    )
    
    workflow.add_edge("node_thinking_009", "node_thinking_010")
    
    # 汇聚到诊断节点
    workflow.add_edge("node_thinking_002", "node_thinking_011")
    workflow.add_edge("node_thinking_003", "node_thinking_011")
    workflow.add_edge("node_thinking_010", "node_thinking_011")
    
    # 诊断节点到输出格式化
    workflow.add_edge("node_thinking_011", "node_control_006")
    
    # 设置结束点
    workflow.set_finish_point("node_control_006")

    return workflow.compile()


def create_compiled_workflow():
    """
    创建并编译工作流
    """
    workflow = build_workflow()
    compiled_workflow = workflow.compile()
    
    return compiled_workflow


# ==================== Main Execution ====================

def run_workflow(input_data: dict) -> dict:
    """
    运行ECU信号一致性测试参数生成工作流
    
    Args:
        input_data: 输入信号配置字典
        
    Returns:
        生成的测试参数字典
    """
    try:
        logger.info("开始执行ECU信号一致性测试参数生成工作流")
        
        # 创建初始状态
        initial_state = create_initial_state()
        initial_state["raw_input"] = input_data
        initial_state["metadata"]["workflow_start_time"] = datetime.now().isoformat()
        
        # 创建并运行编译后的工作流
        compiled_workflow = create_compiled_workflow()
        
        # 执行工作流
        result = compiled_workflow.invoke(initial_state)
        
        logger.info(f"工作流执行完成，生成{len(result.get('test_parameters', []))}个测试参数")
        
        return result.get("final_output", {})
        
    except Exception as e:
        logger.error(f"工作流执行失败: {str(e)}")
        return {
            "error": str(e),
            "workflow_status": "failed",
            "timestamp": datetime.now().isoformat()
        }


def run_workflow_with_stream(input_data: dict):
    """
    使用流式方式运行工作流
    
    Args:
        input_data: 输入信号配置字典
        
    Yields:
        每个节点的中间状态
    """
    try:
        logger.info("开始流式执行ECU信号一致性测试参数生成工作流")
        
        initial_state = create_initial_state()
        initial_state["raw_input"] = input_data
        initial_state["metadata"]["workflow_start_time"] = datetime.now().isoformat()
        
        compiled_workflow = create_compiled_workflow()
        
        for state in compiled_workflow.stream(initial_state):
            node_name = list(state.keys())[0] if state else "unknown"
            logger.info(f"节点完成: {node_name}")
            yield state
            
    except Exception as e:
        logger.error(f"流式执行失败: {str(e)}")
        yield {"error": str(e)}


# ==================== Example Usage ====================

if __name__ == "__main__":
    # 示例输入数据
    sample_input = {
        "signal_name": "EngineSpeed",
        "can_signal_exists": True,
        "can_signal_name": "EngineSpeed_CAN",
        "can_signal_params": {
            "bit_length": 16,
            "start_bit": 0,
            "byte_order": "little_endian",
            "factor": 0.25,
            "offset": 0
        },
        "range_min": 0,
        "range_max": 8000,
        "mapping_rules": [],
        "timeout_ms": 5000,
        "notupdate_timeout_ms": 10000,
        "test_param_internal_signal_initial_value": 0,
        "error_state_trigged_condition": {
            "trigger_signal": "EngineSpeed_CAN",
            "trigger_value": -1
        }
    }
    
    # 运行工作流
    print("=" * 60)
    print("ECU信号一致性测试参数生成工作流")
    print("=" * 60)
    
    result = run_workflow(sample_input)
    
    # 输出结果
    print("\n生成结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    print(f"\n统计信息:")
    print(f"  - 测试参数数量: {len(result.get('test_parameters', []))}")
    print(f"  - 诊断信息数量: {len(result.get('diagnostics_types', []))}")
    print(f"  - 验证状态: {'有效' if result.get('validation', {}).get('is_valid') else '无效'}")