"""更新检查与下载引导的 UI 流程（后台线程 + 主线程弹窗）。

纯逻辑在 core/updater.py；本模块负责：检查 → 发现新版本弹窗 →
下载 zip 到下载目录 → 替换指引。自动检查（启动时）失败静默，
手动检查（设置页）失败弹窗提示。
"""

import threading
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QWidget

from core.logger import get_logger
from core.updater import (
    ReleaseInfo, UpdaterError, check_latest_release, compare_versions,
    download_file, verify_zip_integrity,
)
from core.version import APP_VERSION

_REPLACE_GUIDE_MAC = (
    "替换方法：\n"
    "1. 完全退出 WPS 增强工具\n"
    "2. 解压 zip，把新的 WPS增强工具.app 拖到「{install_dir}」覆盖旧版\n"
    "3. 若提示「无法验证开发者」，请右键点按 App → 打开\n"
)
# 持有运行中的 QThread 引用，防止 Python GC 析构运行中线程
# （Qt 不持有 QThread，局部引用随 check_update_now 返回即失效）。
_ACTIVE_THREADS: list = []


_REPLACE_GUIDE_WIN = (
    "替换方法：\n"
    "1. 完全退出 WPS 增强工具\n"
    "2. 解压 zip，用其中的文件覆盖安装目录（{install_dir}）\n"
    "3. 若出现 SmartScreen 提示，点「更多信息」→「仍要运行」\n"
)


def _replace_guide() -> str:
    """按当前平台返回更新包替换指引（安装目录从设置读取，不写死）。"""
    install_dir = _resolve_install_dir()
    import sys
    template = _REPLACE_GUIDE_WIN if sys.platform == "win32" else _REPLACE_GUIDE_MAC
    return template.format(install_dir=install_dir)


def _resolve_install_dir() -> str:
    """返回应用安装目录（设置可改，默认按平台）。"""
    try:
        from core.settings import get_app_settings
        raw = get_app_settings().install_dir
        if raw.strip():
            return raw.strip()
    except Exception:
        pass
    import sys
    if sys.platform == "win32":
        import os
        return os.path.join(
            os.environ.get("LOCALAPPDATA", str(Path.home())), "WPSEnhancer",
        )
    return "/Applications"


class _UpdateWorker(QObject):
    """后台检查更新的 worker（QThread 内执行，结果经信号回主线程）。

    禁止在 worker 线程使用 QTimer/UI——Qt 对象线程相关，非主线程无事件循环。
    """

    done = pyqtSignal(tuple)

    def __init__(self, use_proxy: bool, update_url: Optional[str]) -> None:
        super().__init__()
        self._use_proxy = use_proxy
        self._update_url = update_url

    def run(self) -> None:
        try:
            result: tuple = (
                "ok",
                check_latest_release(
                    use_system_proxy=self._use_proxy,
                    update_url=self._update_url,
                ),
            )
        except UpdaterError as e:
            get_logger("ui.update_flow").warning(f"检查更新失败：{e}")
            result = ("error", str(e))
        except Exception as e:  # 兜底：任何异常都不允许线程静默卡死
            get_logger("ui.update_flow").exception(f"检查更新异常：{e}")
            result = ("error", f"检查更新异常：{e}")
        self.done.emit(result)


def check_update_now(parent: QWidget, silent_on_failure: bool,
                     on_done: Optional[Callable[[], None]] = None,
                     timeout_ms: int = 18000,
                     use_proxy: bool = True,
                     update_url: Optional[str] = None) -> None:
    """后台检查更新并处理结果（立即返回，不阻塞 UI）。

    on_done：结果处理完成后在主线程回调（用于复位 UI 状态，如清空"检查中"文本）。
    timeout_ms：兜底超时（双端点各 8s + 缓冲）——DNS 解析不受 socket timeout 控制，
    可能无限挂起；到点仍无结果则按超时处理并提示，保证状态文本永远会复位。
    use_proxy：是否自动使用系统代理（来自设置，默认开启）。
    update_url：自定义更新源（update.json 地址，来自设置；空则用 GitHub）。
    """
    done = {"ok": False}

    def _finish(result: tuple) -> None:
        # 主线程串行执行；guard 与 worker 结果先到者生效（防重复弹窗）
        if done["ok"]:
            return
        done["ok"] = True
        _handle_result(parent, result, silent_on_failure, on_done)

    def _guard() -> None:
        if not done["ok"]:
            get_logger("ui.update_flow").warning(
                f"检查更新超时（{timeout_ms // 1000}s 兜底）",
            )
            _finish(("error", "检查超时，请检查网络连接后重试"))

    # 旧实现用 threading.Thread + 线程内 QTimer.singleShot：timer 在线程内
    # 创建（无事件循环）永不触发 → 结果回不到主线程 → 兜底误报超时。
    # 改用 QThread + pyqtSignal：QueuedConnection 跨线程安全回到主线程。
    thread = QThread()
    worker = _UpdateWorker(use_proxy=use_proxy, update_url=update_url)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(_finish)      # 跨线程 QueuedConnection → 主线程
    worker.done.connect(thread.quit)
    worker.done.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    _ACTIVE_THREADS.append((thread, worker))  # 持有引用防 GC（PyQt 信号不持有 receiver）

    def _release() -> None:
        try:
            _ACTIVE_THREADS.remove((thread, worker))
        except ValueError:
            pass

    thread.finished.connect(_release)
    QTimer.singleShot(timeout_ms, _guard)
    thread.start()


