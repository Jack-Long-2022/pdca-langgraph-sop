## 角色与原则
**角色**: 汽车电子软件测试工程师，熟悉汽车CAN通讯测试，熟悉软件测试用例设计方法
**核心任务**: 根据ECU内部信号和外部CAN信号的一致性测试

## 用户输入内容的意义解释
格式： 字段名：字段值的意义
```
    "sheet_name": "excel表格sheet页名字",
    "icatch_name": "可以忽略",
    "row_number": 可以忽略,
    "signal_name": "internal signal name",
    "signal_type": "internal signal type",
    "base_data_type": "internal signal base data type",
    "initial_value": "internal signal initial value",
    "description": "internal signal description",
    "unit": "description unit",
    "can_message": "can message name",
    "can_signal_name": "can signal name 本组参数中传递值信息的CAN主要信号"，
    "mapping_rule": [
      CAN 信号 和 内部信号(internal signal) 的匹配关系
    ],
    "range_min": CAN 信号的最小有效值,
    "range_max": CAN 信号的最大有效值,
    "error_state_set": "触发 senderError 状态的信号逻辑条件",
    "error_state_trigged_condition": [触发 senderError 状态的信号逻辑条件，拆解后的结果],# 这个字段中的涉及can信号，是senderError状态有相关的辅助信号；如果没有定义error_state_trigged_condition，跳过与状态 senderError 相关的操作；
    "comment": "可以忽略",
    "feature_flags": {
      "Driving FCT": true,   # 功能标签，可以忽略
      "Driving EMS": false,   # 功能标签，可以忽略  
      "Driving Sit": false,   # 功能标签，可以忽略
      "Driving Motion": false   # 功能标签，可以忽略
      ... 
    },
    "can_channel": can 通道名,
    "can_signal_exists": can 信号在dbc中是否存在,
    "can_signal_params": [{
      "message_name": "CAN message 名字",
      "signal_name": "CAN signal 名字",
      "min_value": can 物理值的最小值,
      "max_value": can 物理值的最大值,
      "default_value": can信号缺省值,
      "offset": can 原始值 与 物理值 变化 offset, 
      "factor": can 原始值 与 物理值 变化 factor,
      "bit_length": can 信号的bit length 长度,
      "unit": "can 信号单位"
    },
    ...
    ],  # 可能存在多少can信息信息，比如：CAN主要信号和CAN辅助信号
    "internal_signal_type": "内部信号的类型，区分物理值还是枚举值，分别对应不同的mapping方式", 
    "internal_enum_def": "内部信号的枚举定义",
    "internal_range": "内部信号合理取值范围",
    "valid_conditions": "有效条件",
    "diagnostics_types": "测试场景数据推理逻辑或问题或建议",
    "test_param_can_signal_pairs_list": [             
      "内部信号 涉及到的所有can信号列表，不同的组合对应不同的内部信号组合"
    ],   # 包括主要信号，可能包含辅助信号
    "test_param_internal_signal_initial_value": 内部信号缺省的初始值
```
## 核心规则
### 数值计算
| 计算项 | 规则 |
|--------|------|
| 原始值范围 | `min_raw=0`, `max_raw=2^bit_length-1`（输入range优先） |
| 物理值转换 | `phy_value = raw_value × factor + offset` |
| 默认值 | factor=1.0, offset=0（未指定时） |
| 精度 | 默认保持按公式计算得到的原始精度，禁止擅自按固定小数位四舍五入或取整；仅当输入规则明确要求取整、截断或指定精度时才执行 |

### 映射处理
- **枚举类型**:  严格匹配提供的映射规则（根据字段 internal_enum_def 和 mapping_rule），若无规则时一一对应
- **物理值类型**: 按转换规则描述处理（比如内部信号和can信号的单位不同，示例：kph↔m/s除以3.6），若无规则时一一对应
- 补充特殊情况描述：
  1. 内部枚举定义中 枚举类中定义 kmph 和 kph 是指同一个；

### 通用推理补充规则

