"""设置对话框主类：组装各 tab mixin + 底部按钮 + 保存/恢复默认。"""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget,
    QVBoxLayout,
)

from core.exceptions import WpsEnhancerError
from core.logger import get_logger
from core import settings as _settings_mod
from core.settings import (
    AppSettings, get_app_settings,
)
from core.template.config import BuiltinColumn
from ui.components.settings.constants import _PHONE_SEP_DISPLAY, _PHONE_SEP_PARSE
from ui.components.settings.tab_about import AboutTabMixin
from ui.components.settings.tab_builtin import BuiltinTabMixin
from ui.components.settings.tab_export import ExportTabMixin
from ui.components.settings.tab_import import ImportTabMixin
from ui.components.settings.tab_log import LogTabMixin
from ui.components.settings.tab_update import UpdateTabMixin
from ui.components import toast


class SettingsDialog(
    QDialog, ImportTabMixin, ExportTabMixin, BuiltinTabMixin,
    LogTabMixin, UpdateTabMixin, AboutTabMixin,
):
    """全局设置对话框（分页 Tab：导入处理 / 导出格式 / 内置列 / 日志）。"""

    def __init__(self, parent=None, settings: Optional[AppSettings] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(640, 520)
        self._settings = settings if settings is not None else get_app_settings()

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_import_tab(), "导入处理")
        tabs.addTab(self._build_export_tab(), "导出格式")
        tabs.addTab(self._build_builtin_tab(), "内置列")
        tabs.addTab(self._build_log_tab(), "日志")
        tabs.addTab(self._build_update_tab(), "更新")
        tabs.addTab(self._build_about_tab(), "关于")
        layout.addWidget(tabs)
        layout.addLayout(self._build_buttons())

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
            _settings_mod.save_app_settings(AppSettings())
        except WpsEnhancerError as e:
            get_logger("ui.settings_dialog").error(f"恢复默认设置失败：{e}")
            toast.show_toast(self.parent() or self, f"重置失败：{e}", success=False)
            return
        toast.show_toast(self.parent() or self, "重置成功")
        self.accept()

    def _collect_builtin_columns(self) -> List[BuiltinColumn]:
        """从内置列表格收集内置列（跳过占位行与空行）。"""
        columns: List[BuiltinColumn] = []
        for row in range(self._builtin_table.rowCount()):
            if self._is_placeholder_row(row):
                continue
            key = self._builtin_table.item(row, 0).text().strip()
            label = self._builtin_table.item(row, 1).text().strip()
            if not key:
                continue
            aliases = [
                a.strip() for a in
                self._builtin_table.item(row, 2).text().split("，")
                if a.strip()
            ]
            columns.append(BuiltinColumn(key=key, label=label or key, aliases=aliases))
        return columns

    def _collect_phone_separators(self) -> List[str]:
        """从多手机号分隔符编辑框收集（转义显示还原为真实字符）。"""
        separators: List[str] = []
        for line in self._phone_separators_edit.toPlainText().splitlines():
            sep = _PHONE_SEP_PARSE.get(line, line)
            if sep and sep not in separators:
                separators.append(sep)
        return separators

    def _collect_settings(self) -> AppSettings:
        """从各 tab 控件收集为完整设置对象。"""
        vcf_fields = [
            key for key, check in zip(
                ("name", "phone", "company", "website"), self._vcf_checks,
            ) if check.isChecked()
        ]
        if not vcf_fields:
            vcf_fields = ["name", "phone", "company", "website"]
        separator = self._separator_edit.text().strip() \
            if self._separator_combo.currentData() == "__custom__" \
            else self._separator_combo.currentData()
        if not separator:
            separator = " "
        settings = AppSettings(
            builtin_columns=self._collect_builtin_columns(),
            phone_validate=self._validate_check.isChecked(),
            phone_highlight=self._highlight_check.isChecked(),
            phone_merge=self._merge_check.isChecked(),
            phone_separators=self._collect_phone_separators(),
            source_separator=self._source_sep_combo.currentData(),
            source_encoding=self._source_enc_combo.currentData(),
            csv_encoding=self._encoding_combo.currentData(),
            txt_encoding=self._txt_encoding_combo.currentData(),
            txt_separator=separator,
            vcf_fields=vcf_fields,
            vcf_name_prefix=self._vcf_prefix_edit.text().strip(),
            vcf_name_suffix=self._vcf_suffix_edit.text().strip(),
            vcf_timestamp=self._vcf_ts_check.isChecked(),
            vcf_timestamp_position=(
                "prefix" if self._vcf_ts_pos_combo.currentText() == "姓名前"
                else "suffix"
            ),
            declaration_detect=self._declaration_check.isChecked(),
            declaration_keywords=[
                k.strip() for k in self._keywords_edit.text().split("，")
                if k.strip()
            ],
            log_debug=self._log_debug_check.isChecked(),
            log_retain_days=self._retain_combo.currentData(),
            log_auto_clean=self._auto_clean_check.isChecked(),
            auto_update_enabled=self._auto_update_check.isChecked(),
            use_system_proxy=self._proxy_check.isChecked(),
            update_url=self._update_url_edit.text().strip(),
            download_dir=self._download_dir_edit.text().strip(),
            install_dir=self._install_dir_edit.text().strip(),
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
            _settings_mod.save_app_settings(new_settings)
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
        toast.show_toast(self.parent() or self, "保存成功")
        self.accept()
