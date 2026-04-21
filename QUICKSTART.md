# PDCA-LangGraph-SOP 快速开始指南

## 项目使用流程

```
语音输入 → Plan(结构化抽取+配置生成) → Do(代码生成) → Check(测试评估) → Act(复盘优化)
```

## 快速开始 (3步)

### 1. 准备输入文件

创建一个 `.md` 文件，描述你的工作流程：

```markdown
# 我的工作流

首先从API获取数据，然后清洗数据，接着分析趋势，最后生成报告。
```

### 2. 运行 PDCA 循环

```bash
# 基本用法
python run_pdca.py --input examples/input.md --output examples/output

# 完整流程（包括测试和复盘）
python run_pdca.py --input examples/input.md --output examples/output --max-iterations 2

# 只生成代码（跳过测试）
python run_pdca.py --input examples/input.md --output examples/output --skip-check
```

### 3. 查看生成的项目

```bash
cd examples/output/iteration_1
cat README.md
python main.py --help
```

## 示例输出

运行后会生成一个完整的 Python 项目：

```
examples/output/iteration_1/
├── main.py                    # 主程序入口
├── README.md                  # 项目文档
├── requirements.txt           # 依赖
├── config/
│   └── workflow.json         # 工作流配置
├── nodes/                     # 节点实现
│   ├── node_*.py             # 各节点处理函数
│   └── ...
├── tests/                     # 测试文件
└── pdca/
    └── do_/
        └── workflow_runner.py # 工作流运行器
```

## PDCA 各阶段说明

### 📋 Plan 阶段
- **输入**: 你的业务描述文本
- **处理**: AI 分析文本，识别节点、边和状态
- **输出**: WorkflowConfig (JSON 格式的工作流配置)

### 🔨 Do 阶段
- **输入**: WorkflowConfig
- **处理**: 生成可运行的 Python 代码
- **输出**: 完整的项目代码和文档

### ✅ Check 阶段
- **输入**: 生成的工作流项目
- **处理**: 运行测试，收集结果
- **输出**: EvaluationReport (评估报告)

### 🔄 Act 阶段
- **输入**: EvaluationReport
- **处理**: 复盘分析，生成优化方案
- **输出**: 优化建议和改进计划

## 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| --input | -i | 输入文件路径 | 必需 |
| --output | -o | 输出目录 | generated_workflow |
| --workflow-name | - | 工作流名称 | 自动推断 |
| --max-iterations | - | 最大迭代次数 | 2 |
| --quality-threshold | - | 质量阈值(%) | 80.0 |
| --skip-do | - | 跳过Do阶段 | false |
| --skip-check | - | 跳过Check阶段 | false |
| --verbose | -v | 详细输出 | false |

## API 使用示例

```python
from pdca.plan.extractor import StructuredExtractor
from pdca.plan.config_generator import ConfigGenerator
from pdca.do_.code_generator import CodeGenerator

# Plan: 从文本生成配置
text = "首先获取数据，然后分析，最后输出报告"
extractor = StructuredExtractor()
document = extractor.extract(text)

generator = ConfigGenerator()
config = generator.generate(document, "我的工作流")

# Do: 生成代码
code_gen = CodeGenerator()
files = code_gen.generate_project(config, Path("./output"))
```

## 环境变量配置

在项目根目录的 `.env` 文件中配置：

```bash
# 智谱AI配置
ZHIPU_API_KEY=你的API密钥
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4
ZHIPU_MODEL=glm-4.7

# 日志配置
LOG_LEVEL=INFO
```

## 常见问题

**Q: 支持哪些节点类型？**
A: 支持 tool（工具）、thought（思维）、control（控制）三种类型。

**Q: 如何自定义节点实现？**
A: 在生成的 `nodes/*.py` 文件中编辑 TODO 部分，实现具体业务逻辑。

**Q: 可以迭代优化吗？**
A: 可以，系统会根据测试结果自动进行最多 N 次迭代（默认2次），直到达到质量阈值。

## 完整示例

查看 `examples/` 目录获取更多示例：

- `input.md` - 基本的销售数据分析工作流
- `README.md` - 详细的文档和使用说明

## 技术支持

- 查看详细文档: `examples/README.md`
- 查看代码结构: `CLAUDE.md`
- 提交问题: GitHub Issues
