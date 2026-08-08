"""自动更新模块测试（版本比较 / Release 解析 / 下载）。"""

import unittest
from pathlib import Path
from unittest import mock

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

from core.updater import (
    ReleaseInfo, UpdaterError, check_latest_release, compare_versions,
    download_file,
)


class VersionCompareTest(unittest.TestCase):
    """语义化版本比较。"""

    def test_compare_versions(self):
        self.assertEqual(compare_versions("1.0.0", "1.0.0"), 0)
        self.assertEqual(compare_versions("1.0.0", "1.0.1"), -1)
        self.assertEqual(compare_versions("1.1.0", "1.0.9"), 1)
        self.assertEqual(compare_versions("2.0.0", "1.9.9"), 1)
        self.assertEqual(compare_versions("1.10.0", "1.9.0"), 1)
        # v 前缀兼容
        self.assertEqual(compare_versions("1.0.0", "v1.1.0"), -1)
        self.assertEqual(compare_versions("v1.2.0", "1.2.0"), 0)
        # 不同段数
        self.assertEqual(compare_versions("1.0", "1.0.1"), -1)
        # 非数字后缀忽略
        self.assertEqual(compare_versions("1.0.0", "1.0.1-beta"), -1)


class CheckReleaseTest(unittest.TestCase):
    """GitHub Releases API 解析。"""

    def test_check_latest_release_parses_assets(self):
        payload = {
            "tag_name": "v1.1.0",
            "html_url": "https://github.com/x/wps-enhancer/releases/tag/v1.1.0",
            "published_at": "2026-08-09T00:00:00Z",
            "assets": [
                {"name": "WPS增强工具-macOS.zip",
                 "browser_download_url": "https://github.com/x/wps-enhancer/releases/download/v1.1.0/WPS增强工具-macOS.zip",
                 "size": 12345},
                {"name": "notes.md", "browser_download_url": "https://x/notes"},
            ],
        }
        with mock.patch("core.updater.urllib.request.urlopen") as urlopen:
            resp = mock.MagicMock()
            resp.status = 200
            resp.read.return_value = __import__("json").dumps(payload).encode()
            urlopen.return_value.__enter__.return_value = resp
            info = check_latest_release()
        self.assertEqual(info.tag_name, "v1.1.0")
        self.assertTrue(info.zip_url.endswith("WPS增强工具-macOS.zip"))
        self.assertEqual(info.zip_size, 12345)

    def test_check_latest_release_platform_asset(self):
        """更新包按平台匹配资产（macos/windows）。"""
        payload = {
            "tag_name": "v1.1.0",
            "html_url": "https://x",
            "published_at": "2026-08-09T00:00:00Z",
            "assets": [
                {"name": "WPSEnhancer-macOS-arm64.zip",
                 "browser_download_url": "https://x/mac-arm.zip", "size": 1},
                {"name": "WPSEnhancer-Windows-x86_64.zip",
                 "browser_download_url": "https://x/win-x64.zip", "size": 2},
            ],
        }
        with mock.patch("core.updater.urllib.request.urlopen") as urlopen:
            resp = mock.MagicMock()
            resp.status = 200
            resp.read.return_value = __import__("json").dumps(payload).encode()
            urlopen.return_value.__enter__.return_value = resp
            mac = check_latest_release(platform="macos", arch="arm64")
            win = check_latest_release(platform="windows", arch="x86_64")
            # 架构不匹配时回退：mac 机器在 x86_64 资产上按平台匹配不到架构 → 回退平台
            mac_fallback = check_latest_release(platform="macos", arch="x86_64")
        self.assertTrue(mac.zip_url.endswith("mac-arm.zip"))
        self.assertTrue(win.zip_url.endswith("win-x64.zip"))
        self.assertTrue(mac_fallback.zip_url.endswith("mac-arm.zip"))

    def test_check_latest_release_legacy_asset_fallback(self):
        """旧资产（无架构标签）也能被平台匹配命中（回退）。"""
        payload = {
            "tag_name": "v1.0.0",
            "html_url": "https://x",
            "published_at": "2026-08-08T00:00:00Z",
            "assets": [
                {"name": "WPSEnhancer-macOS.zip",
                 "browser_download_url": "https://x/mac.zip", "size": 1},
            ],
        }
        with mock.patch("core.updater.urllib.request.urlopen") as urlopen:
            resp = mock.MagicMock()
            resp.status = 200
            resp.read.return_value = __import__("json").dumps(payload).encode()
            urlopen.return_value.__enter__.return_value = resp
            info = check_latest_release(platform="macos", arch="arm64")
        self.assertTrue(info.zip_url.endswith("mac.zip"))

    def test_check_latest_release_http_error(self):
        """404（暂无 Release）与 500 分别给出明确错误。"""
        import urllib.error
        for code, expect in ((404, "暂无已发布"), (500, "500")):
            with mock.patch(
                "core.updater.urllib.request.urlopen",
                side_effect=urllib.error.HTTPError(
                    "https://x", code, "err", None, None,
                ),
            ):
                with self.assertRaises(UpdaterError) as ctx:
                    check_latest_release()
                self.assertIn(expect, str(ctx.exception))

    def test_check_latest_release_network_error(self):
        import urllib.error
        with mock.patch(
            "core.updater.urllib.request.urlopen",
            side_effect=urllib.error.URLError("boom"),
        ):
            with self.assertRaises(UpdaterError):
                check_latest_release()


