from typing import List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox,
    QCheckBox, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QInputDialog, QPlainTextEdit, QTabWidget, QWidget,
    QFileDialog, QAbstractItemView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHeaderView

from core.settings import (
    AppSettings, ENCODING_CHOICES, SEPARATOR_CHOICES, get_app_settings,
    save_app_settings,
)
from core.exceptions import WpsEnhancerError
from core.logger import get_logger
from core.template.config import BuiltinColumn
from ui.components.toast import show_toast

# vcf 可导出字段（v1 仅四个默认内置列）
_VCF_KEYS = ["name", "phone", "company", "website"]
_VCF_LABELS = {"name": "姓名", "phone": "手机", "company": "公司名", "website": "网址"}
_SEPARATOR_LABELS = {" ": "空格", "\t": "Tab", ",": "逗号", "、": "顿号", "|": "竖线"}
# 手机号分隔符编辑时的转义显示（空格/Tab/换行 无法直接看清）
_PHONE_SEP_DISPLAY = {" ": "[空格]", "\t": "[Tab]", "\n": "[换行]"}
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
        self._proxy_check = QCheckBox("自动使用系统代理（网络受限时建议开启）")
        self._proxy_check.setChecked(self._settings.use_system_proxy)
        layout.addWidget(self._proxy_check)
        self._update_url_edit = QLineEdit(self._settings.update_url)
        self._update_url_edit.setPlaceholderText(
            "https://example.com/update.json（留空使用 GitHub Releases）",
        )
        layout.addWidget(QLabel("自定义更新源（国内网络不稳定时使用）"))
        layout.addWidget(self._update_url_edit)
        tip = QLabel(
            "留空则从 GitHub Releases 检查更新；填写 update.json 地址后优先从"
            "自定义源检查与下载（可托管到 Gitee/OSS 等国内可达地址，"
            "格式见 README「自定义更新源」）。",
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(tip)
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
        """手动检查更新（后台检查，结果弹窗；完成后复位状态文本）。"""
        from ui.components.update_flow import check_update_now
        self._check_update_btn.setEnabled(False)
        self._update_status_label.setText("正在检查更新…")

        def _reset_status() -> None:
            # 检查完成（无论成功失败）：复位按钮与状态文本
            self._check_update_btn.setEnabled(True)
            self._update_status_label.setText("")

        check_update_now(
            self, silent_on_failure=False, on_done=_reset_status,
            use_proxy=self._settings.use_system_proxy,
            update_url=self._update_url_edit.text().strip() or None,
        )

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
        """日志分组（详细开关 + 导出/清空）。"""
        from core.app_paths import get_logs_dir
        group = QGroupBox("日志")
        layout = QVBoxLayout(group)
        self._log_debug_check = QCheckBox("详细日志（DEBUG，排查问题时开启）")
        self._log_debug_check.setChecked(self._settings.log_debug)
        layout.addWidget(self._log_debug_check)
        hint = QLabel(f"日志目录：{get_logs_dir()}")
        hint.setStyleSheet("color: #888888;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        row = QHBoxLayout()
        export_btn = QPushButton("导出日志文件")
        export_btn.clicked.connect(self._on_export_logs)
        clear_btn = QPushButton("删除日志记录")
        clear_btn.clicked.connect(self._on_clear_logs)
        row.addWidget(export_btn)
        row.addWidget(clear_btn)
        row.addStretch()
        layout.addLayout(row)

        cleanup_row = QHBoxLayout()
        cleanup_row.addWidget(QLabel("保留最近"))
        self._retain_combo = QComboBox()
        for days in (15, 30, 60, 90, 365):
            self._retain_combo.addItem(f"{days} 天", days)
        self._retain_combo.setCurrentIndex(1)  # 默认 30 天
        cleanup_row.addWidget(self._retain_combo)
        cleanup_btn = QPushButton("清理过期日志")
        cleanup_btn.clicked.connect(self._on_cleanup_logs)
        cleanup_row.addWidget(cleanup_btn)
        cleanup_row.addStretch()
        layout.addLayout(cleanup_row)
        return group

    def _on_cleanup_logs(self) -> None:
        """按保留天数清理过期日志（二次确认；失败兜底提示）。"""
        from core.logger import cleanup_logs
        retain = self._retain_combo.currentData()
        answer = QMessageBox.question(
            self, "清理过期日志",
            f"将删除 {retain} 天前的过期日志文件，确定继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted, failed = cleanup_logs(retain)
        except Exception as e:
            get_logger("ui.settings_dialog").exception(f"清理日志失败：{e}")
            show_toast(self.parent() or self, f"清理失败：{e}", success=False)
            return
        if failed:
            show_toast(
                self.parent() or self,
                f"清理完成，{failed} 个文件删除失败（权限或占用）",
                success=False,
            )
        elif deleted:
            show_toast(self.parent() or self, f"已清理 {deleted} 个过期日志")
        else:
            show_toast(self.parent() or self, "没有过期日志", success=False)

    def _on_export_logs(self) -> None:
        """导出当天日志文件到用户选择的位置。"""
        import shutil
        from datetime import datetime as _dt
        from core.app_paths import get_logs_dir
        log_dir = get_logs_dir()
        log_file = log_dir / f"wps_enhancer_{_dt.now().strftime('%Y%m%d')}.log"
        if not log_file.exists():
            show_toast(self, "暂无日志文件", success=False)
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "导出日志文件", str(log_file),
            "日志文件 (*.log);;所有文件 (*)",
        )
        if not dest:
            return
        try:
            shutil.copy(log_file, dest)
        except OSError as e:
            get_logger("ui.settings_dialog").error(f"导出日志失败：{e}")
            show_toast(self, f"导出失败：{e}", success=False)
            return
        show_toast(self, "日志已导出")

    def _on_clear_logs(self) -> None:
        """清空全部日志记录（二次确认；当天日志文件保留但内容清空）。"""
        from core.app_paths import get_logs_dir
        log_dir = get_logs_dir()
        logs = sorted(log_dir.glob("wps_enhancer_*.log"))
        if not logs:
            show_toast(self, "暂无日志记录", success=False)
            return
        answer = QMessageBox.question(
            self, "删除日志记录",
            f"确定清空全部 {len(logs)} 个日志文件吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for f in logs:
            try:
                # 清空而非删文件：正在写入的 TimedRotatingFileHandler 持有旧 fd，
                # 删文件会导致后续日志不再落盘；truncate 后 O_APPEND 继续从新末尾写
                with open(f, "w", encoding="utf-8"):
                    pass
            except OSError:
                pass
        show_toast(self, "日志已清空")

    def _build_builtin_group(self) -> QGroupBox:
        """内置列管理分组（增删改查；双击单元格输入，与模板表格一致）。"""
        group = QGroupBox("内置列（姓名/手机/公司名/网址）")
        layout = QVBoxLayout(group)
        self._builtin_table = QTableWidget(0, 3)
        self._builtin_table.setHorizontalHeaderLabels(["语义键", "显示名", "匹配别名（逗号分隔）"])
        self._builtin_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed,
        )
        self._builtin_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._builtin_table.setColumnWidth(0, 160)
        self._builtin_table.setColumnWidth(1, 120)
        self._builtin_table.verticalHeader().setVisible(False)
        # 列宽分配：匹配别名（内容多）Stretch 吃剩余空间，语义键/显示名固定
        self._builtin_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed,
        )
        self._builtin_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed,
        )
        self._builtin_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch,
        )
        self._builtin_table.itemChanged.connect(self._on_builtin_item_changed)
        for col in self._settings.builtin_columns:
            self._append_builtin_row(col)
        self._append_builtin_placeholder()
        layout.addWidget(self._builtin_table)

        btn_row = QHBoxLayout()
        hint = QLabel("双击单元格编辑 / 双击占位行添加")
        hint.setStyleSheet("color: #888888;")
        btn_row.addWidget(hint)
        btn_row.addStretch()
        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self._on_delete_builtin)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)
        return group

    _PLACEHOLDER_TEXT = "双击输入语义键，添加内置列"

    def _append_builtin_row(self, col: BuiltinColumn) -> None:
        """向内置列表格追加一行（全部单元格可双击编辑）。"""
        row = self._builtin_table.rowCount()
        self._builtin_table.insertRow(row)
        self._builtin_table.setItem(row, 0, QTableWidgetItem(col.key))
        self._builtin_table.setItem(row, 1, QTableWidgetItem(col.label))
        self._builtin_table.setItem(row, 2, QTableWidgetItem("，".join(col.aliases)))

    def _append_builtin_placeholder(self) -> None:
        """追加占位行：双击第一格输入语义键即可创建新内置列。"""
        row = self._builtin_table.rowCount()
        self._builtin_table.insertRow(row)
        item = QTableWidgetItem(self._PLACEHOLDER_TEXT)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
        item.setForeground(QColor("#999999"))
        self._builtin_table.setItem(row, 0, item)
        locked = Qt.ItemFlag.ItemIsEnabled
        self._builtin_table.setItem(row, 1, QTableWidgetItem(""))
        self._builtin_table.item(row, 1).setFlags(locked)
        self._builtin_table.setItem(row, 2, QTableWidgetItem(""))
        self._builtin_table.item(row, 2).setFlags(locked)

    def _is_placeholder_row(self, row: int) -> bool:
        """判断行是否为占位行（特征：第 1 列单元格不可编辑）。

        不能按文本判断：itemChanged 触发时占位文本已被新输入替换。
        """
        cell = self._builtin_table.item(row, 1)
        return cell is not None and not (
            cell.flags() & Qt.ItemFlag.ItemIsEditable
        )

    def _on_builtin_item_changed(self, item: QTableWidgetItem) -> None:
        """占位行第一格输入语义键后：该行转为真实行，并追加新占位行。"""
        if item.column() != 0 or item.row() < 0:
            return
        if not self._is_placeholder_row(item.row()):
            return  # 真实行编辑无需处理
        text = item.text().strip()
        if not text or text == self._PLACEHOLDER_TEXT:
            return
        row = item.row()
        self._builtin_table.blockSignals(True)
        self._builtin_table.setItem(row, 0, QTableWidgetItem(text))
        # 1/2 列恢复可编辑
        for col in (1, 2):
            cell = self._builtin_table.item(row, col)
            cell.setFlags(cell.flags() | Qt.ItemFlag.ItemIsEditable)
        self._builtin_table.blockSignals(False)
        self._append_builtin_placeholder()

    def _on_delete_builtin(self) -> None:
        """删除选中的内置列行（二次确认）。"""
        row = self._builtin_table.currentRow()
        if row < 0 or self._is_placeholder_row(row):
            show_toast(self, "请先选择要删除的内置列", success=False)
            return
        answer = QMessageBox.question(
            self, "删除内置列",
            f"确定删除内置列「{self._builtin_table.item(row, 0).text()}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._builtin_table.removeRow(row)

    def _build_buttons(self) -> QHBoxLayout:
        """底部恢复默认/取消/保存按钮 + 快捷键说明。"""
        row = QHBoxLayout()
        reset_btn = QPushButton("恢复默认设置")
        reset_btn.setStyleSheet(
            "background-color: transparent; color: #6B7280;"
            "border: 1px solid #E5E7EB;",
        )
        reset_btn.clicked.connect(self._on_reset_defaults)
        row.addWidget(reset_btn)
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

    def _on_reset_defaults(self) -> None:
        """恢复默认设置（二次确认 → 保存默认 → 轻提示 → 关闭）。"""
        from core.settings import AppSettings
        answer = QMessageBox.question(
            self, "恢复默认设置",
            "确定将所有设置恢复为默认值吗？当前设置将被覆盖。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            save_app_settings(AppSettings())
        except WpsEnhancerError as e:
            get_logger("ui.settings_dialog").error(f"恢复默认设置失败：{e}")
            show_toast(self.parent() or self, f"重置失败：{e}", success=False)
            return
        show_toast(self.parent() or self, "重置成功")
        self.accept()

    def _collect_builtin_columns(self) -> List[BuiltinColumn]:
        """从表格收集内置列（key 为空或占位提示的行跳过）。"""
        columns: List[BuiltinColumn] = []
        for row in range(self._builtin_table.rowCount()):
            key = self._builtin_table.item(row, 0).text().strip()
            if not key or key == self._PLACEHOLDER_TEXT:
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
            use_system_proxy=self._proxy_check.isChecked(),
            update_url=self._update_url_edit.text().strip(),
        )
        return settings

    def _on_save(self) -> None:
        """保存设置并关闭（无变化不提示；写入失败时弹窗提示）。"""
        new_settings = self._collect_settings()
        if not new_settings.builtin_columns:
            QMessageBox.warning(self, "提示", "内置列不能为空")
            return
        changed = new_settings != self._settings
        try:
            save_app_settings(new_settings)
        except WpsEnhancerError as e:
            get_logger("ui.settings_dialog").error(str(e))
            QMessageBox.critical(self, "错误", str(e))
            return
        except Exception as e:
            get_logger("ui.settings_dialog").exception(f"保存设置失败：{e}")
            QMessageBox.critical(self, "错误", f"保存设置失败：{e}\n详情见日志")
            return
        if not changed:
            self.accept()
            return
        # 设置发生变化：轻提示（显示在父窗口上，对话框关闭后仍可见）
        show_toast(self.parent() or self, "保存成功")
        self.accept()
