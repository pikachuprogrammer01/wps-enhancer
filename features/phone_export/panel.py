from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.file_io.base import get_reader, get_writer
from core.exceptions import (
    WpsEnhancerError, FileReadError, ColumnNotFoundError,
    DataProcessError, FileWriteError,
)
from core.logger import get_logger
from features.phone_export.config import ColumnMapping
from features.phone_export.processor import (
    build_preview_data, build_write_request, PreviewData, ExportRow,
)
from ui.components.file_picker import FilePicker
from ui.components.status_bar import StatusBar

_PREVIEW_LIMIT = 30


class PhoneExportPanel(QWidget):
    """手机号导出功能面板。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._preview_data: Optional[PreviewData] = None
        self._file_path: str = ""
        self._all_rows_visible: bool = False
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """构建 UI 布局（纯布局代码）。"""
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._build_file_group())
        main_layout.addWidget(self._build_preview_group())
        main_layout.addWidget(self._build_bottom_bar())

    def _build_file_group(self) -> QGroupBox:
        """构建文件选择 GroupBox。"""
        group = QGroupBox("文件选择")
        layout = QVBoxLayout(group)
        self._file_picker = FilePicker("源文件")
        self._sheet_combo = QComboBox()
        self._sheet_combo.setEnabled(False)
        layout.addWidget(self._file_picker)
        layout.addWidget(self._sheet_combo)
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

    def _build_preview_table(self) -> QTableWidget:
        """构建预览表格。"""
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["姓名", "家庭手机"])
        return table

    def _build_preview_group(self) -> QGroupBox:
        """构建预览 GroupBox。"""
        self._preview_group = QGroupBox("预览")
        self._preview_group.setVisible(False)
        layout = QVBoxLayout(self._preview_group)
        self._summary_label = QLabel()
        layout.addWidget(self._summary_label)
        self._warning_widget = self._build_preview_warning()
        layout.addWidget(self._warning_widget)
        self._table = self._build_preview_table()
        layout.addWidget(self._table)
        self._toggle_btn = QPushButton()
        self._toggle_btn.setVisible(False)
        self._toggle_btn.clicked.connect(self._toggle_preview_rows)
        layout.addWidget(self._toggle_btn)
        return self._preview_group

    def _build_bottom_bar(self) -> QWidget:
        """构建底部操作栏。"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()

        self._status_bar = StatusBar()
        layout.addWidget(self._status_bar)

        self._cancel_btn = QPushButton("取消")
        layout.addWidget(self._cancel_btn)

        self._export_btn = QPushButton("确认导出")
        self._export_btn.setEnabled(False)
        layout.addWidget(self._export_btn)

        return widget

    def _connect_signals(self) -> None:
        """连接所有信号槽。"""
        self._file_picker.file_selected.connect(self._on_file_selected)
        self._sheet_combo.currentTextChanged.connect(self._on_sheet_changed)
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._cancel_btn.clicked.connect(self._reset)

    def _reset(self) -> None:
        """重置到初始状态。"""
        self._preview_data = None
        self._file_path = ""
        self._all_rows_visible = False
        self._file_picker.clear()
        self._sheet_combo.clear()
        self._sheet_combo.setEnabled(False)
        self._preview_group.setVisible(False)
        self._export_btn.setText("确认导出")
        self._export_btn.setEnabled(False)
        self._status_bar.clear()

    # ========== 数据加载 ==========

    def _on_file_selected(self, file_path: str) -> None:
        """用户选择源文件后加载 Sheet 列表。"""
        self._file_path = file_path
        self._preview_group.setVisible(False)
        self._sheet_combo.clear()
        self._sheet_combo.setEnabled(False)
        self._export_btn.setEnabled(False)
        self._status_bar.clear()

        try:
            reader = get_reader(file_path)
            sheets = reader.get_sheet_names(file_path)
            self._sheet_combo.addItems(sheets)
            self._sheet_combo.setEnabled(True)
            get_logger("phone_export.panel").info(
                f"文件 '{file_path}' 加载成功，共 {len(sheets)} 个 Sheet"
            )
        except FileReadError as e:
            self._handle_error(e)

    def _on_sheet_changed(self, sheet_name: str) -> None:
        """用户切换 Sheet 后读取数据并生成预览。"""
        if not sheet_name:
            return
        try:
            reader = get_reader(self._file_path)
            sheet_data = reader.read_sheet(self._file_path, sheet_name)
            get_logger("phone_export.panel").info(
                f"Sheet '{sheet_name}' 读取完成：表头={sheet_data.headers}，数据行数={len(sheet_data.rows)}"
            )
            preview = build_preview_data(sheet_data, ColumnMapping())
            self._display_preview(preview)
        except (FileReadError, ColumnNotFoundError, DataProcessError) as e:
            self._handle_error(e)

    # ========== 预览展示 ==========

    def _update_preview_header(self, total: int, invalid_count: int, invalid_summary: List[str]) -> None:
        """更新预览面板顶部的汇总标签和警告区域。"""
        if invalid_count > 0:
            self._summary_label.setText(
                f"共 {total} 行，其中 {invalid_count} 个手机号格式异常"
            )
            self._warning_label.setText("\n".join(invalid_summary))
            self._warning_widget.setVisible(True)
            self._export_btn.setText("忽略并继续导出")
        else:
            self._summary_label.setText(f"共 {total} 行，手机号格式均合法")
            self._warning_widget.setVisible(False)
            self._export_btn.setText("确认导出")

    def _display_preview(self, preview: PreviewData) -> None:
        """展示预览面板。"""
        self._preview_data = preview
        self._all_rows_visible = False
        total = len(preview.rows)

        self._update_preview_header(total, preview.invalid_count, preview.invalid_summary)
        self._fill_table(preview.rows[:_PREVIEW_LIMIT])

        if total > _PREVIEW_LIMIT:
            self._toggle_btn.setText(f"展开查看全部 {total} 行")
            self._toggle_btn.setVisible(True)
        else:
            self._toggle_btn.setVisible(False)

        self._preview_group.setVisible(True)
        self._export_btn.setEnabled(True)

    def _fill_table(self, rows: List[ExportRow]) -> None:
        """将 ExportRow 列表填充到表格控件。"""
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            name_item = QTableWidgetItem(row.name if row.is_name_cell else "")
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(i, 0, name_item)

            phone_item = QTableWidgetItem(row.phone)
            phone_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if not row.phone_valid:
                phone_item.setBackground(QColor("#FF0000"))
            self._table.setItem(i, 1, phone_item)

    def _toggle_preview_rows(self) -> None:
        """展开/收起全部预览行。"""
        if self._preview_data is None:
            return
        if self._all_rows_visible:
            self._fill_table(self._preview_data.rows[:_PREVIEW_LIMIT])
            self._toggle_btn.setText(
                f"展开查看全部 {len(self._preview_data.rows)} 行"
            )
            self._all_rows_visible = False
        else:
            self._fill_table(self._preview_data.rows)
            self._toggle_btn.setText("收起")
            self._all_rows_visible = True

    # ========== 导出流程 ==========

    def _on_export_clicked(self) -> None:
        """弹出保存对话框，用户确认后执行导出。"""
        src_path = Path(self._file_path)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        default_name = f"{src_path.stem}_{timestamp}{src_path.suffix}"
        default_path = str(src_path.parent / default_name)

        output_path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", default_path,
            "Excel 文件 (*.xls *.xlsx)",
        )
        if not output_path:
            return
        self._write_file(output_path)

    def _write_file(self, output_path: str) -> None:
        """执行文件写入。"""
        try:
            request = build_write_request(
                self._preview_data, ColumnMapping(), output_path,
            )
            get_writer(output_path).write_export(request)
            self._handle_success(output_path)
        except FileWriteError as e:
            self._handle_error(e)

    # ========== 错误与成功处理 ==========

    def _handle_error(self, error: WpsEnhancerError) -> None:
        """统一的错误处理：日志 + 状态栏 + 弹窗。"""
        get_logger("phone_export.panel").error(str(error))
        self._status_bar.show_error(str(error))
        QMessageBox.critical(self, "错误", str(error))

    def _handle_success(self, output_path: str) -> None:
        """统一的成功处理：日志 + 状态栏。"""
        logger = get_logger("phone_export.panel")
        msg = f"导出成功，共 {len(self._preview_data.rows)} 行，文件已保存至：{output_path}"
        logger.info(msg)
        self._status_bar.show_success(msg)
