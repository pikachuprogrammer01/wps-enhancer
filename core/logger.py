import functools
import logging
import re
import time
import traceback
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Callable, Optional, Set, Tuple

from core.app_paths import get_logs_dir

_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# 敏感信息内容级脱敏：11 位手机号中间四位替换（138****5678）
_PHONE_RE = re.compile(r"(1[3-9]\d)\d{4}(\d{4})")
_SLOW_CALL_MS = 1000  # 超过该耗时的调用即使未开 DEBUG 也记 WARNING（排查性能）


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


def cleanup_logs(retain_days: int = 30) -> Tuple[int, int]:
    """删除 retain_days 天前的过期日志文件，返回 (删除数, 失败数)。

    按文件修改时间判断；正在写入的当天日志 mtime 新，天然保留。
    单个文件删除失败不中断（记录 warning），调用方按失败数提示。
    """
    cutoff = time.time() - retain_days * 86400
    deleted = 0
    failed = 0
    for f in get_logs_dir().glob("wps_enhancer_*.log"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        except OSError as e:
            get_logger("core.logger").warning(f"清理日志失败 {f}：{e}")
            failed += 1
    return deleted, failed


def _mask_sensitive(text: str) -> str:
    """内容级脱敏：11 位手机号中间四位替换为 ****（token 等由 mask_keys 覆盖）。"""
    return _PHONE_RE.sub(r"\1****\2", text)


def _summarize(value: Any, max_len: int) -> str:
    """将参数值转换为日志摘要字符串（防大对象刷屏 + 敏感内容脱敏）。"""
    if value is None:
        return "None"
    if isinstance(value, str):
        text = _mask_sensitive(value)
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
            elif (time.perf_counter() - start) * 1000 > _SLOW_CALL_MS:
                # 慢调用：未开 DEBUG 也记录 WARNING，便于排查性能问题
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.warning(f"{func_name}() 慢调用，耗时 {elapsed_ms:.1f}ms")
            return result

        return wrapper

    return decorator
