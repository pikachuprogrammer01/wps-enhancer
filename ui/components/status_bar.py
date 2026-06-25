from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel


class StatusBar(QWidget):
    """状态栏组件：显示带颜色样式的提示信息。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = QLabel()
        self._label.setVisible(False)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self.setLayout(layout)

    def show_info(self, message: str) -> None:
        """显示深灰色信息提示。"""
        self._label.setText(message)
        self._label.setStyleSheet("color: #555555;")
        self._label.setVisible(True)

    def show_success(self, message: str) -> None:
        """显示深绿色成功提示。"""
        self._label.setText(message)
        self._label.setStyleSheet("color: #2e7d32;")
        self._label.setVisible(True)

    def show_error(self, message: str) -> None:
        """显示深红色错误提示。"""
        self._label.setText(message)
        self._label.setStyleSheet("color: #c62828;")
        self._label.setVisible(True)

    def show_warning(self, message: str) -> None:
        """显示深橙色警告提示。"""
        self._label.setText(message)
        self._label.setStyleSheet("color: #e65100;")
        self._label.setVisible(True)

    def clear(self) -> None:
        """隐藏状态栏文字。"""
        self._label.setText("")
        self._label.setVisible(False)