class DownloadTest(unittest.TestCase):
    """更新包下载。"""

    def test_download_file_writes_chunks(self):
        chunks = [b"a" * 65536, b"tail"]
        with mock.patch("core.updater.urllib.request.urlopen") as urlopen:
            resp = mock.MagicMock()
            resp.read.side_effect = chunks + [b""]
            urlopen.return_value.__enter__.return_value = resp
            dest = Path(__file__).parent / "_dl_test.bin"
            try:
                download_file("https://x/pkg.zip", dest)
                self.assertEqual(dest.read_bytes(), b"a" * 65536 + b"tail")
            finally:
                dest.unlink(missing_ok=True)

    def test_download_file_network_error(self):
        import urllib.error
        with mock.patch(
            "core.updater.urllib.request.urlopen",
            side_effect=urllib.error.URLError("boom"),
        ):
            with self.assertRaises(UpdaterError):
                download_file("https://x/pkg.zip", Path("/tmp/_x.zip"))


class AppPathsPlatformTest(unittest.TestCase):
    """平台路径：Windows 打包用 %APPDATA%/%LOCALAPPDATA%。"""

    def test_windows_frozen_paths(self):
        import core.app_paths as ap

        with mock.patch.object(ap.sys, "platform", "win32"), \
                mock.patch.object(ap.sys, "frozen", True, create=True), \
                mock.patch.dict(
                    ap.os.environ,
                    {"APPDATA": r"C:\Users\test\AppData\Roaming",
                     "LOCALAPPDATA": r"C:\Users\test\AppData\Local"},
                ):
            data = ap.get_data_dir()
            logs = ap.get_logs_dir()
            # POSIX 测试机上 Path 不解析盘符：按组成部分断言
            self.assertEqual(data.name, "WPS Enhancer")
            self.assertIn("AppData", str(data))
            self.assertEqual(logs.name, "Logs")
            self.assertIn("Local", str(logs))

    def test_non_frozen_paths_unchanged(self):
        import core.app_paths as ap

        with mock.patch.object(ap.sys, "frozen", False, create=True):
            data = ap.get_data_dir()
            self.assertEqual(data, ap.get_app_root())
            self.assertEqual(ap.get_logs_dir(), ap.get_app_root() / "logs")


if __name__ == "__main__":
    unittest.main()
