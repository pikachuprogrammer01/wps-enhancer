"""Excel 批量导入通讯录：主面板（流程编排）。

职责：步骤导航、数据加载、文件与模板/映射/预览/导出各模块的组装。
- ui/base.py：常量、_safe_slot、弹窗共享引用
- ui/panel_ui.py：控件构建；ui/template_table.py：模板表格；
  ui/mapping_table.py：列映射；ui/preview.py：预览；
  ui/template_actions.py：模板管理；ui/export_actions.py：导出
- processor.py：数据转换纯逻辑
"""

from typing import List, Optional
from pathlib import Path

from PyQt6.QtWidgets import QStackedWidget, QWidget
from PyQt6.QtCore import pyqtSignal

from features.contacts_import.ui import base as _dlg
from core.app_paths import get_templates_dir
from core.exceptions import WpsEnhancerError
from core.file_io.base import get_reader
from core.logger import get_logger, log_call
from core.settings import get_app_settings
from core.template import Template, TemplateManager, match_columns
from features.contacts_import.ui.base import _STEP_NAMES
from features.contacts_import.ui.panel_ui import ContactsPanelUI
from features.contacts_import.ui.base import _safe_slot
from features.contacts_import.ui.template_table import TemplateTableMixin
from features.contacts_import.ui.mapping_table import MappingTableMixin
from features.contacts_import.ui.preview import PreviewMixin
from features.contacts_import.ui.template_actions import TemplateActionsMixin
from features.contacts_import.ui.export_actions import ExportActionsMixin


