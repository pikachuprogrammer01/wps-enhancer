from typing import List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox,
    QCheckBox, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QInputDialog, QPlainTextEdit, QTabWidget, QWidget,
)
from PyQt6.QtCore import Qt

from core.settings import (
    AppSettings, ENCODING_CHOICES, SEPARATOR_CHOICES, get_app_settings,
    save_app_settings,
)
from core.exceptions import WpsEnhancerError
from core.logger import get_logger
from core.template.config import BuiltinColumn

# vcf 可导出字段（v1 仅四个默认内置列）
_VCF_KEYS = ["name", "phone", "company", "website"]
_VCF_LABELS = {"name": "姓名", "phone": "手机", "company": "公司名", "website": "网址"}
_SEPARATOR_LABELS = {" ": "空格", "\t": "Tab", ",": "逗号", "、": "顿号", "|": "竖线"}
# 手机号分隔符编辑时的转义显示（空格/Tab 无法直接看清）
_PHONE_SEP_DISPLAY = {" ": "[空格]", "\t": "[Tab]"}
_PHONE_SEP_PARSE = {v: k for k, v in _PHONE_SEP_DISPLAY.items()}
_ENCODING_LABELS = {
    "utf-8-bom": "UTF-8 带 BOM",
    "utf-8": "UTF-8",
    "gbk": "GBK",
    "utf-16": "UTF-16",
    "unicode": "Unicode（UTF-16）",
}


