"""PDCA-LangGraph-SOP 主入口"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

# Windows 控制台 UTF-8 编码支持
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

from pdca.core.config import get_config, Config
from pdca.core.logger import setup_logging, get_logger, LogConfig, set_log_config
from pdca.core.llm import setup_llm, get_llm_manager

# 加载环境变量
load_dotenv()


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="PDCA-LangGraph-SOP - 基于PDCA循环的LangGraph SOP交付流程系统"
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=None,
        help="配置文件目录"
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="日志目录"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别"
    )
    parser.add_argument(
        "--llm-provider",
        default=os.getenv("LLM_PROVIDER", "zhipu"),
        help="LLM提供商"
    )
    parser.add_argument(
        "--llm-model",
        default=os.getenv("ZHIPU_MODEL", "glm-4.7"),
        help="LLM模型"
    )
    parser.add_argument(
        "--llm-base-url",
        default=os.getenv("ZHIPU_BASE_URL"),
        help="LLM API基础URL"
    )
    parser.add_argument(
        "--llm-api-key",
        default=os.getenv("ZHIPU_API_KEY"),
        help="LLM API密钥"
    )
    parser.add_argument(
        "--init-only",
        action="store_true",
        help="仅初始化，不执行任何任务"
    )
    
    return parser.parse_args()


def initialize(
    config_dir: Optional[Path] = None,
    log_dir: Optional[Path] = None,
    log_level: str = "INFO",
    llm_provider: str = os.getenv("LLM_PROVIDER", "zhipu"),
    llm_model: str = os.getenv("ZHIPU_MODEL", "glm-4.7"),
    llm_base_url: Optional[str] = os.getenv("ZHIPU_BASE_URL"),
    llm_api_key: Optional[str] = os.getenv("ZHIPU_API_KEY")
):
    """初始化系统组件

    Args:
        config_dir: 配置文件目录
        log_dir: 日志目录
        log_level: 日志级别
        llm_provider: LLM提供商
        llm_model: LLM模型
        llm_base_url: LLM API基础URL
        llm_api_key: LLM API密钥
    """
    # 初始化日志
    log_config = LogConfig(
        log_dir=log_dir,
        log_level=log_level
    )
    set_log_config(log_config)
    logger = get_logger(__name__)
    
    # 初始化配置
    config = Config(config_dir=config_dir)
    
    # 初始化LLM
    setup_llm(
        name="default",
        provider=llm_provider,
        model=llm_model,
        api_key=llm_api_key,
        base_url=llm_base_url
    )
    
    logger.info(
        "system_initialized",
        config_dir=str(config.config_dir),
        log_dir=str(log_config.log_dir),
        log_level=log_level,
        llm_model=llm_model
    )
    
    return logger


def main():
    """主入口"""
    args = parse_args()
    
    logger = initialize(
        config_dir=args.config_dir,
        log_dir=args.log_dir,
        log_level=args.log_level,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        llm_base_url=args.llm_base_url,
        llm_api_key=args.llm_api_key
    )
    
    if args.init_only:
        logger.info("init_only_mode")
        print("系统初始化完成")
        return
    
    logger.info("system_starting")
    print("PDCA-LangGraph-SOP 系统已启动")
    print(f"配置文件目录: {args.config_dir or '默认'}")
    print(f"日志目录: {args.log_dir or '默认'}")


if __name__ == "__main__":
    main()