class ContactsImportPanel(
    ContactsPanelUI, TemplateTableMixin, MappingTableMixin,
    PreviewMixin, TemplateActionsMixin, ExportActionsMixin, QWidget,
):
    """通讯录导入主面板：三步流程（数据源 → 列映射 → 预览与导出）。"""

    back_home_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._file_path: str = ""
        self._sheet_data = None
        self._template: Optional[Template] = None
        self._matches = None
        self._manual_map: dict = {}
        self._preview = None
        self._all_rows_visible: bool = False
        self._setup_ui()
        self._connect_signals()

    # ========== 步骤导航 ==========

    def _goto_step(self, index: int) -> None:
        """切换步骤页并更新步骤指示与导航按钮。"""
        self._stack.setCurrentIndex(index)
        self._update_step_indicators(index)
        self._prev_btn.setEnabled(index > 0)
        self._next_btn.setEnabled(index < 2)

    def _update_step_indicators(self, current: int) -> None:
        """更新步骤指示条：已完成绿色✓、当前蓝色高亮、未完成灰色。"""
        for i, label in enumerate(self._step_indicators):
            if i == current:
                label.setStyleSheet(
                    "background: #4A90D9; color: white; border-radius: 6px;"
                    " padding: 6px 0; font-weight: bold;"
                )
                label.setText(f"▸ {_STEP_NAMES[i]}")
            elif i < current:
                label.setStyleSheet(
                    "background: #E8F5E9; color: #2E7D32; border-radius: 6px;"
                    " padding: 6px 0;"
                )
                label.setText(f"✓ {_STEP_NAMES[i]}")
            else:
                label.setStyleSheet(
                    "background: #F0F0F0; color: #999999; border-radius: 6px;"
                    " padding: 6px 0;"
                )
                label.setText(_STEP_NAMES[i])

    def _on_next(self) -> None:
        """下一步：校验当前步骤条件通过后切换。"""
        self._goto_step_checked(self._stack.currentIndex() + 1)

    def _goto_step_checked(self, target: int) -> None:
        """跳转到目标步骤（向后跳转时逐级校验前置条件）。"""
        current = self._stack.currentIndex()
        target = max(0, min(target, len(_STEP_NAMES) - 1))
        if target <= current:
            self._goto_step(target)
            return
        for step in range(current, target):
            if not self._step_ready(step):
                self._show_step_blocked(step)
                return
        # 模板未应用时兜底：使用默认映射（用户可跳过模板选择直接继续）
        if self._template is None and self._sheet_data is not None:
            self._template = self._get_default_template()
            self._manual_map = {}
            self._rebuild_matches()
            self._refresh_preview()
        self._goto_step(target)

    def _step_ready(self, step: int) -> bool:
        """判断第 step 步是否满足进入下一步的条件（0=数据源、1=列映射）。"""
        if step == 0:
            # 仅要求源数据就绪；模板未应用时跳转前自动兜底默认映射
            return self._sheet_data is not None
        if step == 1:
            return bool(
                self._matches and any(m.source_col for m in self._matches)
            )
        return True

    def _show_step_blocked(self, step: int) -> None:
        """提示当前步骤未完成，阻止跳转。"""
        if step == 0:
            _dlg.QMessageBox.information(self, "提示", "请先选择源文件和 Sheet")
        elif step == 1:
            _dlg.QMessageBox.information(self, "提示", "请至少完成一个列映射")

    def _on_prev(self) -> None:
        """上一步。"""
        self._goto_step(self._stack.currentIndex() - 1)

    def _connect_signals(self) -> None:
        """连接所有信号槽。

        clicked 信号在 PyQt6 是双重载（无参/带 bool），装饰后的槽签名不明确会
        被 PyQt 选择带参重载而报错，因此按钮统一用 lambda 明确无参。
        """
        self._file_picker.file_selected.connect(self._on_file_selected)
        self._file_picker.editing_finished.connect(self._on_path_entered)
        self._sheet_combo.currentTextChanged.connect(self._on_sheet_changed)
        self._template_table.itemSelectionChanged.connect(
            self._on_template_selected,
        )
        self._new_btn.clicked.connect(lambda: self._on_new_template())
        self._import_btn.clicked.connect(lambda: self._on_import_template())
        self._export_btn.clicked.connect(lambda: self._on_export_clicked())
        self._cancel_btn.clicked.connect(lambda: self._reset())
        self._prev_btn.clicked.connect(self._on_prev)
        self._next_btn.clicked.connect(self._on_next)
        self._toggle_btn.clicked.connect(lambda: self._toggle_preview_rows())
        self._mapping_table.itemChanged.connect(self._on_column_name_edited)
        self._mapping_table.model().rowsMoved.connect(self._on_rows_moved)
        self._template_table.itemChanged.connect(self._on_template_cell_edited)
        self._format_combo.currentTextChanged.connect(self._on_format_changed)

    def _get_manager(self) -> TemplateManager:
        """返回当前设置下的模板管理器（每次重新读取内置列）。"""
        return TemplateManager(get_templates_dir(), get_app_settings().builtin_columns)

    # ========== 数据加载 ==========

    @_safe_slot
    def _on_path_entered(self) -> None:
        """手动输入文件路径后：校验后缀与存在性，合法则自动加载。"""
        path = self._file_picker.get_file_path().strip()
        if not path:
            return
        if path == self._file_path:
            return  # 路径未变化：避免失焦/回车重复触发重新加载链
        suffix = Path(path).suffix.lower().lstrip(".")
        if suffix not in ("xls", "xlsx", "csv"):
            _dlg.QMessageBox.warning(
                self, "格式错误",
                f"不支持的文件格式：{suffix or '无后缀'}，"
                "请选择 .xls / .xlsx / .csv 文件",
            )
            self._status_bar.show_error("文件格式不支持，无法继续下一步")
            return
        if not Path(path).exists():
            _dlg.QMessageBox.warning(self, "格式错误", f"文件不存在：{path}")
            return
        self._on_file_selected(path)

    @log_call("contacts_import.panel")
    @_safe_slot
    def _on_file_selected(self, file_path: str) -> None:
        """用户选择源文件后加载 Sheet 列表。"""
        self._file_path = file_path
        self._reset_data_state()
        try:
            reader = get_reader(file_path)
            sheets = reader.get_sheet_names(file_path)
            self._sheet_combo.addItems(sheets)
            self._sheet_combo.setEnabled(True)
            get_logger("contacts_import.panel").info(
                f"文件 '{file_path}' 加载成功，共 {len(sheets)} 个 Sheet"
            )
        except WpsEnhancerError as e:
            self._handle_error(e)

    def _reset_data_state(self) -> None:
        """重置数据相关状态（保留文件路径）。"""
        self._sheet_data = None
        self._template = None
        self._matches = None
        self._manual_map = {}
        self._preview = None
        self._all_rows_visible = False
        self._sheet_combo.clear()
        self._sheet_combo.setEnabled(False)
        self._template_table.setRowCount(0)
        self._template_table.setEnabled(False)
        self._mapping_table.setRowCount(0)
        self._source_table.setRowCount(0)
        self._source_table.setColumnCount(0)
        self._preview_group.setVisible(False)
        self._export_btn.setEnabled(False)
        self._status_bar.clear()
        self._source_count_label.setText("源数据 - 行")
        self._export_count_label.setText("导出 - 行")
        self._goto_step(0)

    @_safe_slot
    def _on_sheet_changed(self, sheet_name: str) -> None:
        """用户切换 Sheet 后读取数据，并加载模板列表。"""
        if not sheet_name:
            return
        settings = get_app_settings()
        try:
            reader = get_reader(self._file_path)
            data = reader.read_sheet(
                self._file_path, sheet_name,
                skip_declaration=settings.declaration_detect,
                declaration_keywords=list(settings.declaration_keywords),
            )
            self._sheet_data = data
            self._fill_source_table()
            get_logger("contacts_import.panel").info(
                f"Sheet '{sheet_name}' 读取完成：表头={data.headers}，"
                f"数据行数={len(data.rows)}"
            )
            if data.declaration_skipped:
                get_logger("contacts_import.panel").warning(
                    "已检测到并跳过导出声明行"
                )
                self._status_bar.show_warning("已检测到并跳过导出声明行")
            elif settings.declaration_detect:
                self._status_bar.show_info("声明检测已开启")
            self._reload_templates()
            self._auto_template_decision(data.headers)
            skip_info = "（跳过声明 1 行）" if data.declaration_skipped else ""
            self._source_count_label.setText(
                f"源数据 {len(data.rows) + 1} 行{skip_info}",  # +1 表头，与文件行数可核对
            )
        except WpsEnhancerError as e:
            self._handle_error(e)

    def _auto_template_decision(self, headers: List[str]) -> None:
        """选文件后模板决策：有模板能匹配 → 等待用户选择应用；否则自动默认映射进下一步。"""
        templates = self._get_manager().list_templates()
        matching = [
            t for t in templates if self._template_matches_headers(t, headers)
        ]
        if matching:
            # 能匹配：停在数据源步骤，用户可应用模板或直接下一步（默认映射兜底）
            self._template = None
            self._matches = None
            self._preview = None
            self._status_bar.show_info(
                f"检测到 {len(matching)} 个模板可匹配：点击行内「应用」应用模板，"
                "或直接「下一步」使用默认映射",
            )
            self._goto_step(0)
        else:
            # 匹配不上（或无模板）：自动使用默认映射并进入列映射
            self._template = self._get_default_template()
            self._manual_map = {}
            self._rebuild_matches()
            self._refresh_preview()
            self._status_bar.show_info("未检测到匹配模板，已使用内置列默认映射")
            self._goto_step(1)

    def _template_matches_headers(
        self, template: Template, headers: List[str],
    ) -> bool:
        """判断模板是否能与源表头匹配（至少一列有映射建议或自动匹配成功）。"""
        settings = get_app_settings()
        matches = match_columns(
            headers, template, settings.builtin_columns, dict(template.mappings),
        )
        return any(m.source_col for m in matches)

    # ========== 重置 ==========

    @_safe_slot
    def _reset(self) -> None:
        """重置到初始状态。"""
        self._file_path = ""
        self._file_picker.clear()
        self._reset_data_state()
        self._template_table.setRowCount(0)
        self._template_table.setEnabled(False)
