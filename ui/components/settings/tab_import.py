"""导入处理 tab（手机号处理 + 文件声明检测）。"""

from PyQt6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QVBoxLayout, QWidget,
)

from ui.components.settings.constants import _PHONE_SEP_DISPLAY


class ImportTabMixin:
    """导入处理设置分组（mixin：依赖宿主 SettingsDialog）。"""

    def _build_import_tab(self) -> QWidget:
        """导入处理：手机号处理 + 文件处理（声明检测）。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_phone_group())
        layout.addWidget(self._build_file_group())
        layout.addStretch()
        return page

    def _build_phone_group(self) -> QGroupBox:
        """手机号处理分组。"""
        group = QGroupBox("手机号处理")
        layout = QVBoxLayout(group)
        self._validate_check = QCheckBox("校验手机号格式")
        self._validate_check.setChecked(self._settings.phone_validate)
        self._highlight_check = QCheckBox("非法手机号标红")
        self._highlight_check.setChecked(self._settings.phone_highlight)
        self._merge_check = QCheckBox("同一姓名多手机号合并姓名单元格（仅 xlsx/xls）")
        self._merge_check.setChecked(self._settings.phone_merge)
        layout.addWidget(self._validate_check)
        layout.addWidget(self._highlight_check)
        layout.addWidget(self._merge_check)
        merge_hint = QLabel(
            "未勾选合并时：每个手机号单独一行，相同内容不合并",
        )
        merge_hint.setStyleSheet("color: #888888;")
        layout.addWidget(merge_hint)
        row = QHBoxLayout()
        row.addWidget(QLabel("多手机号分隔符"))
        self._phone_separators_edit = QPlainTextEdit()
        self._phone_separators_edit.setPlaceholderText(
            "每行一个分隔符，如：逗号 / 分号 / 顿号 / [空格] / 竖线",
        )
        display_lines = [
            _PHONE_SEP_DISPLAY.get(sep, sep)
            for sep in self._settings.phone_separators
        ]
        self._phone_separators_edit.setPlainText("\n".join(display_lines))
        self._phone_separators_edit.setFixedHeight(80)
        row.addWidget(self._phone_separators_edit, 1)
        layout.addLayout(row)
        return group

    def _build_file_group(self) -> QGroupBox:
        """文件处理分组（声明行检测 + 关键词）。"""
        group = QGroupBox("文件处理（声明行检测）")
        layout = QVBoxLayout(group)
        self._declaration_check = QCheckBox(
            "声明行检测：自动跳过首行声明（如企查查/天眼查等导出）",
        )
        self._declaration_check.setChecked(self._settings.declaration_detect)
        layout.addWidget(self._declaration_check)
        row = QHBoxLayout()
        row.addWidget(QLabel("声明关键词（逗号分隔）"))
        self._keywords_edit = QLineEdit("，".join(self._settings.declaration_keywords))
        self._keywords_edit.setEnabled(self._declaration_check.isChecked())
        self._declaration_check.toggled.connect(self._keywords_edit.setEnabled)
        row.addWidget(self._keywords_edit, 1)
        layout.addLayout(row)
        return group
