import sys
from pathlib import Path


def get_app_root() -> Path:
    """返回应用根目录，兼容源码运行和 PyInstaller 打包运行。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_features_dir() -> Path:
    """返回 features 功能目录的绝对路径。"""
    return get_app_root() / "features"


def get_logs_dir() -> Path:
    """返回日志目录路径，macOS 打包时使用 ~/Library/Logs/，其他情况使用项目 logs/ 目录。"""
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        from core.mac_paths import get_mac_logs_dir
        return get_mac_logs_dir()
    return get_app_root() / "logs"
