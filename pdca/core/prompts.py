"""集中管理的系统提示词和用户提示词模板"""

# ============== 系统提示词 ==============

SYSTEM_PROMPTS = {
    "extract": (
        "你是工作流架构师。从用户描述中提取结构化工作流定义。"
        "输出严格的JSON，不要有其他内容。"
    ),
    "config": (
        "你是配置工程师。将结构化数据转为完整的LangGraph工作流配置。"
        "优化节点定义、边连接和状态设计。输出严格的JSON。"
    ),
    "code": (
        "你是Python代码专家。为LangGraph工作流生成可执行代码。"
        "使用LangGraph的StateGraph API。只输出Python代码，不要解释。"
    ),
    "test": (
        "你是测试工程师。为工作流生成验收标准和测试用例。"
        "覆盖正常、边界和异常场景。输出严格的JSON。"
    ),
    "report": (
        "你是质量分析师。分析测试结果，输出评估报告。"
        "包含通过率、问题列表和改进建议。输出严格的JSON。"
    ),
    "review": (
        "你是PDCA复盘专家。按GRBARP方法进行复盘："
        "目标回顾(Goal Review)、结果分析(Result Analysis)、"
        "行动规划(Action Planning)、验证规划(Validation Planning)。"
        "同时给出优化建议。输出严格的JSON。"
    ),
}

# ============== 角色路由映射 ==============

PLANNER_TASKS = {"extract", "config", "review"}

# ============== 用户提示词模板 ==============

EXTRACT_PROMPT = """从以下描述中提取完整的工作流定义：

{text}

节点类型定义：
- tool: 执行具体操作（调用API、处理数据、存储文件等）
- thought: 进行思考分析（分析、判断、推理、总结等）
- control: 控制流程（开始、结束、条件分支、循环等）

边类型定义：
- sequential: 顺序执行
- conditional: 条件执行
- parallel: 并行执行

请以JSON格式输出：
{{
    "nodes": [
        {{
            "name": "节点名称（简洁的动作描述）",
            "type": "tool|thought|control",
            "description": "节点功能描述",
            "inputs": ["输入参数列表"],
            "outputs": ["输出参数列表"]
        }}
    ],
    "edges": [
        {{
            "source": "源节点名称",
            "target": "目标节点名称",
            "type": "sequential|conditional|parallel",
            "condition": "条件表达式（条件边时填写）"
        }}
    ],
    "states": [
        {{
            "field_name": "字段名称（英文驼峰）",
            "type": "string|integer|boolean|array|object",
            "default_value": null,
            "description": "字段描述",
            "required": true或false
        }}
    ],
    "missing_info": ["缺失或不确定的信息"]
}}"""

CONFIG_PROMPT = """将以下结构化数据转为完整的LangGraph工作流配置。

工作流名称: {workflow_name}
工作流描述: {workflow_description}

节点列表：
{nodes}

边列表：
{edges}

状态列表：
{states}

请优化并生成完整的配置。确保：
1. 所有节点定义完整（输入、输出、配置参数）
2. 边连接正确且逻辑通顺
3. 状态定义覆盖所有需要的数据
4. 补充遗漏的控制节点（如需要）

以JSON格式输出完整配置：
{{
    "description": "工作流描述",
    "nodes": [
        {{
            "name": "节点名称",
            "type": "tool|thought|control",
            "description": "详细描述",
            "inputs": ["参数: 类型: 描述"],
            "outputs": ["输出: 类型: 描述"],
            "config": {{}}
        }}
    ],
    "edges": [
        {{
            "source": "源节点名称",
            "target": "目标节点名称",
            "type": "sequential|conditional|parallel",
            "condition": "条件（可选）"
        }}
    ],
    "states": [
        {{
            "field_name": "字段名",
            "type": "类型",
            "default_value": null,
            "description": "描述",
            "required": true或false
        }}
    ]
}}"""

CODE_PROMPT = """为以下LangGraph工作流生成完整的可执行Python代码。

工作流名称: {workflow_name}

节点列表：
{nodes}

边列表：
{edges}

状态定义：
{states}

要求：
1. 定义 WorkflowState TypedDict
2. 为每个节点生成处理函数
3. 构建 StateGraph 并添加节点和边
4. 包 compile() 调用
5. 处理异常情况
6. 代码要健壮，无硬编码"""

