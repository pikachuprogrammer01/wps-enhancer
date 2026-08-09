"""设置对话框新功能测试：日志导出/清空、内置列占位行双击、删除确认、保存 toast。"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.components import settings_dialog as sd


class SettingsDialogExtTest(unittest.TestCase):
    """设置对话框扩展功能。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_dialog(self):
        """构造对话框（mock get_app_settings 隔离真实配置）。"""
        from core.settings import AppSettings
        from core.template.config import default_builtin_columns
        settings = AppSettings(builtin_columns=default_builtin_columns())
        dlg = sd.SettingsDialog()
        dlg._settings = settings  # 替换为隔离实例
        return dlg

    def test_builtin_placeholder_input_creates_row(self):
        """双击占位行输入语义键 → 转为真实行并追加新占位行。"""
        dlg = self._make_dialog()
        try:
            before = dlg._builtin_table.rowCount()
            placeholder_row = before - 1
            self.assertTrue(dlg._is_placeholder_row(placeholder_row))
            # 模拟在占位行输入 email
            item = dlg._builtin_table.item(placeholder_row, 0)
            item.setText("email")
            self.assertFalse(dlg._is_placeholder_row(placeholder_row))
            self.assertEqual(
                dlg._builtin_table.item(placeholder_row, 0).text(), "email",
            )
            self.assertEqual(dlg._builtin_table.rowCount(), before + 1)
            self.assertTrue(dlg._is_placeholder_row(dlg._builtin_table.rowCount() - 1))
            # 收集时占位行被跳过、email 行被收集
            keys = [c.key for c in dlg._collect_builtin_columns()]
            self.assertIn("email", keys)
            self.assertNotIn(sd.SettingsDialog._PLACEHOLDER_TEXT, keys)
        finally:
            dlg.close()

    def test_builtin_delete_requires_confirm(self):
        """内置列删除需二次确认：拒绝时行保留，确认时行删除。"""
        dlg = self._make_dialog()
        try:
            rows = dlg._builtin_table.rowCount()
            with mock.patch.object(
                QMessageBox, "question",
                return_value=QMessageBox.StandardButton.No,
            ):
                dlg._builtin_table.setCurrentCell(0, 0)
                dlg._on_delete_builtin()
            self.assertEqual(dlg._builtin_table.rowCount(), rows)
            with mock.patch.object(
                QMessageBox, "question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                dlg._on_delete_builtin()
            self.assertEqual(dlg._builtin_table.rowCount(), rows - 1)
        finally:
            dlg.close()

    def test_export_logs_copies_file(self):
        """导出日志：复制当天日志到用户选择位置，成功 toast。"""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            log_dir.mkdir()
            log_file = log_dir / "wps_enhancer_20260809.log"
            log_file.write_text("test log", encoding="utf-8")
            dest = Path(tmp) / "out.log"
            dlg = self._make_dialog()
            try:
                with mock.patch("core.app_paths.get_logs_dir", return_value=log_dir), \
                        mock.patch.object(
                            QtWidgets.QFileDialog, "getSaveFileName",
                            return_value=(str(dest), ""),
                        ), mock.patch.object(sd, "show_toast") as toast:
                    dlg._on_export_logs()
                self.assertEqual(dest.read_text(encoding="utf-8"), "test log")
                self.assertEqual(toast.call_args[0][1], "日志已导出")
            finally:
                dlg.close()

    def test_export_logs_none_available(self):
        """无日志时导出给出提示，不弹文件对话框。"""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "empty"
            log_dir.mkdir()
            dlg = self._make_dialog()
            try:
                with mock.patch("core.app_paths.get_logs_dir", return_value=log_dir), \
                        mock.patch.object(sd, "show_toast") as toast, \
                        mock.patch.object(QtWidgets.QFileDialog, "getSaveFileName") as fd:
                    dlg._on_export_logs()
                self.assertEqual(toast.call_args[0][1], "暂无日志文件")
                fd.assert_not_called()
            finally:
                dlg.close()

    def test_clear_logs_truncates_after_confirm(self):
        """清空日志：确认后内容清空（文件保留，供运行中 handler 继续写）。"""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            log_dir.mkdir()
            f1 = log_dir / "wps_enhancer_20260808.log"
            f2 = log_dir / "wps_enhancer_20260809.log"
            f1.write_text("old", encoding="utf-8")
            f2.write_text("today", encoding="utf-8")
            dlg = self._make_dialog()
            try:
                with mock.patch("core.app_paths.get_logs_dir", return_value=log_dir), \
                        mock.patch.object(
                            QMessageBox, "question",
                            return_value=QMessageBox.StandardButton.Yes,
                        ), mock.patch.object(sd, "show_toast") as toast:
                    dlg._on_clear_logs()
                self.assertEqual(f1.read_text(encoding="utf-8"), "")
                self.assertEqual(f2.read_text(encoding="utf-8"), "")
                self.assertEqual(toast.call_args[0][1], "日志已清空")
            finally:
                dlg.close()

    def test_clear_logs_cancel_keeps_files(self):
        """清空日志拒绝确认时文件保持不变。"""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            log_dir.mkdir()
            f1 = log_dir / "wps_enhancer_20260809.log"
            f1.write_text("keep", encoding="utf-8")
            dlg = self._make_dialog()
            try:
                with mock.patch("core.app_paths.get_logs_dir", return_value=log_dir), \
                        mock.patch.object(
                            QMessageBox, "question",
                            return_value=QMessageBox.StandardButton.No,
                        ):
                    dlg._on_clear_logs()
                self.assertEqual(f1.read_text(encoding="utf-8"), "keep")
            finally:
                dlg.close()

    def test_save_shows_toast(self):
        """保存成功后弹出轻提示（toast）。"""
        dlg = self._make_dialog()
        try:
            with mock.patch.object(sd, "show_toast") as toast, \
                    mock.patch.object(dlg, "accept") as accept:
                dlg._on_save()
            toast.assert_called_once()
            self.assertEqual(toast.call_args[0][1], "保存成功")
            accept.assert_called_once()
        finally:
            dlg.close()


class ToastTest(unittest.TestCase):
    """轻提示组件（offscreen 下不抛异常且能调度销毁）。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_show_toast_creates_and_schedules(self):
        from ui.components.toast import show_toast
        parent = QtWidgets.QWidget()
        parent.resize(400, 300)
        try:
            show_toast(parent, "保存成功")
            self.app.processEvents()
            # 子控件存在（滑入动画进行中）
            self.assertGreater(len(parent.findChildren(QtWidgets.QLabel)), 0)
        finally:
            parent.close()


if __name__ == "__main__":
    unittest.main()