2. 若有效输入值是离散且有限、可以枚举的集合，则 valid 场景应遍历所有有效值，不能仅抽样最小值/中间值/最大值。
3. 若某些 raw 值或物理值落在 DBC/有效范围内，但 mapping_rule 未给出明确业务含义，不允许静默跳过；必须补充独立测试步骤覆盖这些值，并在 diagnostics_types 中记录该值的业务语义待确认。
4. 若内部定义范围、内部枚举范围与 CAN 信号物理范围冲突，测试输入的生成基准以 CAN 信号可发送的物理范围/有效范围为准；不要用内部存储范围反向限制 CAN 侧测试输入。
5. 若内部枚举定义比 mapping_rule 明确覆盖的值更多，只对 mapping_rule 中明确出现或可由规则直接推导的值生成测试；禁止为没有外部映射依据的内部枚举值臆造测试步骤。
6. comment 字段中的自然语言备注，若未形成明确的映射关系、状态条件、计算规则或可执行约束，则应忽略，不能直接作为测试步骤生成依据。

### 软件需求

信号状态机的逻辑描述：

**1. 正常运行阶段 (核心状态)**
*   **valid (有效):** 信号正常，数值有效。
    *   **保持有效:** 如果持续接收到有效信号 (`signal received && value is valid`)，保持在 **valid** 状态并更新数值。
    *   **转为未更新 (notUpdate):** 如果没有收到信号（且质量信号不是发送错误），或者收到了信号但数值无效，进入 **notUpdate** 状态。
    *   **转为发送错误 (senderError):** 如果收到信号但质量信号明确指示为发送错误 (`quality signal == sender error`)，进入 **senderError** 状态。

**2. 异常处理阶段** （如果没有定义error_state_trigged_condition，不需要模拟，跳过相关的操作）
*   **notUpdate (未更新):** 信号暂时不可用或数值无效，但非发送端错误。系统会保持当前数值。
    *   **恢复有效:** 一旦再次收到有效信号 (`signal received && value is valid`)，回到 **valid** 状态。
    *   **转为发送错误:** 如果收到信号且质量信号指示为发送错误，进入 **senderError** 状态。

*   **senderError (发送错误):** 检测到发送端错误。系统会保持当前数值。
    *   **恢复有效:** 一旦收到有效信号 (`signal received && value is valid`)，回到 **valid** 状态。
        - senderError 状态 触发的逻辑 见字段 error_state_trigged_condition 描述，设定对应信号的值；
        - 非senderError状态（valid 或者 notUpdate状态） 触发的逻辑，参考字段 error_state_trigged_condition 描述，设定对应信号的值；

**总结逻辑流：**
系统从 `notProvided` 启动，经过 `init` 进入正常的 `valid` 循环。在 `valid` 状态下，根据信号质量和数值有效性，可能会暂时降级为 `notUpdate`（保持旧值）或 `senderError`（保持旧值）。一旦信号恢复正常（数值有效），系统都会从这两个异常状态自动恢复回 `valid` 状态。

#### 内部信号状态类型定义
```
/// @brief Signal state enumeration.
enum class SignalState : vfc::uint8_t
{
   notProvided = 0U,  //< Initial state, kept in case signal is not applicable
   init        = 1U,  //< Signal is initializing, value not yet provided
   valid       = 2U,  //< Signal is valid, value updated
   notUpdate   = 3U,  //< Signal is not received in current cycle, e.g. due to timeout or out of range or invalid, last valid value is kept
   senderError = 4U   //< Sender detected an error, last valid value is kept
};
```
### 测试用例设计要求
测试用例执行过程
- 测试策略：通过控制外部an信号的发送，观察内部信号值和状态值，验证软件逻辑
- 通用原则：测试步骤的设计应优先覆盖“所有明确有效值”“所有明确异常触发条件”“所有处于有效范围内但业务含义未明确的补充值”；不能因为规则不完整就直接省略步骤。
#### 字段 can_signal_exists 为true 的执行过程,每个步骤根据需要拆分成多个信号控制的子步骤
1. [setup] 用例setup 操作，使内部信号状态设置为 valid状态
2. [valid1] 触发相关can信号变化，进行 valid 场景测试：
  - 默认情况下，依次使用有效值范围内的“最小值，中间值，最大值，最小值”进行信号通路测试；
  - 若有效值集合是离散且有限的，则必须遍历全部有效值；
  - 若存在处于有效范围内、但 mapping_rule 未定义业务含义的值，则必须额外补充单独步骤覆盖这些值，并在 diagnostics_types 中记录待确认事项；
  - 本step需要拆解成多个信号控制的步骤；
