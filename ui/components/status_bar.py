from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

from ui.components.toast import show_toast


class StatusBar(QWidget):
    """状态栏组件：提示信息以轻提示（toast）形式弹出，3 秒自动消失。

    保留 show_*/clear 接口以兼容既有调用点；消息显示在顶层窗口上，
    不阻塞、不常驻。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = QLabel()
        self._label.setVisible(False)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self.setLayout(layout)

    def _toast(self, message: str, success: bool = True) -> None:
        """在顶层窗口弹出轻提示（无窗口时回退为直接显示文本）。"""
        top = self.window()
        if top is not None and top is not self:
            show_toast(top, message, success=success)
        else:
            self._label.setText(message)
            self._label.setVisible(True)

    def show_info(self, message: str) -> None:
        """轻提示：信息（灰色点）。"""
        self._toast(message, success=True)

    def show_success(self, message: str) -> None:
        """轻提示：成功（绿色点）。"""
        self._toast(message, success=True)

    def show_error(self, message: str) -> None:
        """轻提示：失败（橙色点）。"""
        self._toast(message, success=False)

    def show_warning(self, message: str) -> None:
        """轻提示：警告（橙色点）。"""
        self._toast(message, success=False)

    def clear(self) -> None:
        """兼容接口：toast 自动消失，无需手动清理。"""
        """隐藏状态栏文字。"""
        self._label.setText("")
        self._label.setVisible(False)
