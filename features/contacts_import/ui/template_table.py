"""模板表格渲染与模板应用（拆分自 panel.py：TemplateTableMixin）。"""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QHBoxLayout, QPushButton, QTableWidgetItem, QWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

from features.contacts_import.ui import base as _dlg
from core.exceptions import WpsEnhancerError
from core.logger import get_logger, log_call
from core.settings import get_app_settings
from core.template import Template, TemplateColumn
from features.contacts_import.ui.base import (
    _DEFAULT_MAPPING_NAME, _MAX_COL_WIDTH, _TEMPLATE_CREATE_HINT,
)
from features.contacts_import.ui.base import _safe_slot


class TemplateTableMixin:
    """模板表格：加载/渲染/占位新建/选中/应用。"""

    def _reload_templates(self) -> None:
        """重新加载模板表格（首行固定默认映射项）。"""
        templates = self._get_manager().list_templates()
        self._fill_template_table(templates)
        self._template_table.setEnabled(True)
        self._no_template_label.setVisible(not bool(templates))

    def _fill_template_table(self, templates: List[Template]) -> None:
        """填充模板表格：默认映射项 + 模板列表 + 末行新建提示（双击输入创建）。"""
        self._template_table.blockSignals(True)
        try:
            self._template_table.setRowCount(len(templates) + 2)
            # 首行：默认映射（内置列）
            self._fill_template_row(
                0, _DEFAULT_MAPPING_NAME,
                "、".join(c.label for c in get_app_settings().builtin_columns),
                gray=True,
            )
            for row, t in enumerate(templates, start=1):
                cols = "、".join(c.name for c in t.columns if c.enabled)
                self._fill_template_row(row, t.name, cols)
            # 末行：占位提示（仅第二列可编辑，双击输入创建模板）
            placeholder_row = len(templates) + 1
            hint_item = self._make_cell_item(_TEMPLATE_CREATE_HINT, 260)
            hint_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable,
            )
            hint_item.setForeground(QColor("#999999"))
            self._template_table.setItem(placeholder_row, 1, hint_item)
            self._template_table.setItem(placeholder_row, 0, QTableWidgetItem(""))
            self._template_table.setItem(placeholder_row, 2, QTableWidgetItem(""))
        finally:
            self._template_table.blockSignals(False)

    @staticmethod
    def _parse_template_create_input(text: str) -> tuple:
        """解析「模板名：列1、列2」输入，返回 (名称, 列名列表)。"""
        name, sep, cols_part = text.partition("：")
        if not sep:
            name, sep, cols_part = text.partition(":")
        cols = [
            c.strip() for c in cols_part.replace(",", "、").split("、")
            if c.strip()
        ]
        return name.strip(), cols

    @_safe_slot
    def _on_template_cell_edited(self, item: QTableWidgetItem) -> None:
        """模板表格末行输入「模板名：列1、列2」创建模板（与列映射双击新增一致）。"""
        if item.column() != 1:
            return
        row = item.row()
        if row != self._template_table.rowCount() - 1:
            return  # 仅末行占位格参与创建
        text = item.text().strip()
        if not text or text == _TEMPLATE_CREATE_HINT:
            item.setText(_TEMPLATE_CREATE_HINT)
            return
        name, cols = self._parse_template_create_input(text)
        if not name or not cols:
            _dlg.QMessageBox.information(
                self, "提示", "格式：模板名：列1、列2（列名用顿号或逗号分隔）",
            )
            item.setText(_TEMPLATE_CREATE_HINT)
            return
        try:
            template = self._get_manager().create_from_headers(name, cols)
        except WpsEnhancerError as e:
            self._handle_error(e)
            item.setText(_TEMPLATE_CREATE_HINT)
            return
        self._status_bar.show_success(f"模板「{template.name}」已创建")
        # 延迟到编辑提交完成后刷新表格，避免在 itemChanged 处理中销毁正在编辑的 item
        QTimer.singleShot(0, self._reload_templates)

    def _fill_template_row(
        self, row: int, name: str, cols: str, gray: bool = False,
    ) -> None:
        """填充模板表格的一行（模板名存 UserRole）并放置该行操作按钮。"""
        name_item = self._make_cell_item(name, 160)
        name_item.setData(Qt.ItemDataRole.UserRole, name)
        cols_item = self._make_cell_item(cols, 260)
        if gray:
            for item in (name_item, cols_item):
                item.setForeground(QColor("#999999"))
        self._template_table.setItem(row, 0, name_item)
        self._template_table.setItem(row, 1, cols_item)
        # 操作列：每行独立的应用/编辑/重命名/删除按钮（默认映射行只有应用）
        ops = QWidget()
        op_layout = QHBoxLayout(ops)
        op_layout.setContentsMargins(0, 0, 0, 0)
        op_layout.setSpacing(2)
        apply_btn = QPushButton("应用")
        apply_btn.setFixedWidth(44)
        apply_btn.clicked.connect(
            lambda checked=False, n=name: self._apply_template_by_name(n),
        )
        op_layout.addWidget(apply_btn)
        if not gray:
            edit_btn = QPushButton("编辑")
            edit_btn.setFixedWidth(44)
            edit_btn.clicked.connect(
                lambda checked=False, n=name: self._edit_template_by_name(n),
            )
            op_layout.addWidget(edit_btn)
            rename_btn = QPushButton("重命名")
            rename_btn.setFixedWidth(60)
            rename_btn.clicked.connect(
                lambda checked=False, n=name: self._rename_template_by_name(n),
            )
            op_layout.addWidget(rename_btn)
            delete_btn = QPushButton("删除")
            delete_btn.setFixedWidth(44)
            delete_btn.clicked.connect(
                lambda checked=False, n=name: self._delete_template_by_name(n),
            )
            op_layout.addWidget(delete_btn)
        op_layout.addStretch()
        self._template_table.setCellWidget(row, 2, ops)

    def _selected_template_name(self) -> str:
        """返回模板表格当前行的模板名（无当前行返回空串）。"""
        row = self._template_table.currentRow()
        if row < 0:
            return ""
        item = self._template_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def _select_template_by_name(self, name: str) -> None:
        """按模板名选中模板表格行（存在时）。"""
        for r in range(self._template_table.rowCount()):
            item = self._template_table.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == name:
                self._template_table.setCurrentCell(r, 0)
                self._template_table.selectRow(r)
                return

    @_safe_slot
    def _on_template_selected(self) -> None:
        """模板表格选中变化：更新摘要提示（不自动应用，点「应用模板」生效）。"""
        name = self._selected_template_name()
        if name:
            self._status_bar.show_info(f"已选择模板：{name}，点击「应用模板」生效")

    @log_call("contacts_import.panel")
    @_safe_slot
    def _apply_template(self) -> None:
        """应用表格中选中的模板（兼容选中路径，应用成功后自动进入列映射）。"""
        name = self._selected_template_name()
        if not name:
            _dlg.QMessageBox.information(self, "提示", "请先在模板列表中选择一个模板")
            return
        self._apply_template_by_name(name)

    def _apply_template_by_name(self, name: str) -> None:
        """按模板名应用模板（未选择源文件时提示并终止）。"""
        if self._sheet_data is None:
            _dlg.QMessageBox.information(
                self, "提示", "请先选择源文件，再应用模板",
            )
            return
        if name == _DEFAULT_MAPPING_NAME:
            self._template = self._get_default_template()
            self._manual_map = {}
        else:
            manager = self._get_manager()
            template = next(
                (t for t in manager.list_templates() if t.name == name), None,
            )
            if template is None:
                return
            self._template = template
            # 优先恢复模板保存的建议映射，其余列走自动匹配
            self._manual_map = dict(template.mappings)
        self._rebuild_matches()
        self._refresh_preview()
        self._goto_step(1)  # 应用成功自动去下一步（列映射）
        get_logger("contacts_import.panel").info(
            f"模板 '{name}' 应用成功，映射列数={len(self._matches)}"
        )

    def _get_default_template(self) -> Template:
        """从内置列构建默认映射模板（同名 key 去重）。"""
        seen = set()
        columns = []
        for col in get_app_settings().builtin_columns:
            if col.key in seen:
                continue
            seen.add(col.key)
            columns.append(TemplateColumn(key=col.key, name=col.label))
        return Template(name=_DEFAULT_MAPPING_NAME, columns=columns)
