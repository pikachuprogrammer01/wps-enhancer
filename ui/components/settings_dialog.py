"""兼容层：settings 对话框已拆分至 ui/components/settings/ 包。

保留此模块仅为不破坏历史导入路径（测试与外部引用）：
    from ui.components.settings_dialog import SettingsDialog
实际实现见 ui/components/settings/dialog.py。
"""

from ui.components.settings import SettingsDialog  # noqa: F401

__all__ = ["SettingsDialog"]