TEST_PROMPT = """为以下工作流生成验收标准和测试用例。

工作流描述: {workflow_description}

节点列表：
{nodes}

边列表：
{edges}

请生成：
1. 验收标准（功能、质量、性能、错误处理）
2. 测试用例（覆盖正常、边界、异常场景）

以JSON格式输出：
{{
    "criteria": [
        {{
            "id": "标准ID",
            "category": "functional|quality|performance|error_handling",
            "description": "标准描述",
            "priority": "high|medium|low"
        }}
    ],
    "test_cases": [
        {{
            "case_id": "用例ID",
            "name": "用例名称",
            "description": "详细描述",
            "category": "functional|edge_case|error|performance",
            "inputs": {{}},
            "expected_outputs": {{}},
            "tags": ["标签列表"]
        }}
    ]
}}"""

REPORT_PROMPT = """分析以下测试结果，生成评估报告。

工作流名称: {workflow_name}

测试用例及结果：
{test_results}

请深度分析：
1. 通过率和失败模式
2. 根因分析
3. 成功因素
4. 改进建议

以JSON格式输出：
{{
    "pass_rate": 0.0,
    "total_cases": 0,
    "passed": 0,
    "failed": 0,
    "issues": ["问题列表"],
    "success_factors": ["成功因素"],
    "suggestions": ["改进建议"],
    "root_cause_analysis": "根因分析"
}}"""

REVIEW_PROMPT = """对以下工作流进行PDCA复盘（GRBARP方法）。

工作流名称: {workflow_name}

原始目标：
{goals}

评估报告：
{evaluation_report}

请按以下结构进行复盘：
1. 目标回顾（Goal Review）: 哪些目标达成了？哪些没达成？
2. 结果分析（Result Analysis）: 成功因素和失败因素
3. 行动规划（Action Planning）: 具体的优化方案
4. 验证规划（Validation Planning）: 如何验证优化效果

同时给出优化建议列表。

以JSON格式输出：
{{
    "goal_review": {{
        "achieved_goals": ["达成的目标"],
        "missed_goals": ["未达成的目标"],
        "overall_assessment": "总体评价"
    }},
    "result_analysis": {{
        "success_factors": ["成功因素"],
        "failure_factors": ["失败因素"],
        "key_insights": ["关键洞察"]
    }},
    "action_planning": {{
        "immediate_actions": ["立即行动"],
        "long_term_actions": ["长期行动"]
    }},
    "validation_planning": {{
        "metrics": ["验证指标"],
        "methods": ["验证方法"]
    }},
    "optimizations": [
        {{
            "title": "优化方案标题",
            "description": "详细描述",
            "priority": "high|medium|low",
            "impact": "预期影响",
            "steps": ["实施步骤"]
        }}
    ]
}}"""

MEMORY_CONTEXT_TEMPLATE = """

## 历史经验参考
（以下经验来自 PDCA 记忆系统，请参考）

### 成功模式
{success_patterns}

### 失败教训（避免重蹈覆辙）
{failure_warnings}

### 可复用经验
{reusable_experiences}

### 优化方案参考
{verified_optimizations}
"""

COMPONENT_DISCOVERY_PROMPT = """分析以下工作流配置和复盘结果，识别可复用的组件模式。

工作流名称: {workflow_name}

节点列表：
{nodes}

成功因素：
{success_factors}

失败教训：
{failure_factors}

请识别以下可复用模式：
1. 通用节点模式（可在多个工作流中复用的节点）
2. 常见状态定义（多工作流共享的状态字段）
3. 最佳实践提示模式

以JSON格式输出：
{{
    "reusable_nodes": [
        {{
            "name": "节点模式名称",
            "type": "tool|thought|control",
            "description": "通用描述",
            "inputs": ["输入列表"],
            "outputs": ["输出列表"],
            "reason": "为什么可复用"
        }}
    ],
    "reusable_states": [
        {{
            "field_name": "字段名",
            "type": "类型",
            "description": "描述",
            "reason": "为什么可复用"
        }}
    ],
    "reusable_prompts": [
        {{
            "task_type": "extract|config|code",
            "name": "提示名称",
            "content": "提示内容",
            "reason": "为什么可复用"
        }}
    ]
}}"""

COMPONENT_LLM_MATCH_PROMPT = """我需要从组件库中查找与以下需求匹配的{category}组件。

需求描述: {query}

可用组件列表:
{candidates}

请分析语义相似度，选择最匹配的组件。

以JSON格式输出:
{{
    "match_id": "最匹配组件的ID，无匹配则为null",
    "confidence": 0.0到1.0之间的置信度,
    "reason": "选择理由（简短说明）"
}}

如果没有语义上足够接近的匹配，请将match_id设为null。"""
