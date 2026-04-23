# PDCA-LangGraph-SOP

基于PDCA循环的LangGraph工作流自动化生成系统。

**核心价值**: 业务描述文本 → AI理解 → 自动生成可执行工作流代码 → 持续优化

## 架构概览

```
用户输入（文本/语音）
        ↓
┌─── Plan ──────────────────────────┐
│  StructuredExtractor → ConfigGen  │ ← 组件库查找复用（双层匹配）
└───────────────────────────────────┘
        ↓
┌─── Do ────────────────────────────┐
│  CodeGenerator → Python项目文件    │
└───────────────────────────────────┘
        ↓
┌─── Check ─────────────────────────┐
│  TestCaseGenerator → 评估报告      │
└───────────────────────────────────┘
        ↓
┌─── Act ───────────────────────────┐
│  GRBARPReviewer → 优化方案         │ → 知识固化到组件库
│  LoopController → 循环控制         │ → 经验沉淀到记忆系统
└───────────────────────────────────┘
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
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入 API Key
# OPENAI_API_KEY=sk-...      （OpenAI）
# ZHIPU_API_KEY=...           （智谱）
# MINIMAX_API_KEY=...         （MiniMax）
```

### 运行

方式1：
/prompt-to-langgraph 把提示词文件 @examples\input.md 转成langgraph工作流

方式2：
```bash
# 稳定场景：快速生成 + 组件库复用
python run_pdca.py --input examples/input.md --output output -v

# 探索场景：迭代优化 + 记忆系统 + 组件库
python run_pdca_with_memory.py --input examples/input.md --output output

# 系统初始化（验证环境和LLM连接）
python main.py
```

### 命令行参数

两个入口共享的核心参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--input, -i` | 输入文件路径（必填） | - |
| `--output, -o` | 输出目录 | `generated_workflow` |
| `--workflow-name` | 工作流名称 | 从文件名推断 |
| `--max-iterations` | 最大PDCA迭代次数 | 2 |
| `--quality-threshold` | 质量阈值（通过率%） | 80.0 |
| `--skip-do` | 跳过代码生成阶段 | false |
| `--skip-check` | 跳过测试评估阶段 | false |
| `--no-component-library` | 禁用组件库 | false |

`run_pdca_with_memory.py` 额外参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--memory-dir` | 记忆系统存储目录 | `.pdca_memory` |
| `--no-memory` | 禁用记忆系统 | false |

## 项目结构

```
pdca-langgraph-sop/
├── pdca/                          # 主包
│   ├── core/                      # 核心基础设施
│   │   ├── config.py              # Pydantic配置模型
│   │   ├── llm.py                 # LLM封装（多提供商/双模型路由）
│   │   ├── logger.py              # 结构化日志（structlog）
│   │   ├── memory.py              # PDCA长期记忆系统
│   │   ├── prompts.py             # 集中提示词管理
│   │   ├── component_library.py   # 可复用组件库（YAML + 双层匹配）
│   │   └── utils.py               # 工具函数
│   ├── plan/                      # Plan阶段
│   │   ├── extractor.py           # 结构化抽取（文本→节点/边/状态）
│   │   └── config_generator.py    # 配置生成（抽取结果→WorkflowConfig）
│   ├── do_/                       # Do阶段
│   │   ├── code_generator.py      # 代码生成（配置→Python项目）
│   │   └── workflow_runner.py     # 工作流运行器
│   ├── check/                     # Check阶段
│   │   └── evaluator.py           # 测试生成与评估
│   └── act/                       # Act阶段
│       ├── reviewer.py            # GRBARP复盘 + 优化方案
│       └── loop_controller.py     # PDCA循环控制
├── tests/                         # 测试（100+ 测试用例）
├── examples/                      # 示例输入和演示脚本
├── doc/                           # 设计文档
├── run_pdca.py                    # 稳定场景入口
├── run_pdca_with_memory.py        # 探索/迭代场景入口
└── main.py                        # 系统初始化
```

### 运行时数据目录

```
.pdca_components/                  # 组件库（YAML per-type）
├── catalog.yaml                   # 轻量索引（name + summary + keywords）
├── nodes.yaml                     # 节点模板
├── edges.yaml                     # 边模板
├── states.yaml                    # 状态模板
└── prompts.yaml                   # 提示词模板

.pdca_memory/                      # 记忆系统
├── index.json                     # 记忆条目
├── workflows.json                 # 工作流元数据
└── experience_log.json            # 迭代日志
```

## 核心特性

### 1. 可复用组件库

自动沉淀和管理工作流构建块，支持 YAML 格式方便人工维护：

- **节点模板**: Plan 阶段自动保存，新建工作流时优先复用
- **边/状态模板**: 连接模式和状态定义跨工作流共享
- **提示词管理**: LLM 提示词作为可复用资产统一管理
- **知识固化**: GRRAVP 复盘自动识别成功模式并保存到组件库
- **渐进式加载**: catalog.yaml 轻量扫描，per-type 文件按需读取

```python
from pdca.core.component_library import ComponentLibrary

library = ComponentLibrary()
# 查找相似节点（Tier 1 关键词匹配）
match = library.lookup_node("获取API数据", "从外部API获取数据")
# 保存节点模板
library.save_node(node_definition, workflow_name="my_workflow")
```

### 2. 双层匹配

组件查找采用两级策略：

1. **Tier 1（快速）**: 关键词 Jaccard 匹配，零 API 开销
2. **Tier 2（精准）**: LLM 语义匹配回退，仅在 Tier 1 未命中且主动开启时触发

```python
# 默认仅关键词匹配
library = ComponentLibrary(library_dir=".pdca_components")

# 启用 LLM 语义回退
library = ComponentLibrary(
    library_dir=".pdca_components",
    llm=planner_llm,
    enable_llm_matching=True,
)
```

### 3. PDCA记忆系统

跨迭代经验积累，持续改进：

- 自动记录每次迭代的成功/失败经验
- 下次迭代自动注入历史上下文到 Prompt
- 支持关键词搜索和相关性排序

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

### 6. 两个入口场景

| 能力 | `run_pdca.py` | `run_pdca_with_memory.py` |
|------|:---:|:---:|
| PDCA 完整流程 | ✓ | ✓ |
| 双模型路由 | ✓ | ✓ |
| 组件库（节点/边/状态复用） | ✓ | ✓ |
| 跨迭代经验记忆 | ✗ | ✓ |
| Prompt 注入历史经验 | ✗ | ✓ |
| 复盘结果自动沉淀 | ✗ | ✓ |
| 适用场景 | 稳定场景，快速验证 | 探索阶段，迭代优化 |

## 开发

```bash
# 运行测试
pytest

# 运行组件库测试
pytest tests/test_component_library.py -v

# 代码格式化
black pdca/
ruff check pdca/

# 带覆盖率
pytest --cov=pdca --cov-report=term-missing
```

## 依赖

**核心依赖**:
- `langgraph>=0.0.20` — 工作流编排
- `langchain>=0.1.0` — LLM集成
- `langchain-openai>=0.0.5` — OpenAI兼容API
- `pydantic>=2.0` — 数据验证
- `pyyaml>=6.0` — YAML存储
- `structlog>=24.0.0` — 结构化日志
- `python-dotenv` — 环境变量
- `python-json-logger>=2.0.0` — JSON日志

**开发依赖**:
- `pytest>=8.0` / `black>=24.0` / `ruff>=0.1.0`

## 版本

- **v0.1.0** — 核心PDCA流程、组件库（YAML per-type + 双层匹配）、记忆系统、双模型路由、集中提示词管理
