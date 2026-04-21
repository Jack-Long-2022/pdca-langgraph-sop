# PDCA-LangGraph-SOP - 项目架构指南

> "Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution"

## 项目概述

PDCA-LangGraph-SOP 是一个基于 PDCA 循环的 LangGraph 工作流自动化生成系统。核心功能是将业务描述文本转换为可执行的 LangGraph 工作流代码，并通过持续改进闭环实现质量提升。

**核心价值**: 语音输入 → AI 理解 → 自动生成 → 持续优化

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────────────────┐
│                    用户输入层                          │
│              业务描述文本 / 语音输入                   │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│                  Plan 阶段层                          │
│  StructuredExtractor → ConfigGenerator              │
│  (结构化抽取)          (配置生成)                      │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│                   Do 阶段层                           │
│           CodeGenerator → 项目生成                     │
│           (代码生成)                                   │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│                 Check 阶段层                          │
│  TestCaseGenerator → TestExecutor → 评估报告          │
│  (测试用例生成)       (测试执行)                       │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│                  Act 阶段层                           │
│  GRRAVPReviewer → OptimizationGenerator             │
│  (复盘分析)        (优化方案生成)                      │
│           LoopController (循环控制)                   │
└─────────────────────────────────────────────────────┘
```

### 目录结构

```
pdca/
├── core/                 # 核心基础设施
│   ├── config.py         # 配置管理 (Pydantic模型)
│   ├── llm.py            # LLM封装 (OpenAI, 重试装饰器)
│   └── logger.py         # 结构化日志 (structlog)
│
├── plan/                 # Plan阶段
│   ├── extractor.py      # 结构化抽取 (节点/边/状态)
│   └── config_generator.py  # 配置生成
│
├── do_/                  # Do阶段
│   └── code_generator.py # 代码生成器
│
├── check/                # Check阶段
│   └── evaluator.py      # 测试执行器
│
└── act/                  # Act阶段
    ├── loop_controller.py  # 循环控制
    └── reviewer.py       # GR/RAVP复盘
```

## 核心设计模式

### 1. Pydantic 模型驱动

所有数据结构使用 Pydantic BaseModel 定义，确保类型安全和数据验证：

```python
# pdca/core/config.py
class WorkflowConfig(BaseModel):
    meta: WorkflowMeta
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]
    state: list[StateDefinition]
```

**规则**: 新增数据模型必须使用 Pydantic，提供完整的类型注解和字段描述。

### 2. 单例模式 - LLM管理器

```python
# pdca/core/llm.py
class LLMManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

### 3. 模板方法模式 - 代码生成

```python
# pdca/do_/code_generator.py
class CodeGenerator:
    def generate_project(self, config: WorkflowConfig, output_dir: Path):
        # 1. 创建目录结构
        # 2. 生成主程序
        # 3. 生成节点代码
        # 4. 生成配置
        # 5. 生成测试
```

### 4. 策略模式 - 节点类型识别

```python
# pdca/plan/extractor.py
class NodeExtractor:
    TOOL_KEYWORDS = ['调用', '执行', '运行', ...]
    THOUGHT_KEYWORDS = ['分析', '思考', '判断', ...]
    CONTROL_KEYWORDS = ['开始', '结束', '分支', ...]
    
    def _identify_node_type(self, verb_phrase: str) -> str:
        # 根据关键词识别节点类型
```

## 编码规范

### 命名约定

- **类名**: PascalCase (如 `WorkflowConfig`, `NodeExtractor`)
- **函数名**: snake_case (如 `extract_structure`, `generate_config`)
- **常量**: UPPER_SNAKE_CASE (如 `TOOL_KEYWORDS`, `MAX_RETRIES`)
- **私有方法**: `_前缀` (如 `_extract_verb_phrases`, `_validate_result`)

### 类型注解

**强制**: 所有函数必须提供类型注解

```python
def extract(self, text: str) -> StructuredDocument:
    """从文本中抽取结构化信息"""
    pass
```

### 错误处理

```python
# 使用自定义异常
class LLMError(Exception):
    """LLM调用异常"""
    pass

class RateLimitError(LLMError):
    """限流异常"""
    pass
```

### 日志规范

```python
from pdca.core.logger import get_logger

logger = get_logger(__name__)

# 使用结构化日志
logger.info("config_generation_start", 
           node_count=len(nodes),
           edge_count=len(edges))

logger.error("test_case_error",
            case_id=case_id,
            error=str(e))
```

## 开发工作流

### 1. 代码格式化

