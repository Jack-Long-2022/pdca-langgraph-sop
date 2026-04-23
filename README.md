# PDCA-LangGraph-SOP

基于 PDCA 循环的 LangGraph 工作流自动化生成系统。

**核心价值**: 业务描述文本 → AI 理解 → 自动生成可执行工作流代码 → 持续优化

## 工作流程

```
方式 A：从文本描述生成（完整 PDCA）
──────────────────────────────────
用户输入（文本/语音）
        ↓
┌─── Plan ──────────────────────────┐
│  StructuredExtractor → ConfigGen  │ ← 组件库查找复用
└───────────────────────────────────┘
        ↓
┌─── Do ────────────────────────────┐
│  CodeGenerator → Python 项目文件   │
└───────────────────────────────────┘
        ↓
┌─── Check ─────────────────────────┐
│  TestCaseGenerator → 评估报告      │
└───────────────────────────────────┘
        ↓
┌─── Act ───────────────────────────┐
│  GRBARPReviewer → 优化方案         │ → 知识固化到组件库
│  LoopController → 循环控制         │ → 经验沉淀到记忆系统（可选）
└───────────────────────────────────┘

方式 B：从已有配置文件（跳过 Plan）
──────────────────────────────────
config/extractions/wf_xxx.json  ──→  Do → Check → Act
```

## 快速开始

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd pdca-langgraph-sop

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -e ".[dev]"
```

### 配置

```bash
cp .env.example .env

# 编辑 .env，填入 API Key
# ZHIPU_API_KEY=...          （智谱 - Planner 模型）
# MINIMAX_API_KEY=...         （MiniMax - Executor 模型）
```

### 运行

```bash
# 1. 从文本描述生成（完整 PDCA 循环）
python run.py --input examples/input.md --output output

# 2. 从已有配置文件（跳过 Plan，直接 Do/Check/Act）
python run.py --config config/extractions/wf_ecu_signal_test_gen.json --output output

# 3. 启用记忆系统（跨迭代经验积累）
python run.py --input examples/input.md --output output --memory

# 4. 从配置文件 + 记忆系统
python run.py --config config/extractions/wf_xxx.json --output output --memory
```

也可以使用 Claude Code 技能生成配置：

```
/prompt-to-langgraph 把提示词文件转成langgraph工作流
```

生成的 JSON 保存到 `config/extractions/`，然后用 `--config` 加载。

### 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--input` | `-i` | 输入 markdown 文件（与 `--config` 互斥） | — |
| `--config` | — | 工作流配置 JSON（与 `--input` 互斥） | — |
| `--output` | `-o` | 输出目录 | `generated_workflow` |
| `--workflow-name` | — | 工作流名称 | 从输入推断 |
| `--category` | `-c` | 工作流分类 (data/auto/qa/integration) | `general` |
| `--max-iterations` | — | 最大 PDCA 迭代次数 | 2 |
| `--quality-threshold` | — | 质量阈值（通过率%） | 80.0 |
| `--memory` | — | 启用记忆系统 | 关闭 |
| `--memory-dir` | — | 记忆系统存储目录 | `.pdca_memory` |
| `--component-library-dir` | — | 组件库目录 | `.pdca_components` |
| `--no-component-library` | — | 禁用组件库 | 关闭 |
| `--skip-do` | — | 跳过 Do 阶段 | 关闭 |
| `--skip-check` | — | 跳过 Check 阶段 | 关闭 |
| `--verbose` | `-v` | 详细输出 | 关闭 |

## 项目结构

```
pdca-langgraph-sop/
├── run.py                         # 统一入口（--input / --config / --memory）
├── main.py                        # 系统初始化
├── pdca/                          # 主包
│   ├── core/                      # 核心基础设施
│   │   ├── config.py              # Pydantic 配置模型 (WorkflowConfig)
│   │   ├── llm.py                 # LLM 封装（多提供商 / 双模型路由）
│   │   ├── logger.py              # 结构化日志 (structlog)
│   │   ├── memory.py              # PDCA 长期记忆系统
│   │   ├── prompts.py             # 集中提示词管理
│   │   ├── component_library.py   # 可复用组件库（YAML + 双层匹配）
│   │   └── utils.py               # 工具函数
│   ├── plan/                      # Plan 阶段
│   │   ├── extractor.py           # 结构化抽取（文本 → 节点/边/状态）
│   │   └── config_generator.py    # 配置生成（抽取结果 → WorkflowConfig）
│   ├── do_/                       # Do 阶段
│   │   ├── code_generator.py      # 代码生成（配置 → Python 项目）
│   │   └── workflow_runner.py     # 工作流运行器
│   ├── check/                     # Check 阶段
│   │   └── evaluator.py           # 测试生成与评估
│   └── act/                       # Act 阶段
│       ├── reviewer.py            # GRBARP 复盘 + 优化方案
│       └── loop_controller.py     # PDCA 循环控制
├── config/
│   └── extractions/               # 技能生成的工作流配置 JSON
├── tests/                         # 测试（100+ 测试用例）
├── examples/                      # 示例输入和演示脚本
└── doc/                           # 设计文档
```

