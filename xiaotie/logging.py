"""
日志管理模块

统一的日志管理，支持文件和控制台输出
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional

from .config import Config


class LoggerManager:
    """日志管理器"""

    _instance: Optional["LoggerManager"] = None
    _initialized = False

    def __new__(cls) -> "LoggerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        try:
            self.config = Config.load()
        except Exception:
            # 如果无法加载配置，使用默认配置
            from .config import LLMConfig, LoggingConfig

            self.config = Config(llm=LLMConfig(api_key="dummy"), logging=LoggingConfig())

        self.logger = self._setup_logger()
        self._initialized = True

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger("xiaotie")
        logger.setLevel(getattr(logging, self.config.logging.level.upper()))

        # 清除现有的处理器
        logger.handlers.clear()

        # 创建格式器
        formatter = logging.Formatter(self.config.logging.format)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 文件处理器（如果指定了路径）
        if self.config.logging.file_path:
            log_file = Path(self.config.logging.file_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.config.logging.max_bytes,
                backupCount=self.config.logging.backup_count,
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def get_logger(self) -> logging.Logger:
        """获取日志记录器"""
        return self.logger


def get_logger() -> logging.Logger:
    """获取日志记录器实例"""
    manager = LoggerManager()
    return manager.get_logger()


# 便利函数
def debug(msg: str, *args, **kwargs):
    get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    get_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    get_logger().critical(msg, *args, **kwargs)
