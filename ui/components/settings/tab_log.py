"""日志 tab（详细开关 / 导出 / 清空 / 保留天数与自动清理）。"""

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from core.logger import get_logger
from ui.components import toast


class LogTabMixin:
    """日志设置分组（mixin：依赖宿主 SettingsDialog）。"""

    def _build_log_tab(self) -> QWidget:
        """日志分组。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_log_group())
        layout.addStretch()
        return page

    def _build_log_group(self) -> QGroupBox:
        """日志分组（详细开关 + 导出/清空 + 保留天数自动清理）。"""
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
        idx = self._retain_combo.findData(self._settings.log_retain_days)
        self._retain_combo.setCurrentIndex(idx if idx >= 0 else 1)
        cleanup_row.addWidget(self._retain_combo)
        cleanup_btn = QPushButton("清理过期日志")
        cleanup_btn.clicked.connect(self._on_cleanup_logs)
        cleanup_row.addWidget(cleanup_btn)
        cleanup_row.addStretch()
        layout.addLayout(cleanup_row)
        self._auto_clean_check = QCheckBox(
            "启动时自动清理过期日志（按上面保留天数）",
        )
        self._auto_clean_check.setChecked(self._settings.log_auto_clean)
        layout.addWidget(self._auto_clean_check)
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
            toast.show_toast(self.parent() or self, f"清理失败：{e}", success=False)
            return
        if failed:
            toast.show_toast(
                self.parent() or self,
                f"清理完成，{failed} 个文件删除失败（权限或占用）",
                success=False,
            )
        elif deleted:
            toast.show_toast(self.parent() or self, f"已清理 {deleted} 个过期日志")
        else:
            toast.show_toast(self.parent() or self, "没有过期日志", success=False)

    def _on_export_logs(self) -> None:
        """导出当天日志文件到用户选择的位置。"""
        import shutil
        from datetime import datetime as _dt
        from PyQt6.QtWidgets import QFileDialog
        from core.app_paths import get_logs_dir
        log_dir = get_logs_dir()
        log_file = log_dir / f"wps_enhancer_{_dt.now().strftime('%Y%m%d')}.log"
        if not log_file.exists():
            toast.show_toast(self, "暂无日志文件", success=False)
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
            toast.show_toast(self, f"导出失败：{e}", success=False)
            return
        toast.show_toast(self, "日志已导出")

    def _on_clear_logs(self) -> None:
        """清空全部日志记录（二次确认；当天日志文件保留但内容清空）。"""
        from core.app_paths import get_logs_dir
        log_dir = get_logs_dir()
        logs = sorted(log_dir.glob("wps_enhancer_*.log"))
        if not logs:
            toast.show_toast(self, "暂无日志记录", success=False)
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
        toast.show_toast(self, "日志已清空")
