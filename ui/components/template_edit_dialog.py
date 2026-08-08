from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QDialogButtonBox,
)
from PyQt6.QtCore import Qt

from core.template.config import BuiltinColumn, Template, TemplateColumn


class TemplateEditDialog(QDialog):
    """模板新建/编辑对话框：名称 + 内置列勾选 + 自定义列输入。"""

    def __init__(
        self,
        builtin_columns: List[BuiltinColumn],
        template: Optional[Template] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._builtin_columns = builtin_columns
        self.setWindowTitle("编辑模板" if template else "新建模板")
        self.setMinimumWidth(420)

        self._name_edit = QLineEdit(template.name if template else "")

        self._builtin_list = QListWidget()
        selected_keys = {c.key for c in template.columns} if template else set()
        for col in builtin_columns:
            item = QListWidgetItem(col.label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if col.key in selected_keys
                else Qt.CheckState.Unchecked,
            )
            item.setData(Qt.ItemDataRole.UserRole, col.key)
            self._builtin_list.addItem(item)

        custom_names = [
            c.name for c in template.columns
            if c.key.startswith("custom_")
        ] if template else []
        self._custom_edit = QLineEdit("，".join(custom_names))

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("模板名称"))
        layout.addWidget(self._name_edit)
        layout.addWidget(QLabel("内置列（勾选导出字段）"))
        layout.addWidget(self._builtin_list)
        layout.addWidget(QLabel("自定义列（逗号分隔）"))
        layout.addWidget(self._custom_edit)
        layout.addWidget(button_box)

    def _validate_and_accept(self) -> None:
        """校验模板名非空后接受。"""
        if not self._name_edit.text().strip():
            self._name_edit.setFocus()
            return
        self.accept()

    def get_template(self) -> Template:
        """返回对话框编辑结果（调用方在 accepted 后读取）。"""
        name = self._name_edit.text().strip()
        columns: List[TemplateColumn] = []
        for i in range(self._builtin_list.count()):
            item = self._builtin_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                key = item.data(Qt.ItemDataRole.UserRole)
                columns.append(TemplateColumn(key=key, name=item.text()))
        custom_index = 1
        for raw in self._custom_edit.text().split("，"):
            raw = raw.strip()
            if not raw:
                continue
            for part in raw.replace(",", "，").split("，"):
                part = part.strip()
                if not part:
                    continue
                while any(c.key == f"custom_{custom_index}" for c in columns):
                    custom_index += 1
                columns.append(TemplateColumn(
                    key=f"custom_{custom_index}", name=part,
                ))
                custom_index += 1
        return Template(name=name, columns=columns)
