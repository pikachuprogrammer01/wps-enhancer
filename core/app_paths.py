import os
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
    """返回日志目录路径：macOS 打包用 ~/Library/Logs/，Windows 打包用 %LOCALAPPDATA%/WPS Enhancer/Logs，其他情况用项目 logs/ 目录。"""
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        from core.mac_paths import get_mac_logs_dir
        return get_mac_logs_dir()
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return local / "WPS Enhancer" / "Logs"
    return get_app_root() / "logs"


def get_data_dir() -> Path:
    """返回应用可写数据目录（模板/设置存放），兼容源码运行和 PyInstaller 打包运行。

    macOS 打包用 ~/Library/Application Support/，Windows 打包用 %APPDATA%/WPS Enhancer。
    """
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        from core.mac_paths import get_mac_data_dir
        return get_mac_data_dir()
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", str(Path.home())))
        return appdata / "WPS Enhancer"
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return get_app_root()


def get_templates_dir() -> Path:
    """返回模板目录路径（<数据目录>/template/）。"""
    return get_data_dir() / "template"


def get_settings_path() -> Path:
    """返回全局设置文件路径（<数据目录>/settings.json）。"""
    return get_data_dir() / "settings.json"
