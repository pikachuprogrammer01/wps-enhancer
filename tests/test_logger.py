"""日志系统测试：敏感信息脱敏、分级记录、过期日志清理。"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent.parent))


class LoggerMaskTest(unittest.TestCase):
    """敏感信息内容级脱敏。"""

    def test_summarize_masks_phone(self):
        from core.logger import _summarize
        self.assertEqual(
            _summarize("联系人：13812345678", 200),
            "联系人：138****5678",
        )

    def test_summarize_masks_phone_in_plain_text(self):
        from core.logger import _summarize
        out = _summarize("13812345678", 200)
        self.assertNotIn("1234", out)
        self.assertIn("****", out)

    def test_format_args_masks_kwargs_keys(self):
        from core.logger import _format_args
        out = _format_args(
            ("13812345678",), {"token": "secret-abc"},
            mask_keys={"token"}, max_arg_len=200,
        )
        self.assertIn("token=***", out)
        self.assertIn("138****5678", out)  # 位置参数内容级脱敏


class CleanupLogsTest(unittest.TestCase):
    """过期日志清理（按保留天数）。"""

    def _make_log_dir(self):
        tmp = tempfile.mkdtemp()
        log_dir = Path(tmp) / "logs"
        log_dir.mkdir()
        old = log_dir / "wps_enhancer_20260101.log"
        old.write_text("old", encoding="utf-8")
        os.utime(old, (time.time() - 40 * 86400,) * 2)  # 40 天前
        fresh = log_dir / "wps_enhancer_20260809.log"
        fresh.write_text("fresh", encoding="utf-8")
        os.utime(fresh, (time.time() - 3600,) * 2)  # 1 小时前
        return log_dir, old, fresh

    def test_cleanup_deletes_only_expired(self):
        from core.logger import cleanup_logs
        log_dir, old, fresh = self._make_log_dir()
        with mock.patch("core.logger.get_logs_dir", return_value=log_dir):
            deleted, failed = cleanup_logs(retain_days=30)
        self.assertEqual((deleted, failed), (1, 0))
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())  # 当天日志保留

    def test_cleanup_no_expired(self):
        from core.logger import cleanup_logs
        log_dir, old, fresh = self._make_log_dir()
        with mock.patch("core.logger.get_logs_dir", return_value=log_dir):
            deleted, failed = cleanup_logs(retain_days=365)
        self.assertEqual((deleted, failed), (0, 0))
        self.assertTrue(old.exists())

    def test_cleanup_failure_reported(self):
        from core.logger import cleanup_logs
        log_dir, old, fresh = self._make_log_dir()
        with mock.patch("core.logger.get_logs_dir", return_value=log_dir), \
                mock.patch("pathlib.Path.unlink", side_effect=OSError("permission")):
            deleted, failed = cleanup_logs(retain_days=30)
        self.assertEqual(failed, 1)  # 删除失败被计入且不中断
        self.assertTrue(old.exists())


class CleanupUiTest(unittest.TestCase):
    """设置页清理按钮流程（确认/取消/提示）。"""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_cleanup_cancel_keeps_logs(self):
        from PyQt6.QtWidgets import QMessageBox
        from ui.components.settings import dialog as sd
        dlg = sd.SettingsDialog()
        try:
            with mock.patch.object(
                QMessageBox, "question",
                return_value=QMessageBox.StandardButton.No,
            ), mock.patch("core.logger.cleanup_logs") as cleanup:
                dlg._on_cleanup_logs()
            cleanup.assert_not_called()
        finally:
            dlg.close()

    def test_cleanup_confirm_toast(self):
        from PyQt6.QtWidgets import QMessageBox
        from ui.components.settings import dialog as sd
        dlg = sd.SettingsDialog()
        try:
            with mock.patch.object(
                QMessageBox, "question",
                return_value=QMessageBox.StandardButton.Yes,
            ), mock.patch("core.logger.cleanup_logs", return_value=(3, 0)), \
                    mock.patch("ui.components.toast.show_toast") as toast:
                dlg._on_cleanup_logs()
            self.assertEqual(toast.call_args[0][1], "已清理 3 个过期日志")
        finally:
            dlg.close()

    def test_cleanup_partial_failure_toast(self):
        from PyQt6.QtWidgets import QMessageBox
        from ui.components.settings import dialog as sd
        dlg = sd.SettingsDialog()
        try:
            with mock.patch.object(
                QMessageBox, "question",
                return_value=QMessageBox.StandardButton.Yes,
            ), mock.patch("core.logger.cleanup_logs", return_value=(1, 2)), \
                    mock.patch("ui.components.toast.show_toast") as toast:
                dlg._on_cleanup_logs()
            self.assertIn("2 个文件删除失败", toast.call_args[0][1])
            self.assertFalse(toast.call_args.kwargs["success"])  # 失败提示
        finally:
            dlg.close()


if __name__ == "__main__":
    unittest.main()


class CleanupRotatedTest(unittest.TestCase):
    """轮转文件（.log.日期 后缀）也能被自动清理（glob 匹配回归）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._log_dir = Path(self._tmp.name)
        patcher = mock.patch("core.logger.get_logs_dir", return_value=self._log_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_rotated_file_deleted_when_expired(self):
        from core.logger import cleanup_logs
        rotated = self._log_dir / "wps_enhancer_20260101.log.2026-01-02"
        rotated.write_text("old", encoding="utf-8")
        os.utime(rotated, (1, 1))  # 过期
        deleted, failed = cleanup_logs(retain_days=30)
        self.assertEqual((deleted, failed), (1, 0))
        self.assertFalse(rotated.exists())

    def test_rotated_file_kept_when_recent(self):
        from core.logger import cleanup_logs
        rotated = self._log_dir / "wps_enhancer_20260809.log.2026-08-09"
        rotated.write_text("recent", encoding="utf-8")
        deleted, failed = cleanup_logs(retain_days=30)
        self.assertEqual(deleted, 0)
        self.assertTrue(rotated.exists())
