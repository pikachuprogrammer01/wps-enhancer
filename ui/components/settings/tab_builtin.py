"""内置列 tab（双击单元格增删改查，与模板表格交互一致）。"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView,
)

from core.template.config import BuiltinColumn
from ui.components import toast

_PLACEHOLDER_TEXT = "双击输入语义键，添加内置列"


class BuiltinTabMixin:
    """内置列管理分组（mixin：依赖宿主 SettingsDialog）。"""

    def _build_builtin_tab(self) -> QWidget:
        """内置列管理（增删改查）。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_builtin_group())
        layout.addStretch()
        return page

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
        item = QTableWidgetItem(_PLACEHOLDER_TEXT)
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
        if not text or text == _PLACEHOLDER_TEXT:
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
            toast.show_toast(self, "请先选择要删除的内置列", success=False)
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