def _handle_result(parent: QWidget, result: tuple, silent: bool,
                   on_done: Optional[Callable[[], None]] = None) -> None:
    """处理检查结果：无更新提示/有新版本询问下载。"""
    status, payload = result
    if status == "error":
        if not silent:
            QMessageBox.warning(parent, "检查更新失败", payload)
        if on_done is not None:
            on_done()
        return
    info: ReleaseInfo = payload
    if compare_versions(APP_VERSION, info.tag_name) >= 0:
        if not silent:
            QMessageBox.information(
                parent, "检查更新", f"当前已是最新版本 v{APP_VERSION}",
            )
        if on_done is not None:
            on_done()
        return
    notes_text = f"\n更新说明：{info.notes}\n" if info.notes else ""
    answer = QMessageBox.question(
        parent, "发现新版本",
        f"发现新版本 {info.tag_name}（当前 v{APP_VERSION}）{notes_text}\n"
        f"发布时间：{info.published_at[:10]}\n\n是否下载更新包？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if on_done is not None:
        on_done()
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
    download_dir = _resolve_download_dir()
    dest = download_dir / f"WPS增强工具_{info.tag_name}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)

    def worker() -> None:
        try:
            download_file(info.zip_url, dest)
            verify_zip_integrity(dest)  # 坏包直接拦截，避免替换损坏的更新包
            result: tuple = ("ok", str(dest))
        except UpdaterError as e:
            get_logger("ui.update_flow").warning(f"下载更新包失败：{e}")
            try:
                dest.unlink(missing_ok=True)  # 清理损坏的半成品
            except OSError:
                pass
            result = ("error", str(e))
        QTimer.singleShot(
            0, lambda: _handle_download_done(parent, result),
        )

    threading.Thread(target=worker, daemon=True).start()


def _resolve_download_dir() -> Path:
    """返回更新包下载目录（设置可改，默认系统下载目录）。"""
    try:
        from core.settings import get_app_settings
        raw = get_app_settings().download_dir
        if raw.strip():
            return Path(raw.strip()).expanduser()
    except Exception:
        pass
    return Path.home() / "Downloads"


def _reveal_in_finder(path: str) -> None:
    """在系统文件管理器中定位文件（macOS Finder / Windows 资源管理器）。"""
    import subprocess
    import sys
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", path])
        else:
            subprocess.Popen(["open", "-R", path])
    except OSError:
        pass  # 打不开文件管理器不影响主流程，静默


def _handle_download_done(parent: QWidget, result: tuple) -> None:
    """下载完成：校验已通过，提示替换指引 + 打开所在文件夹按钮。"""
    status, payload = result
    if status == "error":
        QMessageBox.warning(parent, "下载失败", payload)
        return
    box = QMessageBox(parent)
    box.setWindowTitle("更新包已下载")
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(f"更新包已保存到：\n{payload}\n\n{_replace_guide()}")
    box.addButton("打开所在文件夹", QMessageBox.ButtonRole.ActionRole)
    box.addButton("打开安装目录", QMessageBox.ButtonRole.ActionRole)
    box.addButton(QMessageBox.StandardButton.Ok)
    box.exec()
    if box.buttonRole(box.clickedButton()) == QMessageBox.ButtonRole.ActionRole:
        if box.clickedButton().text() == "打开安装目录":
            _reveal_dir(_resolve_install_dir())
        else:
            _reveal_in_finder(payload)


def _reveal_dir(path: str) -> None:
    """在系统文件管理器中打开目录（macOS Finder / Windows 资源管理器）。"""
    import subprocess
    import sys
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", path])
        else:
            subprocess.Popen(["open", path])
    except OSError:
        pass  # 打不开文件管理器不影响主流程，静默
