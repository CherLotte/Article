"""统一日志封装。"""
from __future__ import annotations

import logging
import sys

_LOGGER_NAME = "novel-pipeline"


def setup_logger(name: str = _LOGGER_NAME, level: str = "INFO") -> logging.Logger:
    """获取一个标准化的 logger,避免重复添加 handler。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger
