"""更新检查与下载引导的 UI 流程（后台线程 + 主线程弹窗）。

纯逻辑在 core/updater.py；本模块负责：检查 → 发现新版本弹窗 →
下载 zip 到下载目录 → 替换指引。自动检查（启动时）失败静默，
手动检查（设置页）失败弹窗提示。
"""

import threading
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox, QWidget

from core.logger import get_logger
from core.updater import (
    ReleaseInfo, UpdaterError, check_latest_release, compare_versions,
    download_file,
)
from core.version import APP_VERSION

_REPLACE_GUIDE = (
    "替换方法：\n"
    "1. 完全退出 WPS 增强工具\n"
    "2. 解压 zip，把新的 WPS增强工具.app 拖到「应用程序」覆盖旧版\n"
    "3. 若提示「无法验证开发者」，请右键点按 App → 打开\n"
)


def check_update_now(parent: QWidget, silent_on_failure: bool) -> None:
    """后台检查更新并处理结果（立即返回，不阻塞 UI）。"""
    def worker() -> None:
        try:
            result: tuple = ("ok", check_latest_release())
        except UpdaterError as e:
            get_logger("ui.update_flow").warning(f"检查更新失败：{e}")
            result = ("error", str(e))
        QTimer.singleShot(0, lambda: _handle_result(parent, result, silent_on_failure))

    threading.Thread(target=worker, daemon=True).start()


def _handle_result(parent: QWidget, result: tuple, silent: bool) -> None:
    """处理检查结果：无更新提示/有新版本询问下载。"""
    status, payload = result
    if status == "error":
        if not silent:
            QMessageBox.warning(parent, "检查更新失败", payload)
        return
    info: ReleaseInfo = payload
    if compare_versions(APP_VERSION, info.tag_name) >= 0:
        if not silent:
            QMessageBox.information(
                parent, "检查更新", f"当前已是最新版本 v{APP_VERSION}",
            )
        return
    answer = QMessageBox.question(
        parent, "发现新版本",
        f"发现新版本 {info.tag_name}（当前 v{APP_VERSION}）\n"
        f"发布时间：{info.published_at[:10]}\n\n是否下载更新包？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    _start_download(parent, info)


def _start_download(parent: QWidget, info: ReleaseInfo) -> None:
    """后台下载更新包到下载目录。"""
    if not info.zip_url:
        QMessageBox.information(
            parent, "更新",
            "该版本未提供更新包（zip），请到 Release 页面手动下载：\n"
            f"{info.html_url}",
        )
        return
    dest = Path.home() / "Downloads" / f"WPS增强工具_{info.tag_name}.zip"

    def worker() -> None:
        try:
            download_file(info.zip_url, dest)
            result: tuple = ("ok", str(dest))
        except UpdaterError as e:
            get_logger("ui.update_flow").warning(f"下载更新包失败：{e}")
            result = ("error", str(e))
        QTimer.singleShot(
            0, lambda: _handle_download_done(parent, result),
        )

    threading.Thread(target=worker, daemon=True).start()


def _handle_download_done(parent: QWidget, result: tuple) -> None:
    """下载完成提示替换指引。"""
    status, payload = result
    if status == "error":
        QMessageBox.warning(parent, "下载失败", payload)
        return
    QMessageBox.information(
        parent, "更新包已下载",
        f"更新包已保存到：\n{payload}\n\n{_REPLACE_GUIDE}",
    )
