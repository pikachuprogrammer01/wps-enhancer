"""GitHub Releases 自动更新：检查/比较/下载（纯标准库，无第三方依赖）。

用法：
    info = check_latest_release()          # 查最新版本（抛 UpdaterError）
    if compare_versions(APP_VERSION, info.tag_name) < 0:
        download_file(info.zip_url, dest)  # 下载更新包
"""

import json
import ssl
import urllib.error
import urllib.request

import certifi
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.exceptions import WpsEnhancerError
from core.logger import log_call

# GitHub 仓库（公开仓库无需 token）
REPO = "pikachuprogrammer01/wps-enhancer"
_UA = "wps-enhancer-updater/1.0"
_DEFAULT_TIMEOUT = 10


class UpdaterError(WpsEnhancerError):
    """更新检查/下载失败（网络、解析、响应异常）。"""


@dataclass
class ReleaseInfo:
    """GitHub Release 摘要信息。"""
    tag_name: str          # 版本 tag，如 v1.1.0
    html_url: str          # Release 页面
    zip_url: Optional[str] = None   # 更新包下载地址（zip 资产）
    zip_size: Optional[int] = None  # 更新包字节数
    published_at: str = ""


def compare_versions(local: str, remote: str) -> int:
    """语义化版本比较（支持 v 前缀）：local < remote 返回 -1，相等 0，大于 1。

    仅比较数字段（如 1.2.3）；非数字段（-beta 等）忽略。
    """
    def numbers(tag: str):
        parts = tag.strip().lstrip("vV").split(".")
        out = []
        for p in parts:
            digits = "".join(ch for ch in p if ch.isdigit())
            out.append(int(digits) if digits else 0)
        return out

    a, b = numbers(local), numbers(remote)
    for x, y in zip(a, b):
        if x != y:
            return -1 if x < y else 1
    if len(a) != len(b):
        return -1 if len(a) < len(b) else 1
    return 0


@log_call("core.updater", log_args=False, log_result=False)
def check_latest_release(
    repo: str = REPO, timeout: int = _DEFAULT_TIMEOUT,
    platform: Optional[str] = None,
) -> ReleaseInfo:
    """查询 GitHub Releases 最新版本（网络/解析失败抛 UpdaterError）。

    platform：更新包匹配平台（"macos" / "windows"，默认按当前系统）。
    """
    platform = platform or _current_platform()
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    # certifi 根证书（python.org 的 Python 与 PyInstaller 冻结环境均无系统证书）
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            if resp.status != 200:
                raise UpdaterError(f"GitHub API 返回状态码 {resp.status}")
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # urlopen 对 4xx/5xx 直接抛 HTTPError（不返回响应体）
        if e.code == 404:
            raise UpdaterError("仓库暂无已发布的版本（Release）") from e
        raise UpdaterError(f"GitHub API 返回状态码 {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise UpdaterError(f"无法连接 GitHub：{e}") from e
    except (ValueError, KeyError) as e:
        raise UpdaterError(f"解析更新信息失败：{e}") from e

    tag = str(data.get("tag_name", ""))
    if not tag:
        raise UpdaterError("Release 缺少版本号（tag_name）")
    zip_url: Optional[str] = None
    zip_size: Optional[int] = None
    for asset in data.get("assets", []) or []:
        name = str(asset.get("name", "")).lower()
        if name.endswith(".zip") and platform in name:
            zip_url = asset.get("browser_download_url") or zip_url
            zip_size = asset.get("size") or zip_size
    return ReleaseInfo(
        tag_name=tag,
        html_url=str(data.get("html_url", url)),
        zip_url=zip_url,
        zip_size=zip_size,
        published_at=str(data.get("published_at", "")),
    )


def _current_platform() -> str:
    """返回当前系统对应的更新包平台标签。"""
    import sys
    return "windows" if sys.platform == "win32" else "macos"


@log_call("core.updater", log_args=False)
def download_file(url: str, dest: Path, timeout: int = 30) -> Path:
    """流式下载 url 到 dest（覆盖），返回 dest；失败抛 UpdaterError。"""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp, \
                open(dest, "wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UpdaterError(f"下载更新包失败：{e}") from e
    return dest
