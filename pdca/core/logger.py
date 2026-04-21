"""日志系统模块

提供结构化日志、日志分级和日志轮转功能
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
import structlog
from datetime import datetime


class LogConfig:
    """日志配置"""
    
    def __init__(
        self,
        log_dir: Optional[Path] = None,
        log_level: str = "INFO",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        enable_json: bool = True
    ):
        self.log_dir = log_dir or Path(__file__).parent.parent.parent / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_level = log_level.upper()
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.enable_json = enable_json


def setup_logging(config: Optional[LogConfig] = None) -> None:
    """配置日志系统
    
    Args:
        config: 日志配置，如果为None则使用默认配置
    """
    if config is None:
        config = LogConfig()
    
    # 设置根日志级别
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level))
    
    # 清除现有handlers
    root_logger.handlers.clear()
    
    # 创建格式化器
    if config.enable_json:
        # JSON格式输出到文件
        file_formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            rename_fields={'levelname': 'level', 'asctime': 'timestamp'}
        )
        # 控制台使用彩色输出
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(),
        )
    else:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = file_formatter
    
    # 文件Handler - 带轮转
    log_file = config.log_dir / f"pdca-langgraph-{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # 控制台Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 配置structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取结构化日志记录器
    
    Args:
        name: 日志记录器名称，通常使用 __name__
    
    Returns:
        结构化日志记录器
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """日志混入类，为类提供日志功能"""
    
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """获取当前类的日志记录器"""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__module__ + '.' + self.__class__.__name__)
        return self._logger


# 全局日志配置
_log_config: Optional[LogConfig] = None

def get_log_config() -> LogConfig:
    """获取全局日志配置"""
    global _log_config
    if _log_config is None:
        _log_config = LogConfig()
    return _log_config

def set_log_config(config: LogConfig) -> None:
    """设置全局日志配置"""
    global _log_config
    _log_config = config
    setup_logging(config)
