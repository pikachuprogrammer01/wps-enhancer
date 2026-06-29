from pathlib import Path


def get_mac_logs_dir() -> Path:
    """返回 macOS 应用日志目录，遵循 Apple 文件系统规范（~/Library/Logs/）。"""
    return Path.home() / "Library" / "Logs" / "WPS Enhancer"
