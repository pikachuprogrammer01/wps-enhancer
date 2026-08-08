import functools
import logging
import time
import traceback
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Callable, Optional, Set

from core.app_paths import get_logs_dir

_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def get_logger(module_name: str) -> logging.Logger:
    """返回统一配置的 logger，同一 module_name 返回同一实例。"""
    logger = logging.getLogger(module_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    log_dir = get_logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"wps_enhancer_{datetime.now().strftime('%Y%m%d')}.log"

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


def is_debug_log_enabled() -> bool:
    """读取详细日志开关（内存缓存，设置保存后即时生效）。"""
    try:
        from core.settings import get_app_settings
        return get_app_settings().log_debug
    except Exception:
        return False


def _summarize(value: Any, max_len: int) -> str:
    """将参数值转换为日志摘要字符串（防大对象刷屏）。"""
    if value is None:
        return "None"
    if isinstance(value, str):
        text = value
    elif isinstance(value, (list, tuple, set)):
        text = f"({len(value)} 项)"
    elif isinstance(value, dict):
        text = f"({len(value)} 键)"
    else:
        type_name = type(value).__name__
        if type_name == "SheetData":
            text = f"({len(value.rows)} 行)"
        elif type_name == "Template":
            text = f"({value.name})"
        elif type_name == "AppSettings":
            text = "(设置)"
        else:
            text = f"({type_name})"
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


def _format_args(
    args: tuple, kwargs: dict, mask_keys: Optional[Set[str]], max_arg_len: int,
) -> str:
    """将函数调用参数格式化为摘要字符串，mask_keys 命中的值脱敏。"""
    parts = [_summarize(arg, max_arg_len) for arg in args]
    for key, value in kwargs.items():
        if mask_keys and key in mask_keys:
            parts.append(f"{key}=***")
        else:
            parts.append(f"{key}={_summarize(value, max_arg_len)}")
    return ", ".join(parts) if parts else "无"


def log_call(
    module: str,
    *,
    level: int = logging.DEBUG,
    log_args: bool = True,
    log_result: bool = False,
    mask_keys: Optional[Set[str]] = None,
    max_arg_len: int = 200,
) -> Callable:
    """AOP 装饰器：自动记录函数进入、退出、耗时与异常。"""
    def decorator(func: Callable) -> Callable:
        logger = get_logger(module)
        func_name = func.__qualname__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            enabled = is_debug_log_enabled()
            if enabled and log_args:
                logger.log(
                    level,
                    f"{func_name}() 开始，参数: {_format_args(args, kwargs, mask_keys, max_arg_len)}",
                )
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                # 异常日志不受 log_debug 开关影响，始终记录
                logger.error(f"{func_name}() 抛出异常: {type(e).__name__}: {e}")
                logger.error(traceback.format_exc())
                raise
            if enabled:
                elapsed_ms = (time.perf_counter() - start) * 1000
                msg = f"{func_name}() 完成，耗时 {elapsed_ms:.1f}ms"
                if log_result:
                    msg += f"，结果: {_summarize(result, max_arg_len)}"
                logger.log(level, msg)
            return result

        return wrapper

    return decorator
