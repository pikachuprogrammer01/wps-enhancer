"""列映射表格与源表预览渲染（拆分自 panel.py：MappingTableMixin）。"""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QComboBox, QPushButton, QTableWidgetItem,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor

from features.contacts_import.ui import base as _dlg
from core.settings import get_app_settings
from core.template import Template, TemplateColumn, match_columns
from features.contacts_import.ui.base import (
    _MAX_COL_WIDTH, _SOURCE_COL_WIDTH, _SOURCE_PREVIEW_LIMIT, _STATUS_TEXT,
)
from features.contacts_import.ui.base import _safe_slot


class MappingTableMixin:
    """列映射表格：渲染/列名编辑/拖拽排序/增删列/源表联动高亮。"""

    def _rebuild_matches(self) -> None:
        """按当前手动映射重建匹配结果并刷新映射表格。"""
        if self._template is None or self._sheet_data is None:
            return
        settings = get_app_settings()
        self._matches = match_columns(
            self._sheet_data.headers, self._template,
            settings.builtin_columns, self._manual_map,
        )
        self._update_template_summary()
        self._fill_mapping_table()

    def _update_template_summary(self) -> None:
        """更新模板摘要：列名列表 + 已映射列数（无模板时显示内置列）。"""
        if self._template is None:
            self._template_summary.setText("")
            return
        cols = [c.name for c in self._template.columns if c.enabled]
        mapped = sum(1 for m in (self._matches or []) if m.source_col)
        self._template_summary.setText(
            f"列：{'、'.join(cols)}（共 {len(cols)} 列，已映射 {mapped} 列）",
        )

    def _make_cell_item(
        self, text: str, width: int = _MAX_COL_WIDTH,
    ) -> QTableWidgetItem:
        """生成单元格项：超长文本省略号显示，tooltip 提供全文。"""
        elided = self.fontMetrics().elidedText(
            text, Qt.TextElideMode.ElideRight, width,
        )
        item = QTableWidgetItem(elided)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        if elided != text:
            item.setToolTip(text)
        return item

    def _fill_mapping_table(self) -> None:
        """填充映射编辑表格（模板列可编辑 | 状态 | 源列 | 示例 | 操作）。"""
        if self._matches is None or self._sheet_data is None:
            return
        headers = [""] + self._sheet_data.headers
        self._mapping_table.blockSignals(True)  # 防 itemChanged 递归
        try:
            self._mapping_table.setRowCount(len(self._matches))
            self._mapping_table.setColumnWidth(0, 140)
            self._mapping_table.setColumnWidth(1, 90)
            self._mapping_table.setColumnWidth(2, _SOURCE_COL_WIDTH)
            self._mapping_table.setColumnWidth(3, _MAX_COL_WIDTH)
            self._mapping_table.setColumnWidth(4, 60)
            for row, match in enumerate(self._matches):
                name_item = self._make_cell_item(match.template_col.name, 140)
                name_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable,
                )
                name_item.setData(
                    Qt.ItemDataRole.UserRole, match.template_col.key,
                )  # 拖拽排序时按 key 重排模板列
                self._mapping_table.setItem(row, 0, name_item)

                status_item = self._make_cell_item(_STATUS_TEXT[match.status], 90)
                if match.status == "none":
                    status_item.setBackground(QColor("#FFF9C4"))
                self._mapping_table.setItem(row, 1, status_item)

                combo = QComboBox()
                # 源列下拉：仅去除空表头项（空行），无映射时保持未选中（空白）
                combo.addItems([h for h in headers if h.strip()])
                if match.source_col:
                    combo.setCurrentText(match.source_col)
                else:
                    combo.setCurrentIndex(-1)  # 未映射：不选中任何项（空白）
                combo.currentTextChanged.connect(
                    lambda text, r=row: self._on_mapping_changed(r, text),
                )
                self._mapping_table.setCellWidget(row, 2, combo)

                example_item = self._make_cell_item(
                    self._source_example_values(match.source_col), _MAX_COL_WIDTH,
                )
                self._mapping_table.setItem(row, 3, example_item)

                del_btn = QPushButton("删除")
                del_btn.setFixedWidth(48)
                del_btn.setStyleSheet(
                    "QPushButton { padding: 3px 6px; font-size: 12px; }",
                )
                del_btn.clicked.connect(
                    lambda checked=False, r=row: self._remove_template_column(r),
                )
                self._mapping_table.setCellWidget(row, 4, del_btn)
            # 末尾占位行：双击第一格直接输入列名添加（提示语）
            placeholder_row = len(self._matches)
            self._mapping_table.setRowCount(placeholder_row + 1)
            placeholder_item = QTableWidgetItem("双击输入列名，添加模板列")
            placeholder_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable,
            )
            placeholder_item.setForeground(QColor("#999999"))
            self._mapping_table.setItem(placeholder_row, 0, placeholder_item)
        finally:
            self._mapping_table.blockSignals(False)

    def _source_example_values(self, source_col: Optional[str]) -> str:
        """返回源列前 3 个非空值的示例（无数据返回「—」）。"""
        if not source_col or self._sheet_data is None:
            return "—"
        values = [
            row.get(source_col, "") for row in self._sheet_data.rows
            if row.get(source_col, "").strip()
        ]
        examples = values[:3]
        return " / ".join(examples) if examples else "—"

    def _fill_source_table(self) -> None:
        """填充源表内容表格（表头 + 前 10 行原始数据）。"""
        if self._sheet_data is None:
            return
        headers = self._sheet_data.headers
        rows = self._sheet_data.rows[:_SOURCE_PREVIEW_LIMIT]
        self._source_table.setColumnCount(len(headers))
        self._source_table.setHorizontalHeaderLabels(headers)
        self._source_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, header in enumerate(headers):
                item = self._make_cell_item(
                    row.get(header, ""), _SOURCE_COL_WIDTH,
                )
                self._source_table.setItem(i, j, item)
            # 列宽 = 表头长度自适应，但不超过上限（防撑破窗口）
            for j, header in enumerate(headers):
                width = min(
                    max(60, self.fontMetrics().horizontalAdvance(header) + 24),
                    _SOURCE_COL_WIDTH,
                )
                self._source_table.setColumnWidth(j, width)

    def _highlight_source_column(self, source_col: str) -> None:
        """高亮源表预览中选中的列（空值清除全部高亮）。"""
        highlight_col = -1
        if source_col and self._sheet_data is not None:
            highlight_col = next(
                (i for i, h in enumerate(self._sheet_data.headers) if h == source_col),
                -1,
            )
        for col in range(self._source_table.columnCount()):
            for row in range(self._source_table.rowCount()):
                item = self._source_table.item(row, col)
                if item is None:
                    continue
                if col == highlight_col:
                    item.setBackground(QColor("#D6EAF8"))
                else:
                    item.setBackground(QBrush())

    def _on_rows_moved(self, parent, start: int, end: int, dest, row: int) -> None:
        """拖拽行排序后：按表格当前顺序重排模板列并重建匹配。"""
        if self._template is None or self._matches is None:
            return
        order: List[str] = []
        for r in range(min(len(self._template.columns), self._mapping_table.rowCount())):
            item = self._mapping_table.item(r, 0)
            key = item.data(Qt.ItemDataRole.UserRole) if item else None
            if key:
                order.append(key)
        by_key = {c.key: c for c in self._template.columns}
        self._template.columns = [by_key[k] for k in order if k in by_key]
        self._rebuild_matches()
        self._refresh_preview()
        self._status_bar.show_info("模板列顺序已调整")

    @_safe_slot
    def _on_column_name_edited(self, item: QTableWidgetItem) -> None:
        """模板列名单元格编辑结束：已有行改列名，占位行输入即新增。"""
        if item.column() != 0 or self._matches is None or self._template is None:
            return
        row = item.row()
        text = item.text().strip()
        if row < len(self._matches):
            if not text or text == self._template.columns[row].name:
                item.setText(self._template.columns[row].name)  # 空/未变恢复
                return
            self._template.columns[row].name = text
            self._rebuild_matches()
            self._refresh_preview()
            self._status_bar.show_info(f"模板列已改名为「{text}」")
        elif row == len(self._matches):
            if not text or text == "双击输入列名，添加模板列":
                item.setText("双击输入列名，添加模板列")
                return
            self._add_template_column(text)

    @_safe_slot
    def _remove_template_column(self, row: int) -> None:
        """删除映射表中的模板列（需二次确认）。"""
        if self._matches is None or self._template is None or row >= len(self._matches):
            return
        name = self._template.columns[row].name
        answer = _dlg.QMessageBox.question(
            self, "删除模板列",
            f"确定删除模板列「{name}」吗？\n删除后该列不再导出。",
            _dlg.QMessageBox.StandardButton.Yes | _dlg.QMessageBox.StandardButton.No,
            _dlg.QMessageBox.StandardButton.No,
        )
        if answer != _dlg.QMessageBox.StandardButton.Yes:
            return
        key = self._template.columns[row].key
        self._template.columns.pop(row)
        self._manual_map.pop(key, None)
        self._rebuild_matches()
        self._refresh_preview()
        self._status_bar.show_info(f"已删除模板列「{name}」")

    @_safe_slot
    def _on_add_template_column(self) -> None:
        """点击占位行弹窗添加模板列。"""
        if self._template is None or self._sheet_data is None:
            _dlg.QMessageBox.information(self, "提示", "请先选择源文件并应用模板")
            return
        name, ok = _dlg.QInputDialog.getText(
            self, "添加模板列", "列名（导出表头）：",
        )
        if not ok or not name.strip():
            return
        self._add_template_column(name.strip())

    def _add_template_column(self, name: str) -> None:
        """按列名添加模板列（手动状态、未设源列导出空列）。"""
        key = self._next_custom_key()
        self._template.columns.append(
            TemplateColumn(key=key, name=name),
        )
        self._manual_map[key] = ""  # 手动状态、未设源列 → 导出该列内容为空
        self._rebuild_matches()
        self._refresh_preview()
        self._status_bar.show_info(
            f"已添加模板列「{name}」，请在下方选择源列（留空则导出为空列）",
        )

    def _next_custom_key(self) -> str:
        """生成不冲突的自定义列语义键（custom_1、custom_2...）。"""
        keys = {c.key for c in self._template.columns}
        n = 1
        while f"custom_{n}" in keys:
            n += 1
        return f"custom_{n}"

    def _on_mapping_changed(self, row: int, source_col: str) -> None:
        """用户手动修改映射下拉后：高亮源表列并更新匹配与预览。"""
        if self._matches is None or self._template is None:
            return
        key = self._template.columns[row].key
        self._manual_map[key] = source_col
        self._highlight_source_column(source_col)
        self._rebuild_matches()
        self._refresh_preview()
