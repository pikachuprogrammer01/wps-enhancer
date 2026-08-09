"""卸载功能测试：清理项框架 / 逐项执行 / UI 确认流程。"""

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.uninstall import (
    UninstallItem, remove_item, uninstall_app, uninstall_items,
)


class UninstallItemsTest(unittest.TestCase):
    """清理项框架：四项齐全、risky 标记、key 唯一。"""

    def test_items_defined(self):
        items = uninstall_items()
        keys = [i.key for i in items]
        self.assertEqual(keys, ["app", "data", "logs", "downloads"])
        self.assertEqual(len(set(keys)), len(keys))  # key 唯一

    def test_data_is_risky_and_unchecked(self):
        data = next(i for i in uninstall_items() if i.key == "data")
        self.assertTrue(data.risky)
        self.assertFalse(data.default_checked)  # 用户数据默认不勾

    def test_app_not_risky(self):
        app = next(i for i in uninstall_items() if i.key == "app")
        self.assertFalse(app.risky)


class RemoveItemTest(unittest.TestCase):
    """单项删除：目录/文件/下载包清理/不存在视为成功。"""

    def test_remove_dir(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "data"
            target.mkdir()
            (target / "settings.json").write_text("{}", encoding="utf-8")
            item = UninstallItem(
                key="data", label="x",
                resolve=lambda: target, risky=True,
            )
            self.assertIsNone(remove_item(item))
        self.assertFalse(target.exists())

    def test_remove_file(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "app.exe"
            target.write_bytes(b"x")
            item = UninstallItem(key="app", label="x", resolve=lambda: target)
            self.assertIsNone(remove_item(item))
        self.assertFalse(target.exists())

    def test_downloads_only_own_zips(self):
        with TemporaryDirectory() as tmp:
            own = Path(tmp) / "WPS增强工具_v1.1.0.zip"
            other = Path(tmp) / "other.zip"
            own.write_bytes(b"a")
            other.write_bytes(b"b")
            item = UninstallItem(key="downloads", label="x",
                                 resolve=lambda: Path(tmp))
            self.assertIsNone(remove_item(item))
            self.assertFalse(own.exists())
            self.assertTrue(other.exists())  # 其他文件不受影响

    def test_missing_target_is_success(self):
        item = UninstallItem(key="app", label="x",
                             resolve=lambda: Path("/nonexistent/nope"))
        self.assertIsNone(remove_item(item))

    def test_remove_failure_reported(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "data"
            target.mkdir()
            item = UninstallItem(key="data", label="数据", resolve=lambda: target)
            with mock.patch("core.uninstall.shutil.rmtree",
                            side_effect=PermissionError("denied")):
                err = remove_item(item)
            # 退出 patch 后真实清理（mock 期间目录未被删除）
            import shutil
            shutil.rmtree(target, ignore_errors=True)
        self.assertIsNotNone(err)
        self.assertIn("数据", err)


class UninstallAppTest(unittest.TestCase):
    """逐项执行：单项失败不中断后续项。"""

    def test_all_success(self):
        with TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            items = [
                UninstallItem(key="app", label="a", resolve=lambda: None),
                UninstallItem(key="logs", label="b", resolve=lambda: logs),
            ]
            with mock.patch("core.uninstall.uninstall_items", return_value=items):
                results = uninstall_app(["app", "logs"])
        self.assertEqual(results, [("app", None), ("logs", None)])

    def test_failure_does_not_stop_next(self):
        def boom():
            raise PermissionError("denied")
        items = [
            UninstallItem(key="app", label="本体", resolve=boom),
            UninstallItem(key="logs", label="日志",
                          resolve=lambda: Path("/nonexistent/nope")),
        ]
        with mock.patch("core.uninstall.uninstall_items", return_value=items):
            results = uninstall_app(["app", "logs"])
        self.assertIsNotNone(results[0][1])  # 第一项失败有原因
        self.assertIsNone(results[1][1])     # 第二项仍执行成功

    def test_unknown_key_reported(self):
        with mock.patch("core.uninstall.uninstall_items", return_value=[]):
            results = uninstall_app(["nope"])
        self.assertIn("未知清理项", results[0][1])


class UninstallUiTest(unittest.TestCase):
    """设置页卸载流程：确认框与结果反馈。"""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_confirm_yes_runs_uninstall(self):
        from PyQt6.QtWidgets import QDialog, QMessageBox
        from ui.components import settings_dialog as sd
        from ui.components.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        try:
            with mock.patch.object(
                QDialog, "exec", return_value=QDialog.DialogCode.Accepted,
            ), mock.patch.object(
                QMessageBox, "question",
                return_value=QMessageBox.StandardButton.Yes,
            ), mock.patch(
                "core.uninstall.uninstall_app", return_value=[("app", None)],
            ) as un, mock.patch.object(sd, "show_toast") as toast:
                dlg._on_uninstall()
            un.assert_called_once()
            self.assertTrue(toast.called)
        finally:
            dlg.close()

    def test_confirm_no_aborts(self):
        from PyQt6.QtWidgets import QDialog, QMessageBox
        from ui.components import settings_dialog as sd
        from ui.components.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        try:
            with mock.patch.object(
                QDialog, "exec", return_value=QDialog.DialogCode.Accepted,
            ), mock.patch.object(
                QMessageBox, "question",
                return_value=QMessageBox.StandardButton.No,
            ), mock.patch("core.uninstall.uninstall_app") as un:
                dlg._on_uninstall()
            un.assert_not_called()
        finally:
            dlg.close()
