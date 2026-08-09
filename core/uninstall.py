"""卸载功能：注册式清理项框架（UninstallItem）+ 逐项执行。

扩展方式（可维护性核心）：
- 新增清理项 = 在 uninstall_items() 列表加一条 UninstallItem
- 新增平台 = 给 resolve 加平台分支（路径解析已集中在 app_paths）
- 主流程（勾选 → 确认 → 执行 → 反馈）永不动
"""

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from core.logger import get_logger


@dataclass
class UninstallItem:
    """一个卸载清理项（注册式，路径解析平台自适应）。"""
    key: str                          # 稳定标识（app / data / logs / downloads）
    label: str                        # 勾选文案
    resolve: Callable[[], Optional[Path]]  # 路径解析（None/不存在=视为已清理）
    risky: bool = False               # True=默认不勾选 + 确认框标注 ⚠️（防误删）
    default_checked: bool = True      # 默认勾选状态


def _app_path() -> Optional[Path]:
    """应用程序本体路径（macOS /Applications；Windows 安装目录）。"""
    if sys.platform == "win32":
        import os
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return local / "WPSEnhancer"
    if sys.platform == "darwin":
        return Path("/Applications") / "WPS增强工具.app"
    return None


def _downloads_path() -> Path:
    """更新包下载目录（复用设置；异常回退系统下载目录）。"""
    try:
        from core.settings import get_app_settings
        raw = get_app_settings().download_dir
        if raw.strip():
            return Path(raw.strip()).expanduser()
    except Exception:
        pass
    return Path.home() / "Downloads"


def uninstall_items() -> List[UninstallItem]:
    """返回当前平台全部清理项（顺序固定，UI 与执行共用）。"""
    from core.app_paths import get_data_dir, get_logs_dir
    return [
        UninstallItem(
            key="app",
            label="删除应用程序本体",
            resolve=_app_path,
            risky=False,
        ),
        UninstallItem(
            key="data",
            label="删除本地数据（设置/模板）",
            resolve=get_data_dir,
            risky=True,
            default_checked=False,  # 用户数据默认不清理，防误删
        ),
        UninstallItem(
            key="logs",
            label="删除日志",
            resolve=get_logs_dir,
            risky=False,
        ),
        UninstallItem(
            key="downloads",
            label="删除已下载的更新包（WPS增强工具_*.zip）",
            resolve=_downloads_path,
            risky=False,
        ),
    ]


def remove_item(item: UninstallItem) -> Optional[str]:
    """删除单个清理项；返回 None=成功（或本就无残留），字符串=失败原因。"""
    target = item.resolve()
    if target is None or not target.exists():
        return None  # 无残留视为已清理
    try:
        if item.key == "downloads":
            # 只清本应用的更新包，不碰目录里的其他文件
            for p in target.glob("WPS增强工具_*.zip"):
                p.unlink(missing_ok=True)
            return None
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
        return None
    except OSError as e:
        get_logger("core.uninstall").warning(f"删除 {target} 失败：{e}")
        return f"{item.label} 删除失败：{e}"


def uninstall_app(keys: List[str]) -> List[Tuple[str, Optional[str]]]:
    """按 key 顺序逐项执行卸载；单项失败只记录，不中断后续项。

    返回 [(key, error_or_None)]，None=该项成功。
    """
    by_key = {item.key: item for item in uninstall_items()}
    results: List[Tuple[str, Optional[str]]] = []
    for key in keys:
        item = by_key.get(key)
        if item is None:
            results.append((key, f"未知清理项：{key}"))
            continue
        try:
            results.append((key, remove_item(item)))
        except Exception as e:  # 路径解析等任何异常都不中断后续项
            get_logger("core.uninstall").warning(f"清理项 {key} 执行异常：{e}")
            results.append((key, f"{item.label} 执行失败：{e}"))
    return results
