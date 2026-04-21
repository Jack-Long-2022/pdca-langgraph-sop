# PDCA-LangGraph-SOP 使用指南

## 项目概述

PDCA-LangGraph-SOP 是一个基于 PDCA 循环的 LangGraph 工作流自动化生成系统。通过语音/文字输入，自动将业务描述转换为可执行的 LangGraph 工作流代码，并通过持续改进闭环实现质量提升。

## 核心价值

**语音输入 → AI 理解 → 自动生成 → 持续优化**

## 快速开始

### 1. 环境配置

确保已安装 Python 3.11+ 和项目依赖：

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（编辑 .env 文件）
# ZHIPU_API_KEY=你的API密钥
# ZHIPU_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4
# ZHIPU_MODEL=glm-4.7
```

### 2. 准备输入文件

创建一个 markdown 文件，描述你想要的工作流程。参考 `examples/input.md`：

```markdown
# 我的工作流标题

我想创建一个自动化的数据分析工作流。首先从API获取销售数据，
然后对数据进行清洗，接着分析销售趋势，最后生成分析报告
并发送邮件通知。

具体步骤如下：
1. 首先调用销售数据API...
2. 然后对数据进行清洗...
3. 接着分析销售趋势...
4. 最后生成报告...
```

### 3. 运行 PDCA 循环

```bash
# 基本用法
python run_pdca.py --input examples/input.md --output examples/output

# 详细输出
python run_pdca.py --input examples/input.md --output examples/output --verbose

# 自定义工作流名称
python run_pdca.py --input examples/input.md --output examples/output --workflow-name "销售分析工作流"

# 只执行 Plan 和 Do 阶段
python run_pdca.py --input examples/input.md --output examples/output --skip-check
```

## PDCA 流程详解

### 📋 Plan 阶段：结构化抽取与配置生成

**输入**: 用户的业务描述文本（语音转文字后的内容）

**处理步骤**:
1. **StructuredExtractor** - 从文本中识别节点、边和状态
   - NodeExtractor: 识别动作节点（工具/思维/控制）
   - EdgeExtractor: 识别节点间的关系
   - StateExtractor: 识别数据对象和中间结果

2. **ConfigGenerator** - 生成 LangGraph 工作流配置
   - 转换为 WorkflowConfig 格式
   - 使用 LLM 细化节点描述
   - 生成完整的配置元数据

**输出**: WorkflowConfig (JSON 格式)

**示例输出**:
```json
{
  "meta": {
    "workflow_id": "wf_a1b2c3d4e5f6",
    "name": "销售数据分析工作流",
    "version": "0.1.0"
  },
  "nodes": [
    {
      "node_id": "node_12345678",
      "name": "调用销售数据API",
      "type": "tool",
      "description": "从销售系统API获取本月销售记录"
    }
  ],
  "edges": [...],
  "state": [...]
}
```

### 🔨 Do 阶段：代码生成

**输入**: WorkflowConfig

**处理步骤**:
1. **CodeGenerator** - 生成完整的 Python 项目
   - 生成主程序 (main.py)
   - 生成工作流运行器 (workflow_runner.py)
   - 生成节点处理模块 (nodes/*.py)
   - 生成测试文件 (tests/test_*.py)
   - 生成配置文件和文档

**输出**: 可运行的 Python 项目

**生成的项目结构**:
```
generated_workflow/
├── main.py              # 主程序入口
├── requirements.txt     # 项目依赖
├── README.md            # 项目文档
├── config/
│   └── workflow.json    # 工作流配置
├── nodes/               # 节点处理模块
│   ├── __init__.py
│   ├── node_*.py        # 各节点实现
│   └── ...
├── tests/               # 测试文件
│   ├── __init__.py
│   └── test_workflow.py
└── pdca/
    └── do_/
        └── workflow_runner.py  # 工作流运行器
```

### ✅ Check 阶段：测试与评估

**输入**: 生成的工作流项目

**处理步骤**:
1. **TestCaseGenerator** - 生成测试用例
   - 正常场景测试
   - 边界条件测试
   - 异常处理测试

2. **TestExecutor** - 执行测试
   - 运行所有测试用例
   - 收集测试结果
   - 记录执行时间

3. **EvaluationReportGenerator** - 生成评估报告
   - 计算通过率
   - 分析问题
   - 生成改进建议

**输出**: EvaluationReport

**示例输出**:
```
📊 评估结果:
   总用例数: 8
   通过: 6
   失败: 1
   错误: 1
   通过率: 75.0%
```

### 🔄 Act 阶段：复盘与优化

**输入**: EvaluationReport

**处理步骤**:
1. **GRRAVPReviewer** - 执行 GR/RAVP 复盘
   - Goal Review: 目标回顾
   - Result Analysis: 结果分析
   - Action Planning: 行动规划
   - Validation Planning: 验证规划

2. **OptimizationGenerator** - 生成优化方案
   - 基于未达成目标生成方案
   - 基于失败因素生成方案
   - 按优先级排序

**输出**: GRRAVPReviewResult + OptimizationProposals

**示例输出**:
```
📈 复盘结果:
   总体评分: 72.5/100