class SettingsDialog(QDialog):
    """全局设置对话框（分页 Tab：导入处理 / 导出格式 / 内置列 / 日志）。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(640, 520)
        self._settings = get_app_settings()

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_import_tab(), "导入处理")
        tabs.addTab(self._build_export_tab(), "导出格式")
        tabs.addTab(self._build_builtin_tab(), "内置列")
        tabs.addTab(self._build_log_tab(), "日志")
        tabs.addTab(self._build_update_tab(), "更新")
        layout.addWidget(tabs)
        layout.addLayout(self._build_buttons())

    def _build_update_tab(self) -> QWidget:
        """更新：自动检查开关 + 手动检查按钮 + 版本信息。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_update_group())
        layout.addStretch()
        return page

    def _build_update_group(self) -> QGroupBox:
        """更新分组（GitHub Releases 自动更新）。"""
        from core.version import APP_VERSION
        group = QGroupBox("更新")
        layout = QVBoxLayout(group)
        self._auto_update_check = QCheckBox("自动检查更新（启动时检查 GitHub Releases）")
        self._auto_update_check.setChecked(self._settings.auto_update_enabled)
        layout.addWidget(self._auto_update_check)
        row = QHBoxLayout()
        row.addWidget(QLabel(f"当前版本：v{APP_VERSION}"))
        row.addStretch()
        self._check_update_btn = QPushButton("检查更新")
        self._check_update_btn.clicked.connect(self._on_check_update)
        row.addWidget(self._check_update_btn)
        layout.addLayout(row)
        self._update_status_label = QLabel("")
        self._update_status_label.setStyleSheet("color: #666666;")
        self._update_status_label.setWordWrap(True)
        layout.addWidget(self._update_status_label)
        return group

    def _on_check_update(self) -> None:
        """手动检查更新（后台检查，结果弹窗）。"""
        from ui.components.update_flow import check_update_now
        self._check_update_btn.setEnabled(False)
        self._update_status_label.setText("正在检查更新…")
        check_update_now(self, silent_on_failure=False)
        self._check_update_btn.setEnabled(True)

    def _build_import_tab(self) -> QWidget:
        """导入处理：手机号处理 + 文件处理（声明检测）。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_phone_group())
        layout.addWidget(self._build_file_group())
        layout.addStretch()
        return page

    def _build_export_tab(self) -> QWidget:
        """导出格式：csv/txt 编码分隔符 + vcf 字段与姓名前后缀。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_export_group())
        layout.addStretch()
        return page

    def _build_builtin_tab(self) -> QWidget:
        """内置列管理（增删改查）。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_builtin_group())
        layout.addStretch()
        return page

    def _build_log_tab(self) -> QWidget:
        """日志分组。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_log_group())
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

    def _build_log_group(self) -> QGroupBox:
        """日志分组。"""
        group = QGroupBox("日志")
        layout = QVBoxLayout(group)
        self._log_debug_check = QCheckBox("详细日志（DEBUG，排查问题时开启）")
        self._log_debug_check.setChecked(self._settings.log_debug)
        layout.addWidget(self._log_debug_check)
        return group

    def _build_builtin_group(self) -> QGroupBox:
        """内置列管理分组（增删改查）。"""
        group = QGroupBox("内置列（姓名/手机/公司名/网址）")
        layout = QVBoxLayout(group)
        self._builtin_table = QTableWidget(0, 3)
        self._builtin_table.setHorizontalHeaderLabels(["语义键", "显示名", "匹配别名（逗号分隔）"])
        for col in self._settings.builtin_columns:
            self._append_builtin_row(col)
        layout.addWidget(self._builtin_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加内置列")
        add_btn.clicked.connect(self._on_add_builtin)
        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self._on_delete_builtin)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return group

    def _append_builtin_row(self, col: BuiltinColumn) -> None:
        """向内置列表格追加一行。"""
        row = self._builtin_table.rowCount()
        self._builtin_table.insertRow(row)
        key_item = QTableWidgetItem(col.key)
        key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._builtin_table.setItem(row, 0, key_item)
        self._builtin_table.setItem(row, 1, QTableWidgetItem(col.label))
        self._builtin_table.setItem(row, 2, QTableWidgetItem("，".join(col.aliases)))

    def _on_add_builtin(self) -> None:
        """弹窗输入新内置列信息。"""
        key, ok1 = QInputDialog.getText(self, "添加内置列", "语义键（英文，如 email）：")
        if not ok1 or not key.strip():
            return
        label, ok2 = QInputDialog.getText(self, "添加内置列", "显示名（如 邮箱）：")
        if not ok2 or not label.strip():
            return
        self._append_builtin_row(BuiltinColumn(key=key.strip(), label=label.strip()))

    def _on_delete_builtin(self) -> None:
        """删除选中的内置列行。"""
        row = self._builtin_table.currentRow()
        if row >= 0:
            self._builtin_table.removeRow(row)

    def _build_buttons(self) -> QHBoxLayout:
        """底部保存/取消按钮 + 快捷键说明。"""
        row = QHBoxLayout()
        hint = QLabel("快捷键：⌘ + , 打开设置")
        hint.setStyleSheet("color: #999999;")
        row.addWidget(hint)
        row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        row.addWidget(cancel_btn)
        row.addWidget(save_btn)
        return row

    def _collect_builtin_columns(self) -> List[BuiltinColumn]:
        """从表格收集内置列（key 为空的行跳过）。"""
        columns: List[BuiltinColumn] = []
        for row in range(self._builtin_table.rowCount()):
            key = self._builtin_table.item(row, 0).text().strip()
            if not key:
                continue
            label = self._builtin_table.item(row, 1).text().strip() or key
            aliases = [
                a.strip() for a in self._builtin_table.item(row, 2).text().split("，")
                if a.strip()
            ]
            columns.append(BuiltinColumn(key=key, label=label, aliases=aliases))
        return columns

    def _collect_phone_separators(self) -> List[str]:
        """从多行编辑框收集手机号分隔符（空行跳过，转义还原）。"""
        separators: List[str] = []
        for line in self._phone_separators_edit.toPlainText().splitlines():
            line = line.strip()
            if not line:
                continue
            separators.append(_PHONE_SEP_PARSE.get(line, line))
        return separators

    def _collect_settings(self) -> AppSettings:
        """汇总对话框所有控件为 AppSettings。"""
        sep_index = self._separator_combo.currentIndex()
        separator = self._separator_edit.text() if sep_index == self._separator_custom_index \
            else self._separator_combo.currentData()
        vcf_fields = [
            key for key, check in zip(_VCF_KEYS, self._vcf_checks) if check.isChecked()
        ]
        settings = AppSettings(
            builtin_columns=self._collect_builtin_columns(),
            phone_validate=self._validate_check.isChecked(),
            phone_highlight=self._highlight_check.isChecked(),
            phone_merge=self._merge_check.isChecked(),
            phone_separators=self._collect_phone_separators(),
            csv_encoding=self._encoding_combo.currentData(),
            txt_encoding=self._txt_encoding_combo.currentData(),
            txt_separator=separator,
            vcf_fields=vcf_fields,
            vcf_name_prefix=self._vcf_prefix_edit.text().strip(),
            vcf_name_suffix=self._vcf_suffix_edit.text().strip(),
            vcf_timestamp=self._vcf_ts_check.isChecked(),
            vcf_timestamp_position=(
                "prefix"
                if self._vcf_ts_pos_combo.currentText() == "姓名前" else "suffix"
            ),
            declaration_detect=self._declaration_check.isChecked(),
            declaration_keywords=[
                k.strip() for k in self._keywords_edit.text().split("，")
                if k.strip()
            ],
            log_debug=self._log_debug_check.isChecked(),
            auto_update_enabled=self._auto_update_check.isChecked(),
        )
        return settings

    def _on_save(self) -> None:
        """保存设置并关闭（写入失败时弹窗提示）。"""
        if not self._collect_builtin_columns():
            QMessageBox.warning(self, "提示", "内置列不能为空")
            return
        try:
            save_app_settings(self._collect_settings())
        except WpsEnhancerError as e:
            get_logger("ui.settings_dialog").error(str(e))
            QMessageBox.critical(self, "错误", str(e))
            return
        except Exception as e:
            get_logger("ui.settings_dialog").exception(f"保存设置失败：{e}")
            QMessageBox.critical(self, "错误", f"保存设置失败：{e}\n详情见日志")
            return
        self.accept()