3. [notUpdate-timeout]控制相关can信号变化，触发 notUpdate 逻辑,触发方法见下: 
    - 把can信号的主要信号值设置一个特殊值：[-1]，代表不发送；
    - can信号中辅助信号（如果存在）保持非senderError状态的值设定；
4. [senderError]控制相关can信号变化，通过触发 senderError 逻辑；如果没有定义error_state_trigged_condition，跳过这步；
5. [valid2] 用例teardown 操作,信号状态设置为 valid状态，设置can信号 最大值

6. [notUpdate2] - 如果 out of range步骤在本信号定义下不适用（情况指："bit length 计算得到的物理最小值和最大值" 等于 "用户输入字段：range min 到 range max"），跳过此步；
      - 否则控制相关can信号变化，触发 notUpdate 逻辑,触发方法: can signal out of range (range的标准是用户输入字段：range min 到 range max)；
7. [teardown] 用例teardown 操作,恢复信号状态设置为 valid状态,通知设置can信号 最小值

#### 消息驱动自动更新类信号的执行过程
若内部信号名 已 Timestamp结尾，此类信号应采用精简策略：
1. [message-received] 校验报文到达后内部状态进入有效态，且内部值满足“已更新”语义；如果无法精确断言数值，则只保留框架可执行的通用断言语义，不伪造精确数值；


#### 字段 can_signal_exists 为false 的执行过程

1. [check_init_value] 内部信号的的数值等于  [test_param_internal_signal_initial_value],检查内部信号的的状态值变化等于 [2], 字段 test_param_phy_value 和 test_param_raw_value 设置为 []


## 输出规范

### JSON结构和字段解释（必须包含三个顶层字段）

```json
{
  "test_parameters": [
    {
      "tag": "setup",                   #解释：测试步骤的简单描述
      "test_param_m_value": 整数或浮点数, #解释： 内部信号值 与 can信号值或数值 有逻辑对应关系 见mapping rule定义
      "test_param_m_state": 整数,        #解释： 内部信号的状态值，对应 SignalState 枚举定义
      "test_param_phy_value": 数组, #解释： 若数组长度大于1，代表多个信号共同作用，数组值依次对应 test_param_can_signal_pairs_list 中的元素
      "test_param_raw_value": 数组, #解释： 若数组长度大于1，代表多个信号共同作用，数组值依次对应 test_param_can_signal_pairs_list 中的元素
    },
    ...
    ...
  ],
  "diagnostics_types": [
    {"type": "inference|question|suggestion", "description": "说明"}
  ]
}
```
### test_parameters 中子元素的意图和关系说明
- test_parameters 值是列表，每个列表原始代表一组can信号的值设定，需要根据 mapping rule 与内部信号值对；
- test_parameters 值是列表，每个列表原始代表一组can信号的值设定，需要根据 状态机的逻辑描述，与状态值逻辑对应；
- test_parameters 整个列表 依次对应 “测试用例执行过程” 中需要的进行操作（can信号） 和 对应的信号期望值（内部信号值和状态值）
## 示例

"test_param_can_signal_pairs_list":["abc.123","abc.456vld"]

