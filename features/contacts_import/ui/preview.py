"""预览与导出展示（PreviewMixin）。

预览展示「即将导出的内容」：
- xlsx/xls：表格形式（模板全部列，vcf 相关设置不生效）
- csv/txt/vcf：文本形式（与导出文件内容完全一致）
"""

from typing import List

from PyQt6.QtGui import QColor

from core.settings import get_app_settings
from features.contacts_import.ui.base import _MAX_COL_WIDTH, _PREVIEW_LIMIT
from features.contacts_import.ui.base import _safe_slot
from features.contacts_import.processor import (
    build_preview_data, build_preview_display, build_text_preview,
)

# 表格形式预览的格式（其余为文本形式）
_TABLE_FORMATS = ("xlsx", "xls")


class PreviewMixin:
    """预览数据生成与展示（含导出格式联动）。"""

    def _on_format_changed(self, fmt: str) -> None:
        """导出格式变化：vcf 专属控件按格式显隐，并刷新预览展示。"""
        vcf_mode = fmt == "vcf"
        self._vcf_custom_row.setVisible(vcf_mode)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """重新生成预览并展示。

        导出按钮仅预览正常且存在数据时开放；生成失败/无数据时
        禁用按钮并给出明确提示（异常兜底）。
        """
        if self._template is None or self._sheet_data is None or self._matches is None:
            self._export_btn.setEnabled(False)
            return
        try:
            settings = get_app_settings()
            self._preview = build_preview_data(
                self._sheet_data, self._template, self._matches, settings,
            )
        except Exception as e:
            from core.logger import get_logger
            get_logger("contacts_import.preview").exception(f"预览生成失败：{e}")
            self._preview = None
            self._export_btn.setEnabled(False)
            self._status_bar.show_error(f"预览生成失败：{e}")
            return
        total = len(self._preview.rows)
        self._export_count_label.setText(f"导出 {total} 行")
        if total == 0:
            self._export_btn.setEnabled(False)
            self._status_bar.show_info("无数据可导出，请检查列映射")
            return
        self._export_btn.setEnabled(True)
        self._display_preview(settings)

    def _display_preview(self, settings) -> None:
        """展示预览面板：按导出格式切换表格/文本模式。"""
        if self._preview is None or self._template is None:
            return
        self._all_rows_visible = False
        total = len(self._preview.rows)
        fmt = self._format_combo.currentText()
        self._update_preview_header(total)
        if fmt in _TABLE_FORMATS:
            self._display_table_preview(settings)
        else:
            self._display_text_preview(settings)

        if total > _PREVIEW_LIMIT:
            self._toggle_btn.setText(f"展开查看全部 {total} 行")
            self._toggle_btn.setVisible(True)
        else:
            self._toggle_btn.setVisible(False)

        self._preview_group.setVisible(True)
        self._export_btn.setEnabled(total > 0)

    def _display_table_preview(self, settings) -> None:
        """表格模式（xlsx/xls）：显示模板全部列。"""
        self._preview_table.setVisible(True)
        self._preview_text.setVisible(False)
        headers, display_rows = build_preview_display(
            self._preview, self._matches, settings,
            self._format_combo.currentText(),
        )
        self._setup_preview_table(headers)
        self._fill_preview_table(display_rows[:_PREVIEW_LIMIT], settings)

    def _display_text_preview(self, settings) -> None:
        """文本模式（csv/txt/vcf）：显示与导出文件一致的文本内容。"""
        self._preview_text.setVisible(True)
        self._preview_table.setVisible(False)
        fmt = self._format_combo.currentText()
        text = build_text_preview(
            self._preview, self._matches, settings, fmt, _PREVIEW_LIMIT,
        )
        self._preview_text.setPlainText(text.rstrip("\n"))

    def _setup_preview_table(self, headers: List[str]) -> None:
        """按导出格式设置预览表格列。"""
        self._preview_table.setColumnCount(len(headers))
        self._preview_table.setHorizontalHeaderLabels(headers)

    def _update_preview_header(self, total: int) -> None:
        """更新预览顶部汇总与警告横幅（vcf 时显示当前生效的姓名前缀）。"""
        if self._preview is None:
            return
        prefix_note = ""
        if self._format_combo.currentText() == "vcf":
            from features.contacts_import.processor import _effective_vcf_prefix
            prefix_note = f"，vcf 姓名前缀：{_effective_vcf_prefix(get_app_settings())}"
        if self._preview.invalid_count > 0:
            self._summary_label.setText(
                f"共 {total} 行{prefix_note}，其中 "
                f"{self._preview.invalid_count} 个手机号格式异常"
            )
            self._warning_label.setText(
                "\n".join(self._preview.invalid_summary),
            )
            self._warning_widget.setVisible(True)
            self._export_btn.setText("忽略并继续导出")
        else:
            self._summary_label.setText(f"共 {total} 行{prefix_note}")
            self._warning_widget.setVisible(False)
            self._export_btn.setText("确认导出")

    def _fill_preview_table(self, display_rows, settings) -> None:
        """将导出预览行（List[str]）填充到预览表格。"""
        if self._preview is None:
            return
        self._preview_table.setRowCount(len(display_rows))
        for i, row in enumerate(display_rows):
            for j, value in enumerate(row):
                item = self._make_cell_item(value, _MAX_COL_WIDTH)
                if (
                    not self._preview.rows[i].phone_valid
                    and settings.phone_highlight
                ):
                    item.setBackground(QColor("#FF0000"))
                self._preview_table.setItem(i, j, item)

    @_safe_slot
    def _toggle_preview_rows(self) -> None:
        """展开/收起全部预览（表格模式切行数，文本模式切全文）。"""
        if self._preview is None or self._matches is None:
            return
        settings = get_app_settings()
        fmt = self._format_combo.currentText()
        total = len(self._preview.rows)
        if self._all_rows_visible:
            # 收起
            if fmt in _TABLE_FORMATS:
                headers, display_rows = build_preview_display(
                    self._preview, self._matches, settings, fmt,
                )
                self._fill_preview_table(display_rows[:_PREVIEW_LIMIT], settings)
            else:
                self._preview_text.setPlainText(
                    build_text_preview(
                        self._preview, self._matches, settings, fmt,
                        _PREVIEW_LIMIT,
                    ).rstrip("\n"),
                )
            self._toggle_btn.setText(f"展开查看全部 {total} 行")
            self._all_rows_visible = False
        else:
            # 展开全部
            if fmt in _TABLE_FORMATS:
                headers, display_rows = build_preview_display(
                    self._preview, self._matches, settings, fmt,
                )
                self._fill_preview_table(display_rows, settings)
            else:
                self._preview_text.setPlainText(
                    build_text_preview(
                        self._preview, self._matches, settings, fmt, total,
                    ).rstrip("\n"),
                )
            self._toggle_btn.setText("收起")
            self._all_rows_visible = True
