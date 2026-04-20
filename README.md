# PDCA-LangGraph-SOP

基于PDCA循环的LangGraph SOP交付流程系统

## 项目概述

本系统通过语音输入→AI理解→自动生成→持续优化的闭环机制，实现从业务描述到可执行LangGraph工作流的自动化转换，并建立基于PDCA循环的持续改进机制。

## 核心功能

- **Plan阶段**: 语音理解、结构化抽取、配置生成
- **Do阶段**: 代码生成、节点实现、工作流运行
- **Check阶段**: 验收规则生成、测试执行、评估报告
- **Act阶段**: 复盘分析、优化方案、循环控制

## 安装

```bash
pip install -e .
```

## 快速开始

```bash
# 初始化系统
python main.py --llm-model gpt-4

# 查看帮助
python main.py --help
```

## 项目结构

```
PDCA-LangGraph-SOP/
├── config/              # 配置文件
├── logs/                # 日志目录
├── pdca/                # 主包
│   ├── core/            # 核心模块
│   │   ├── config.py    # 配置管理
│   │   ├── logger.py    # 日志系统
│   │   └── llm.py       # LLM封装
│   ├── plan/            # Plan阶段
│   ├── do_/             # Do阶段
│   ├── check/           # Check阶段
│   └── act/             # Act阶段
├── tests/               # 测试目录
├── examples/            # 示例
└── main.py              # 入口
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
black pdca/
ruff check pdca/
```

## 文档

详细技术方案见: [PDCA_LangGraph_SOP技术方案.docx](./PDCA_LangGraph_SOP技术方案.docx)
