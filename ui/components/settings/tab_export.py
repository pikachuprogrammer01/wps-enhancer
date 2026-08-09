"""导出格式 tab（csv/txt 编码分隔符 + vcf 字段与姓名前后缀/时间戳）。"""

from typing import List

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QVBoxLayout, QWidget,
)

from core.settings import ENCODING_CHOICES, SEPARATOR_CHOICES
from ui.components.settings.constants import (
    _ENCODING_LABELS, _SEPARATOR_LABELS, _VCF_KEYS, _VCF_LABELS,
)


class ExportTabMixin:
    """导出格式设置分组（mixin：依赖宿主 SettingsDialog）。"""

    def _build_export_tab(self) -> QWidget:
        """导出格式：csv/txt 编码分隔符 + vcf 字段与姓名前后缀。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_export_group())
        layout.addStretch()
        return page

    def _build_export_group(self) -> QGroupBox:
        """导出格式分组（csv 编码 / txt 分隔符与编码 / vcf 字段与前后缀）。"""
        group = QGroupBox("导出格式")
        layout = QVBoxLayout(group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("csv 编码"))
        self._encoding_combo = QComboBox()
        for choice in ENCODING_CHOICES:
            self._encoding_combo.addItem(_ENCODING_LABELS.get(choice, choice), choice)
        self._encoding_combo.setCurrentIndex(
            max(0, ENCODING_CHOICES.index(self._settings.csv_encoding))
            if self._settings.csv_encoding in ENCODING_CHOICES else 0,
        )
        row1.addWidget(self._encoding_combo)
        row1.addStretch()
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("txt 分隔符"))
        self._separator_combo = QComboBox()
        self._separator_custom_index = len(SEPARATOR_CHOICES)
        for sep in SEPARATOR_CHOICES:
            self._separator_combo.addItem(_SEPARATOR_LABELS.get(sep, sep), sep)
        self._separator_combo.addItem("自定义", "__custom__")
        if self._settings.txt_separator in SEPARATOR_CHOICES:
            self._separator_combo.setCurrentIndex(SEPARATOR_CHOICES.index(self._settings.txt_separator))
        else:
            self._separator_combo.setCurrentIndex(self._separator_custom_index)
        self._separator_edit = QLineEdit(self._settings.txt_separator)
        self._separator_edit.setEnabled(
            self._separator_combo.currentIndex() == self._separator_custom_index,
        )
        self._separator_combo.currentIndexChanged.connect(self._on_separator_changed)
        row2.addWidget(self._separator_combo)
        row2.addWidget(self._separator_edit)
        row2.addStretch()
        layout.addLayout(row2)

        row2b = QHBoxLayout()
        row2b.addWidget(QLabel("txt 编码"))
        self._txt_encoding_combo = QComboBox()
        for choice in ENCODING_CHOICES:
            self._txt_encoding_combo.addItem(_ENCODING_LABELS.get(choice, choice), choice)
        self._txt_encoding_combo.setCurrentIndex(
            max(0, ENCODING_CHOICES.index(self._settings.txt_encoding))
            if self._settings.txt_encoding in ENCODING_CHOICES else 0,
        )
        row2b.addWidget(self._txt_encoding_combo)
        row2b.addStretch()
        layout.addLayout(row2b)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("vcf 导出字段"))
        self._vcf_checks: List[QCheckBox] = []
        for key in _VCF_KEYS:
            check = QCheckBox(_VCF_LABELS.get(key, key))
            check.setChecked(key in self._settings.vcf_fields)
            self._vcf_checks.append(check)
            row3.addWidget(check)
        row3.addStretch()
        layout.addLayout(row3)

        row3b = QHBoxLayout()
        row3b.addWidget(QLabel("vcf 姓名前缀"))
        self._vcf_prefix_edit = QLineEdit(self._settings.vcf_name_prefix)
        self._vcf_prefix_edit.setPlaceholderText("如：vcf_ / 客户-")
        row3b.addWidget(self._vcf_prefix_edit, 1)
        row3b.addWidget(QLabel("后缀"))
        self._vcf_suffix_edit = QLineEdit(self._settings.vcf_name_suffix)
        row3b.addWidget(self._vcf_suffix_edit, 1)
        row3c = QHBoxLayout()
        self._vcf_ts_check = QCheckBox("使用时间戳（年月日）")
        self._vcf_ts_check.setChecked(self._settings.vcf_timestamp)
        row3c.addWidget(self._vcf_ts_check)
        row3c.addWidget(QLabel("时间戳位置"))
        self._vcf_ts_pos_combo = QComboBox()
        self._vcf_ts_pos_combo.addItems(["姓名前", "姓名后"])
        self._vcf_ts_pos_combo.setCurrentText(
            "姓名前" if self._settings.vcf_timestamp_position == "prefix" else "姓名后",
        )
        row3c.addWidget(self._vcf_ts_pos_combo)
        row3c.addStretch()
        layout.addLayout(row3b)
        layout.addLayout(row3c)
        return group

    def _on_separator_changed(self, index: int) -> None:
        """分隔符下拉切换时控制自定义输入框可用性。"""
        self._separator_edit.setEnabled(index == self._separator_custom_index)