💡 优化方案:
   方案 1: 修复: 1个测试用例失败
     优先级: high
     预期收益: 提高通过率
```

## 完整示例

### 示例 1: 简单的顺序工作流

**输入** (`examples/simple_workflow.md`):
```markdown
# 文本处理工作流

首先读取用户输入的文本文件，然后对文本进行分词处理，
接着统计词频，最后输出词频统计结果到文件。
```

**运行**:
```bash
python run_pdca.py --input examples/simple_workflow.md --output examples/simple_output
```

### 示例 2: 带条件分支的工作流

**输入** (`examples/conditional_workflow.md`):
```markdown
# 数据审核工作流

首先获取待审核的数据，然后检查数据完整性。
如果数据完整，则执行数据分析并生成报告；
如果数据不完整，则记录错误并发送通知。
```

**运行**:
```bash
python run_pdca.py --input examples/conditional_workflow.md --output examples/conditional_output
```

### 示例 3: 复杂的多阶段工作流

**输入** (`examples/complex_workflow.md`):
```markdown
# ETL数据处理工作流

我需要创建一个ETL数据处理流程：

1. 首先从数据库抽取源数据
2. 然后对数据进行清洗和转换
3. 接着验证数据质量
4. 如果验证通过，加载到目标系统
5. 如果验证失败，记录错误并回滚
6. 最后生成处理报告并发送通知

需要支持重试机制和错误处理。
```

**运行**:
```bash
python run_pdca.py --input examples/complex_workflow.md --output examples/complex_output --max-iterations 3
```

## 高级用法

### 自定义 LLM 配置

```python
from pdca.core.llm import setup_llm

# 使用不同的模型
setup_llm(
    name="custom",
    provider="zhipu",
    model="glm-4-plus",  # 使用更强大的模型
    api_key="your-api-key",
    base_url="https://open.bigmodel.cn/api/coding/paas/v4"
)
```

### 直接使用 API

```python
from pdca.plan.extractor import StructuredExtractor
from pdca.plan.config_generator import ConfigGenerator
from pdca.do_.code_generator import CodeGenerator

# Plan 阶段
extractor = StructuredExtractor()
document = extractor.extract("你的工作流描述")

generator = ConfigGenerator()
config = generator.generate(document, workflow_name="我的工作流")

# Do 阶段
code_gen = CodeGenerator()
files = code_gen.generate_project(config, Path("./output"))
```

### 集成到 CI/CD

```yaml
# .github/workflows/pdca.yml
name: PDCA Workflow Generation

on:
  push:
    paths:
      - 'workflows/*.md'

jobs:
  pdca:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run PDCA
        env:
          ZHIPU_API_KEY: ${{ secrets.ZHIPU_API_KEY }}
        run: |
          for file in workflows/*.md; do
            python run_pdca.py --input "$file" --output "generated/$(basename $file .md)"
          done
```

## 输出文件说明

每次 PDCA 迭代会生成以下文件：

```
iteration_1/
├── main.py                      # 主程序
├── workflow_runner.py           # 工作流运行器
├── nodes/                       # 节点实现
│   ├── node_*.py
│   └── ...
├── config/
│   ├── workflow.json            # 工作流配置
│   └── workflow_metadata.json   # 元数据
├── tests/
│   └── test_workflow.py         # 测试文件
├── evaluation_report.json       # 评估报告
├── review_result.json           # 复盘结果
├── optimization_proposals.json  # 优化方案
└── README.md                    # 项目文档
```

## 质量标准

- **通过率**: 默认阈值 80%，可通过 `--quality-threshold` 调整
- **最大迭代**: 默认 2 次，可通过 `--max-iterations` 调整
- **测试覆盖**: 自动生成正常、边界、异常三类测试用例

## 常见问题

### Q: 如何查看生成的代码？

A: 生成后的代码在输出目录中，可以直接查看和编辑：

```bash
cd generated_workflow/iteration_1
cat main.py
cat nodes/node_*.py
```

### Q: 如何手动测试生成的工作流？

A: 进入生成的项目目录，运行主程序：

```bash
cd generated_workflow/iteration_1
python main.py --help
python main.py --input input.txt --output output.txt
```

### Q: 如何迭代优化工作流？

A: 系统会自动执行多次迭代，直到达到质量阈值或达到最大迭代次数。每次迭代会基于上一次的复盘结果进行优化。

### Q: 支持哪些类型的节点？

A: 支持三种节点类型：
- **tool**: 工具节点（调用API、执行操作）
- **thought**: 思维节点（分析、判断、推理）
- **control**: 控制节点（开始、结束、分支、循环）

### Q: 如何处理敏感的API密钥？

A: 使用 `.env` 文件存储敏感信息，并将其添加到 `.gitignore`：

```bash
# .env
ZHIPU_API_KEY=your-secret-key

# .gitignore
.env
.env.local
```

## 技术架构

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

## 版本历史

- **v0.1.0**: 初始版本，核心PDCA流程实现
  - Plan: 结构化抽取和配置生成
  - Do: 代码生成和项目构建
  - Check: 测试执行和评估报告
  - Act: GR/RAVP复盘和优化方案

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
