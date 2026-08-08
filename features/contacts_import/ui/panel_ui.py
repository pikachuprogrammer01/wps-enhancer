"""面板 UI 构建（拆分自 panel.py：ContactsPanelUI mixin）。

仅负责控件创建与布局，交互逻辑在各功能 mixin 与主面板中。
"""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QStackedWidget,
    QTableWidget, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

from core.settings import get_app_settings
from ui.components.file_picker import FilePicker
from ui.components.status_bar import StatusBar
from features.contacts_import.ui.base import (
    _STEP_NAMES, _VCF_FIELD_KEYS, _VCF_FIELD_LABELS,
)


class ContactsPanelUI:
    """面板控件构建：步骤条 + 状态栏 + 三个步骤页 + 底部操作栏。"""

    def _setup_ui(self) -> None:
        """构建 UI 布局：步骤指示 + 堆叠步骤页（① 数据源/② 列映射/③ 预览导出）。"""
        main_layout = QVBoxLayout(self)
        # 步骤指示条（点击可跳转，带校验）
        step_row = QHBoxLayout()
        self._step_indicators: List[QLabel] = []
        for i, name in enumerate(_STEP_NAMES):
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.mouseReleaseEvent = (
                lambda event, idx=i: self._goto_step_checked(idx)
            )
            self._step_indicators.append(label)
            step_row.addWidget(label, 1)
            if i < len(_STEP_NAMES) - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #999999;")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                step_row.addWidget(arrow)
        main_layout.addLayout(step_row)
        self._status_bar = StatusBar()
        main_layout.addWidget(self._status_bar)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_source_tab())
        self._stack.addWidget(self._build_mapping_tab())
        self._stack.addWidget(self._build_export_tab())
        main_layout.addWidget(self._stack, 1)
        main_layout.addLayout(self._build_bottom_bar())
        self._goto_step(0)

    def _build_source_tab(self) -> QWidget:
        """数据源 Tab：文件选择 + 模板选择与管理。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._build_file_group())
        layout.addWidget(self._build_template_group())
        layout.addStretch()
        return widget

    def _build_mapping_tab(self) -> QWidget:
        """列映射 Tab：映射编辑表格 + 源表内容预览（联动）。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._build_mapping_group())
        layout.addWidget(self._build_source_group())
        return widget

    def _build_export_tab(self) -> QWidget:
        """预览与导出 Tab：预览 + 警告横幅。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._build_preview_group())
        layout.addStretch()
        return widget

    def _build_file_group(self) -> QGroupBox:
        """构建文件选择 GroupBox。"""
        group = QGroupBox("文件选择")
        layout = QVBoxLayout(group)
        self._file_picker = FilePicker(
            "源文件", "表格文件 (*.xls *.xlsx *.csv)",
        )
        row = QHBoxLayout()
        row.addWidget(QLabel("Sheet"))
        self._sheet_combo = QComboBox()
        self._sheet_combo.setEnabled(False)
        row.addWidget(self._sheet_combo, 1)
        layout.addWidget(self._file_picker)
        layout.addLayout(row)
        return group

    def _build_template_group(self) -> QGroupBox:
        """构建模板 GroupBox：顶部创建按钮 + 模板表格（每行含操作按钮）。"""
        group = QGroupBox("模板")
        layout = QVBoxLayout(group)

        # 创建入口（最上方）
        create_row = QHBoxLayout()
        self._new_btn = QPushButton("新建模板")
        create_row.addWidget(self._new_btn)
        self._import_btn = QPushButton("从表头导入")
        create_row.addWidget(self._import_btn)
        create_row.addStretch()
        layout.addLayout(create_row)

        # 模板表格（首行固定默认映射项）：模板名 | 模板列 | 操作
        self._template_table = QTableWidget(0, 3)
        self._template_table.setHorizontalHeaderLabels(
            ["模板名", "模板列", "操作"],
        )
        self._template_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._template_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self._template_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed,
        )
        self._template_table.setColumnWidth(0, 160)
        self._template_table.setColumnWidth(1, 260)
        self._template_table.setColumnWidth(2, 210)
        self._template_table.verticalHeader().setVisible(False)
        layout.addWidget(self._template_table)

        # 当前模板摘要（列名 + 实际映射数）
        self._template_summary = QLabel()
        self._template_summary.setWordWrap(True)
        self._template_summary.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(self._template_summary)

        # 无模板时的提示
        self._no_template_label = QLabel("暂无模板，可新建或从表头导入")
        self._no_template_label.setStyleSheet("color: #999999;")
        layout.addWidget(self._no_template_label)
        return group

    def _build_mapping_group(self) -> QGroupBox:
        """构建映射编辑 GroupBox（模板列可编辑 | 状态 | 源列 | 示例 | 操作）。"""
        group = QGroupBox(
            "列映射（第一列可直接编辑列名/输入新增，末行点击或输入添加列）",
        )
        layout = QVBoxLayout(group)
        self._mapping_table = QTableWidget(0, 5)
        self._mapping_table.setHorizontalHeaderLabels(
            ["模板列", "匹配状态", "源列", "源列内容示例", "操作"],
        )
        # 行拖拽排序（模板列顺序）
        self._mapping_table.setDragEnabled(True)
        self._mapping_table.setAcceptDrops(True)
        self._mapping_table.setDropIndicatorShown(True)
        self._mapping_table.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove,
        )
        self._mapping_table.setDefaultDropAction(Qt.DropAction.MoveAction)
        layout.addWidget(self._mapping_table)
        return group

    def _build_source_group(self) -> QGroupBox:
        """构建源表内容预览 GroupBox（原表表头 + 前 10 行数据）。"""
        group = QGroupBox("源表内容（前 10 行，选中的源列高亮显示）")
        layout = QVBoxLayout(group)
        self._source_table = QTableWidget()
        layout.addWidget(self._source_table)
        return group

    def _build_preview_warning(self) -> QWidget:
        """构建预览面板中的警告横幅区域。"""
        widget = QWidget()
        widget.setStyleSheet("background-color: #FFEBEE;")
        widget.setVisible(False)
        layout = QVBoxLayout(widget)
        self._warning_label = QLabel()
        self._warning_label.setWordWrap(True)
        layout.addWidget(self._warning_label)
        return widget

    def _build_vcf_custom_row(self) -> QWidget:
        """构建 vcf 自定义区（前缀/后缀/时间戳开关与位置 + 导出字段，非 vcf 时整行隐藏）。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        settings = get_app_settings()
        # 第一行：前缀/后缀 + 时间戳开关与位置
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("vcf 姓名前缀"))
        self._vcf_prefix_edit = QLineEdit(settings.vcf_name_prefix)
        self._vcf_prefix_edit.setPlaceholderText("如：vcf_ / 客户-")
        self._vcf_prefix_edit.setFixedWidth(110)
        self._vcf_prefix_edit.editingFinished.connect(self._sync_vcf_settings)
        row1.addWidget(self._vcf_prefix_edit)
        row1.addWidget(QLabel("后缀"))
        self._vcf_suffix_edit = QLineEdit(settings.vcf_name_suffix)
        self._vcf_suffix_edit.setFixedWidth(110)
        self._vcf_suffix_edit.editingFinished.connect(self._sync_vcf_settings)
        row1.addWidget(self._vcf_suffix_edit)
        self._vcf_ts_check = QCheckBox("使用时间戳（年月日）")
        self._vcf_ts_check.setChecked(settings.vcf_timestamp)
        self._vcf_ts_check.toggled.connect(self._sync_vcf_settings)
        row1.addWidget(self._vcf_ts_check)
        row1.addWidget(QLabel("时间戳位置"))
        self._vcf_ts_pos_combo = QComboBox()
        self._vcf_ts_pos_combo.addItems(["姓名前", "姓名后"])
        self._vcf_ts_pos_combo.setCurrentText(
            "姓名前" if settings.vcf_timestamp_position == "prefix" else "姓名后",
        )
        self._vcf_ts_pos_combo.currentTextChanged.connect(self._sync_vcf_settings)
        row1.addWidget(self._vcf_ts_pos_combo)
        row1.addStretch()
        layout.addLayout(row1)
        # 第二行：导出字段勾选
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("导出字段"))
        self._vcf_field_checks: List[QCheckBox] = []
        for key, label in zip(_VCF_FIELD_KEYS, _VCF_FIELD_LABELS):
            check = QCheckBox(label)
            check.setChecked(key in settings.vcf_fields)
            check.toggled.connect(self._sync_vcf_settings)
            self._vcf_field_checks.append(check)
            row2.addWidget(check)
        row2.addStretch()
        layout.addLayout(row2)
        return widget

    def _build_preview_group(self) -> QGroupBox:
        """构建预览 GroupBox（上方含 vcf 自定义行，与全局设置联动）。"""
        self._preview_group = QGroupBox("预览")
        self._preview_group.setVisible(False)
        layout = QVBoxLayout(self._preview_group)
        self._summary_label = QLabel()
        layout.addWidget(self._summary_label)
        self._warning_widget = self._build_preview_warning()
        layout.addWidget(self._warning_widget)

        # vcf 自定义（仅 vcf 格式时可见）
        self._vcf_custom_row = self._build_vcf_custom_row()
        layout.addWidget(self._vcf_custom_row)

        self._preview_table = QTableWidget()
        layout.addWidget(self._preview_table)
        # 文本形式预览（csv/txt/vcf：展示导出文件的实际内容）
        self._preview_text = QPlainTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setVisible(False)
        self._preview_text.setStyleSheet(
            "font-family: Menlo, Monaco, monospace; font-size: 12px;",
        )
        layout.addWidget(self._preview_text)
        self._toggle_btn = QPushButton()
        self._toggle_btn.setVisible(False)
        layout.addWidget(self._toggle_btn)
        return self._preview_group

    def _sync_vcf_settings(self) -> None:
        """将预览页 vcf 自定义控件同步到全局设置并保存（失败不影响会话）。"""
        settings = get_app_settings()
        settings.vcf_name_prefix = self._vcf_prefix_edit.text().strip()
        settings.vcf_name_suffix = self._vcf_suffix_edit.text().strip()
        settings.vcf_timestamp = self._vcf_ts_check.isChecked()
        settings.vcf_timestamp_position = (
            "prefix" if self._vcf_ts_pos_combo.currentText() == "姓名前" else "suffix"
        )
        settings.vcf_fields = [
            key for key, check in zip(_VCF_FIELD_KEYS, self._vcf_field_checks)
            if check.isChecked()
        ]
        try:
            from core.settings import save_app_settings
            save_app_settings(settings)
        except Exception:
            pass
        self._refresh_preview()  # 刷新预览（vcf 字段/前后缀变化反映到预览）

    def _build_bottom_bar(self) -> QHBoxLayout:
        """构建底部操作栏（格式选择 + 源/导出行数对比 + 步骤导航贴近导出按钮）。"""
        row = QHBoxLayout()
        row.addWidget(QLabel("导出格式"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(["xlsx", "xls", "csv", "vcf", "txt"])
        self._format_combo.setCurrentText("vcf")  # 默认导出格式 vcf
        row.addWidget(self._format_combo)
        row.addStretch()

        # 源数据行数与导出行数对比（含表头/声明信息，便于核对）
        self._source_count_label = QLabel("源数据 - 行")
        self._source_count_label.setStyleSheet("color: #666666;")
        row.addWidget(self._source_count_label)
        self._export_count_label = QLabel("导出 - 行")
        self._export_count_label.setStyleSheet("color: #1A73E8; font-weight: bold;")
        row.addWidget(self._export_count_label)

        self._prev_btn = QPushButton("上一步")
        row.addWidget(self._prev_btn)
        self._next_btn = QPushButton("下一步")
        row.addWidget(self._next_btn)
        self._cancel_btn = QPushButton("取消")
        row.addWidget(self._cancel_btn)
        self._export_btn = QPushButton("确认导出")
        self._export_btn.setEnabled(False)
        row.addWidget(self._export_btn)
        return row