```bash
# 格式化代码
black pdca/

# 检查代码
ruff check pdca/
```

### 2. 测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_extractor.py

# 带覆盖率报告
pytest --cov=pdca --cov-report=term-missing
```

### 3. 添加新功能

1. **Plan**: 在对应 PDCA 阶段模块中创建新类/函数
2. **Type**: 使用 Pydantic 定义数据模型
3. **Test**: 在 `tests/` 中创建对应测试文件
4. **Log**: 使用结构化日志记录关键操作

## 核心组件说明

### Plan 阶段 - 结构化抽取

**输入**: 用户描述文本
**输出**: StructuredDocument (nodes, edges, states)

```python
from pdca.plan.extractor import StructuredExtractor

extractor = StructuredExtractor()
document = extractor.extract("首先调用API获取数据，然后分析结果...")
```

**关键类**:
- `NodeExtractor`: 从文本识别节点
- `EdgeExtractor`: 识别节点间关系
- `StateExtractor`: 识别状态字段
- `StructuredExtractor`: 总控协调器

### Do 阶段 - 代码生成

**输入**: WorkflowConfig
**输出**: Python 项目文件

```python
from pdca.do_.code_generator import CodeGenerator

generator = CodeGenerator()
files = generator.generate_project(config, output_dir)
```

**生成结构**:
```
output/
├── main.py              # 主程序入口
├── nodes/               # 节点处理模块
├── config/              # 配置文件
├── tests/               # 测试文件
└── README.md            # 文档
```

### Check 阶段 - 测试评估

```python
from pdca.check.evaluator import run_evaluation

report = run_evaluation(
    workflow_name="测试工作流",
    workflow_description="...",
    node_count=3,
    workflow_runner=runner
)
```

**评估指标**:
- pass_rate: 通过率
- execution_time: 执行时间
- issues: 问题列表
- suggestions: 改进建议

### Act 阶段 - 复盘优化

```python
from pdca.act.reviewer import GRRAVPReviewer
from pdca.act.loop_controller import LoopController

reviewer = GRRAVPReviewer()
result = reviewer.review(workflow_name, goals, report)

controller = LoopController(max_iterations=2)
controller.start(workflow_name)
```

**GR/RAVP 复盘流程**:
- Goal Review: 目标回顾
- Result Analysis: 结果分析
- Action Planning: 行动规划
- Validation Planning: 验证规划

## 依赖管理

### 核心依赖
- `langgraph>=0.0.20`: 工作流编排
- `langchain>=0.1.0`: LLM集成
- `langchain-openai>=0.0.5`: OpenAI集成
- `pydantic>=2.0`: 数据验证
- `structlog>=24.0.0`: 结构化日志

### 开发依赖
- `pytest>=8.0`: 测试框架
- `black>=24.0`: 代码格式化
- `ruff>=0.1.0`: 代码检查

## 配置管理

### 环境变量
```bash
export OPENAI_API_KEY="sk-..."
export LOG_LEVEL="INFO"
```

### 配置文件
```yaml
# config/workflow.yaml
workflow:
  max_iterations: 2
  quality_threshold: 90.0
  timeout: 60
```

## 注意事项

### 1. 不可变数据优先

```python
from dataclasses import dataclass

@dataclass(frozen=True)  # 不可变
class NodeDefinition:
    node_id: str
    name: str
    type: str
```

### 2. 文件路径处理

```python
from pathlib import Path

# 正确
config_dir = Path(__file__).parent / "config"

# 错误
config_dir = "./config"
```

### 3. LLM调用重试

```python
from pdca.core.llm import retry_on_error

@retry_on_error(max_retries=3, delay=1.0)
def generate(self, prompt: str) -> str:
    # 自动重试的LLM调用
    pass
```

## 常见任务

### 添加新的节点类型

1. 在 `pdca/core/config.py` 中扩展 `NodeDefinition` 验证器
2. 在 `pdca/plan/extractor.py` 中添加识别关键词
3. 在 `pdca/do_/code_generator.py` 中添加生成模板

### 扩展测试用例生成

1. 在 `pdca/check/evaluator.py` 中扩展 `TestCaseGenerator`
2. 添加新的 `generate_*_cases` 方法
3. 在测试文件中验证生成的用例

### 自定义LLM提供商

1. 在 `pdca/core/llm.py` 中继承 `BaseLLM`
2. 实现 `generate()` 和 `generate_messages()` 方法
3. 在 `setup_llm()` 中注册新提供商

## 版本历史

- v0.1.0: 初始版本，核心PDCA流程实现
