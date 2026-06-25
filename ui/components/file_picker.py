from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog
from PyQt6.QtCore import pyqtSignal
from typing import Optional


class FilePicker(QWidget):
    """文件选择组件：标签 + 只读路径框 + 浏览按钮。"""
    file_selected = pyqtSignal(str)

    def __init__(
        self,
        label: str,
        file_filter: str = "Excel 文件 (*.xls *.xlsx)",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._file_filter = file_filter
        self._label = QLabel(label)
        self._line_edit = QLineEdit()
        self._line_edit.setReadOnly(True)
        self._browse_btn = QPushButton("浏览...")
        self._browse_btn.clicked.connect(self._on_browse_clicked)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        layout.addWidget(self._line_edit)
        layout.addWidget(self._browse_btn)
        self.setLayout(layout)

    def _on_browse_clicked(self) -> None:
        """弹出文件对话框，选中后发出 file_selected 信号。"""
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", self._file_filter)
        if path:
            self._line_edit.setText(path)
            self.file_selected.emit(path)

    def get_file_path(self) -> str:
        """返回当前选择的文件路径。"""
        return self._line_edit.text()

    def clear(self) -> None:
        """清空文件路径。"""
        self._line_edit.clear()
