import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime

_LOG_DIR = Path("logs")
_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def get_logger(module_name: str) -> logging.Logger:
    """返回统一配置的 logger，同一 module_name 返回同一实例。"""
    logger = logging.getLogger(module_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    _LOG_DIR.mkdir(exist_ok=True)
    log_file = _LOG_DIR / f"wps_enhancer_{datetime.now().strftime('%Y%m%d')}.log"

    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(fmt=_FMT, datefmt=_DATE_FMT)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
