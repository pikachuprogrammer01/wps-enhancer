from pathlib import Path


def get_mac_logs_dir() -> Path:
    """返回 macOS 应用日志目录，遵循 Apple 文件系统规范（~/Library/Logs/）。"""
    return Path.home() / "Library" / "Logs" / "WPS Enhancer"


def get_mac_data_dir() -> Path:
    """返回 macOS 应用可写数据目录，遵循 Apple 文件系统规范（~/Library/Application Support/）。"""
    return Path.home() / "Library" / "Application Support" / "WPS Enhancer"