### 运行时数据目录

```
.pdca_components/                  # 组件库（YAML per-type）
├── catalog.yaml                   # 轻量索引（name + summary + keywords）
├── nodes.yaml                     # 节点模板
├── edges.yaml                     # 边模板
├── states.yaml                    # 状态模板
└── prompts.yaml                   # 提示词模板

.pdca_memory/                      # 记忆系统（--memory 启用）
├── index.json                     # 记忆条目
├── workflows.json                 # 工作流元数据
└── experience_log.json            # 迭代日志
```

### 产出物目录

每次迭代在 `--output` 下生成语义化命名的子目录：

```
generated_workflow/
├── index.yaml                     # 产出物索引（自动维护）
├── 001_general_xxx_v1.0.0/       # 第 1 次迭代
│   ├── main.py                    # 主程序入口
│   ├── config/workflow_metadata.json
│   ├── nodes/                     # 节点实现
│   ├── evaluation_report.json     # Check 阶段报告
│   ├── review_result.json         # Act 阶段复盘
│   └── optimization_proposals.json
└── 002_general_xxx_v1.0.0/       # 第 2 次迭代（如需）
```

## 核心特性

### 1. 统一入口

`run.py` 通过参数组合覆盖所有使用场景：

| 模式 | 命令 | 说明 |
|------|------|------|
| 完整 PDCA | `--input xxx.md` | Plan → Do → Check → Act |
| 跳过 Plan | `--config xxx.json` | 直接 Do → Check → Act |
| 带记忆 | 加 `--memory` | 跨迭代经验积累与注入 |
| 快速验证 | `--skip-check` | 只生成代码不做测试 |

### 2. 可复用组件库

自动沉淀和管理工作流构建块，支持 YAML 格式方便人工维护：

- **节点模板**: Plan 阶段自动保存，新建工作流时优先复用
- **边/状态模板**: 连接模式和状态定义跨工作流共享
- **提示词管理**: LLM 提示词作为可复用资产统一管理
- **知识固化**: GRBARP 复盘自动识别成功模式并保存到组件库
- **双层匹配**: Tier 1 关键词（零 API 开销）→ Tier 2 LLM 语义（精准回退）

### 3. PDCA 记忆系统

`--memory` 启用后：

- 自动记录每次迭代的成功/失败经验
- 下次迭代自动注入历史上下文到 Prompt
- Act 阶段自动将复盘结果沉淀到记忆系统
- 支持跨工作流的模式识别

### 4. 双模型路由

根据任务复杂度智能路由 LLM：

- **Planner 任务**（抽取/配置/复盘）→ 使用强模型（如 GLM-4）
- **Executor 任务**（代码生成/测试）→ 使用轻量模型（如 MiniMax）

### 5. GRBARP 复盘

完整的 PDCA Act 阶段复盘流程：

1. **Goal Review** — 目标回顾（达成/未达成/部分达成）
2. **Result Analysis** — 结果分析（成功/失败因素）
3. **Action Planning** — 行动规划（优化方案）
4. **Validation Planning** — 验证规划（如何验证优化效果）

## 开发

```bash
# 运行测试
pytest

# 带覆盖率
pytest --cov=pdca --cov-report=term-missing

# 代码格式化
black pdca/
ruff check pdca/
```

## 依赖

**核心依赖**:
- `langgraph>=0.0.20` — 工作流编排
- `langchain>=0.1.0` — LLM 集成
- `langchain-openai>=0.0.5` — OpenAI 兼容 API
- `pydantic>=2.0` — 数据验证
- `pyyaml>=6.0` — YAML 存储
- `structlog>=24.0.0` — 结构化日志
- `python-dotenv` — 环境变量

**开发依赖**:
- `pytest>=8.0` / `black>=24.0` / `ruff>=0.1.0`

## 版本

- **v0.2.0** — 统一入口 run.py，合并 run_pdca.py 和 run_pdca_with_memory.py，支持 --config 跳过 Plan
- **v0.1.0** — 核心 PDCA 流程、组件库、记忆系统、双模型路由
