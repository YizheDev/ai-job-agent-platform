"""统一日志系统

支持文件日志 + 控制台日志，日志格式符合企业级标准。
- 应用日志: logs/app.log（全量，DEBUG级别）
- 错误日志: logs/error.log（仅ERROR以上）
- 控制台: INFO级别
- 日志轮转: 单文件10MB，保留5个备份
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.core.config import LOG_DIR

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 10 * 1024 * 1024  # 10MB
_BACKUP_COUNT = 5


def get_logger(name: str = "ai_job_agent") -> logging.Logger:
    """获取统一日志器（同名Logger仅初始化一次）"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 应用日志文件 Handler（全量 DEBUG）
    app_file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    app_file_handler.setLevel(logging.DEBUG)
    app_file_handler.setFormatter(formatter)
    logger.addHandler(app_file_handler)

    # 错误日志文件 Handler（仅 ERROR+）
    error_file_handler = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    logger.addHandler(error_file_handler)

    return logger
