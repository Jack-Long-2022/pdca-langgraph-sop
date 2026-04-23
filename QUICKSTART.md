# PDCA-LangGraph-SOP 快速开始指南

## 项目使用流程

```
语音输入 → Plan(结构化抽取+配置生成) → Do(代码生成) → Check(测试评估) → Act(复盘优化)
```

## 快速开始 (3 步)

### 1. 准备输入文件

创建一个 `.md` 文件，描述你的工作流程：

```markdown
# 我的工作流

首先从API获取数据，然后清洗数据，接着分析趋势，最后生成报告。
```

或者使用 Claude Code 技能直接生成配置：

```
/prompt-to-langgraph 把提示词文件转成langgraph工作流
```

### 2. 运行 PDCA 循环

```bash
# 从文本描述生成（完整 PDCA）
python run.py --input examples/input.md --output output

# 从已有配置文件（跳过 Plan）
python run.py --config config/extractions/wf_ecu_signal_test_gen.json --output output

# 带记忆系统（跨迭代优化）
python run.py --input examples/input.md --output output --memory

# 只生成代码（跳过测试）
python run.py --input examples/input.md --output output --skip-check
```

### 3. 查看生成的项目

```bash
cd output/001_general_xxx_v1.0.0
cat README.md
python main.py --help
```

## 产出物结构

运行后生成：

```
output/
├── index.yaml                     # 产出物索引
├── 001_general_xxx_v1.0.0/
│   ├── main.py                    # 主程序入口
│   ├── README.md                  # 项目文档
│   ├── requirements.txt           # 依赖
│   ├── config/
│   │   └── workflow_metadata.json
│   ├── nodes/                     # 节点实现
│   ├── tests/                     # 测试文件
│   ├── evaluation_report.json     # 评估报告
│   ├── review_result.json         # 复盘结果
│   └── optimization_proposals.json
```

## PDCA 各阶段说明

### Plan 阶段
- **输入**: 你的业务描述文本（或 `--config` 跳过）
- **处理**: AI 分析文本，识别节点、边和状态
- **输出**: WorkflowConfig (JSON 格式的工作流配置)

### Do 阶段
- **输入**: WorkflowConfig
- **处理**: 生成可运行的 Python 代码
- **输出**: 完整的项目代码和文档

### Check 阶段
- **输入**: 生成的工作流项目
- **处理**: 运行测试，收集结果
- **输出**: EvaluationReport (评估报告)

### Act 阶段
- **输入**: EvaluationReport
- **处理**: 复盘分析，生成优化方案
- **输出**: 优化建议和改进计划

## 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--input` | `-i` | 输入 markdown 文件（与 `--config` 互斥） | 必填* |
| `--config` | — | 配置 JSON（与 `--input` 互斥） | 必填* |
| `--output` | `-o` | 输出目录 | `generated_workflow` |
| `--workflow-name` | — | 工作流名称 | 自动推断 |
| `--category` | `-c` | 工作流分类 | `general` |
| `--max-iterations` | — | 最大迭代次数 | 2 |
| `--quality-threshold` | — | 质量阈值(%) | 80.0 |
| `--memory` | — | 启用记忆系统 | 关闭 |
| `--skip-do` | — | 跳过 Do 阶段 | 关闭 |
| `--skip-check` | — | 跳过 Check 阶段 | 关闭 |
| `--verbose` | `-v` | 详细输出 | 关闭 |

*`--input` 和 `--config` 必须提供其中一个。

## API 使用示例

```python
from pathlib import Path
from pdca.core.config import WorkflowConfig
from pdca.plan.extractor import StructuredExtractor
from pdca.plan.config_generator import ConfigGenerator
from pdca.do_.code_generator import CodeGenerator

# 方式 1: 从文本生成
text = "首先获取数据，然后分析，最后输出报告"
extractor = StructuredExtractor()
document = extractor.extract(text)

generator = ConfigGenerator()
config = generator.generate(document, "我的工作流")

# 方式 2: 从 JSON 加载
import json
with open("config/extractions/wf_xxx.json") as f:
    data = json.load(f)
config = WorkflowConfig(**data["config"])  # 或直接 WorkflowConfig(**data)

# Do: 生成代码
code_gen = CodeGenerator()
files = code_gen.generate_project(config, Path("./output"))
```

## 环境变量配置

在项目根目录的 `.env` 文件中配置：

```bash
# 智谱 AI 配置（Planner 模型）
ZHIPU_API_KEY=你的API密钥
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4
ZHIPU_MODEL=glm-4.7

# MiniMax 配置（Executor 模型）
MINIMAX_API_KEY=你的API密钥
MINIMAX_MODEL=MiniMax-Text-01

# 日志配置
LOG_LEVEL=INFO
```

## 常见问题

**Q: `--input` 和 `--config` 有什么区别？**
A: `--input` 从文本描述走完整 PDCA（Plan→Do→Check→Act）；`--config` 从已有的 JSON 配置文件跳过 Plan，直接 Do→Check→Act。

**Q: 什么时候用 `--memory`？**
A: 当你进行多轮迭代优化时，记忆系统会自动积累每轮的经验教训并注入到下一轮。单次运行不需要。

**Q: 支持哪些节点类型？**
A: 支持 tool（工具）、thought（思维）、control（控制）三种类型。

**Q: 如何自定义节点实现？**
A: 在生成的 `nodes/*.py` 文件中编辑 TODO 部分，实现具体业务逻辑。

**Q: 可以迭代优化吗？**
A: 可以，系统会根据测试结果自动进行最多 N 次迭代（默认 2 次），直到达到质量阈值。