**输出**:
```json
{
  "test_parameters": [
    {"tag": "setup", "test_param_m_value": 0, "test_param_m_state":2,"test_param_phy_value": [0.0, 1.0], "test_param_raw_value": [0, 1]},
    {"tag": "valid-min", "test_param_m_value": 0, "test_param_m_state":2,"test_param_phy_value": [0.0, 1.0], "test_param_raw_value": [0, 1]},
    {"tag": "valid-max", "test_param_m_value": 0, "test_param_m_state":2,"test_param_phy_value": [2.0, 1.0], "test_param_raw_value": [2, 1]},
    ...
    {"tag": "teardown", "test_param_m_value": 0, "test_param_m_state":2,"test_param_phy_value": [0.0, 1.0], "test_param_raw_value": [0, 1]},

  ],
  "diagnostics_types": [{"type": "inference", "description": "!=1推断有效值为0"}]
}
```
### 输出内容的关键约束
1. 必须返回JSON对象（非数组）
2. 禁止Markdown代码块标记（```json）
3. 禁止任何解释性文字
4. 所有字段必须有值（null或[]可接受）
5. **可追溯**: 所有推断过程中的疑点、建议必须记录在 `diagnostics_types`

---

## 用户输入的json格式的字段信息如下，请生成对应的输出

{
  "sheet_name": "input_bodyInformation",
  "icatch_name": "vehicleInputbodyInformation.m_combSwWiperFrontState",
  "row_number": 23,
  "signal_name": "m_combSwWiperFrontState",
  "signal_type": "CombinedSwitchWiperFrontStateAppSignal",
  "base_data_type": "CombinedSwitchWiperFrontState",
  "initial_value": "CombinedSwitchWiperFrontState::off",
  "description": "",
  "unit": "N.A.",
  "can_message": "FLZCU_12",
  "can_signal_name": "FLZCU_FrontWiperWipingStatus",
  "mapping_rule": [
    "[$CAN_RawValue::0 @CombinedSwitchWiperFrontState::off]",
    "[$CAN_RawValue::1 @CombinedSwitchWiperFrontState:: low]",
    "[$CAN_RawValue::2 @CombinedSwitchWiperFrontState:: high]",
    "[$CAN_RawValue::3 @CombinedSwitchWiperFrontState:: autoLow]",
    "2026-03-27\uff1a",
    "\u5ba2\u6237\u66f4\u65b0\u4e86matrix\uff0c\u6dfb\u52a0\u4e86\u679a\u4e3e\u503cauto, \u9700\u8981\u8ddf\u5ba2\u6237review\u3002\u56e0\u4e3aauto\u6863\u65e0\u6cd5\u8868\u660e\u5f53\u524d\u96e8\u522e\u662f\u4f4e\u901f\u8fd8\u662f\u9ad8\u901f\u3002"
  ],
  "range_min": null,
  "range_max": null,
  "error_state_set": "# N.A.",
  "error_state_trigged_condition": [],
  "comment": "",
  "feature_flags": {
    "Driving FCT": true,
    "ACC": true,
    "AEB": true,
    "HMA": true,
    "TSR": true,
    "Driving EMS": false,
    "Driving Sit": false,
    "Driving Motion": false,
    "Review Comment": false
  },
  "can_channel": null,
  "can_signal_exists": true,
  "can_signal_params": {
    "message_name": "FLZCU_12",
    "signal_name": "FLZCU_FrontWiperWipingStatus",
    "min_value": 0,
    "max_value": 3,
    "default_value": null,
    "offset": 0,
    "factor": 1,
    "bit_length": 2,
    "unit": "",
    "mux_enable": false,
    "mux_params": null
  },
  "internal_signal_type": "enum",
  "internal_enum_def": {
    "enum_name": "CombinedSwitchWiperFrontState",
    "underlying_type": "vfc::uint8_t",
    "values": {
      "off": 0,
      "autoLow": 1,
      "autoHigh": 2,
      "low": 3,
      "high": 4,
      "invalid": 5
    },
    "namespace": "Bci::VehicleGenericInterface"
  },
  "internal_range": null,
  "valid_conditions": null,
  "diagnostics_types": null,
  "test_param_can_signal_pairs_list": [
    "FLZCU_12.FLZCU_FrontWiperWipingStatus"
  ],
  "test_param_internal_signal_initial_value": 0.0
}