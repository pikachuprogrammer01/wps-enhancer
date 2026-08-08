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
                {"name": "WPS增强工具.zip",
                 "browser_download_url": "https://github.com/x/wps-enhancer/releases/download/v1.1.0/WPS增强工具.zip",
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
        self.assertTrue(info.zip_url.endswith("WPS增强工具.zip"))
        self.assertEqual(info.zip_size, 12345)

    def test_check_latest_release_http_error(self):
        with mock.patch("core.updater.urllib.request.urlopen") as urlopen:
            resp = mock.MagicMock()
            resp.status = 404
            urlopen.return_value.__enter__.return_value = resp
            with self.assertRaises(UpdaterError):
                check_latest_release()

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


if __name__ == "__main__":
    unittest.main()
