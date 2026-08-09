"""GitHub Releases 自动更新：检查/比较/下载（纯标准库，无第三方依赖）。

用法：
    info = check_latest_release()          # 查最新版本（抛 UpdaterError）
    if compare_versions(APP_VERSION, info.tag_name) < 0:
        download_file(info.zip_url, dest)  # 下载更新包
"""

import json
import os
import platform
import re
import ssl
import subprocess
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
_DEFAULT_TIMEOUT = 5


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


def _system_proxy() -> Optional[str]:
    """读取系统代理地址（macOS scutil / Windows 注册表），返回 http://host:port。

    打包版从 Finder/资源管理器启动时没有 shell 代理环境变量，
    urlopen 不会自动走系统代理（国内访问 GitHub 的主要卡点之一）。
    读取失败或无代理返回 None。
    """
    try:
        if platform.system() == "Windows":
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            ) as key:
                enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
                if not enable:
                    return None
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
                return server or None
        # macOS：scutil --proxy 输出形如 "HTTPSProxy : 127.0.0.1" / "HTTPSPort : 7890"
        out = subprocess.run(
            ["scutil", "--proxy"], capture_output=True, text=True, timeout=3,
        ).stdout
        m = re.search(r"HTTPSProxy\s*:\s*([^\s]+)", out)
        port_m = re.search(r"HTTPSPort\s*:\s*(\d+)", out)
        if not m:
            m = re.search(r"HTTPProxy\s*:\s*([^\s]+)", out)
            port_m = port_m or re.search(r"HTTPPort\s*:\s*(\d+)", out)
        if not m:
            return None
        return f"http://{m.group(1)}:{port_m.group(1) if port_m else 80}"
    except Exception:
        return None


def _apply_system_proxy() -> None:
    """把系统代理写入 HTTPS_PROXY/HTTP_PROXY 环境变量（仅在未显式设置时）。"""
    if os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"):
        return
    proxy = _system_proxy()
    if proxy:
        os.environ["HTTPS_PROXY"] = proxy
        os.environ["HTTP_PROXY"] = proxy


@log_call("core.updater", log_args=False, log_result=False)
def check_latest_release(
    repo: str = REPO, timeout: int = _DEFAULT_TIMEOUT,
    platform: Optional[str] = None, arch: Optional[str] = None,
    use_system_proxy: bool = True,
) -> ReleaseInfo:
    """查询 GitHub Releases 最新版本（网络/解析失败抛 UpdaterError）。

    platform：更新包平台标签（"macos"/"windows"，默认按当前系统）；
    arch：架构标签（"arm64"/"x86_64"/"x86"，默认按当前机器）。
    use_system_proxy：是否自动读取并使用系统代理（打包版无 shell 代理环境）。
    资产匹配：优先「平台+架构」精确匹配，回退「仅平台」匹配（兼容旧资产）。
    """
    platform = platform or _current_platform()
    arch = arch or _current_arch()
    if use_system_proxy:
        _apply_system_proxy()  # 打包版无 shell 代理环境：从系统代理补上
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        # certifi 根证书（python.org 的 Python 与 PyInstaller 冻结环境均无系统证书）
        context = ssl.create_default_context(cafile=certifi.where())
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
    except (ssl.SSLError, OSError, ValueError) as e:
        # 证书/SSL 环境异常也归为 UpdaterError，避免线程静默卡死
        raise UpdaterError(f"网络或证书异常：{e}") from e
    except (ValueError, KeyError) as e:
        raise UpdaterError(f"解析更新信息失败：{e}") from e

    tag = str(data.get("tag_name", ""))
    if not tag:
        raise UpdaterError("Release 缺少版本号（tag_name）")
    assets = data.get("assets", []) or []
    # 优先精确匹配（平台+架构），如 WPSEnhancer-macOS-arm64.zip
    exact = _find_asset(assets, platform, arch)
    if exact is None:
        exact = _find_asset(assets, platform, None)  # 回退仅平台（旧资产）
    zip_url = exact.get("browser_download_url") if exact else None
    zip_size = exact.get("size") if exact else None
    return ReleaseInfo(
        tag_name=tag,
        html_url=str(data.get("html_url", url)),
        zip_url=zip_url,
        zip_size=zip_size,
        published_at=str(data.get("published_at", "")),
    )


def _find_asset(assets: list, platform: str, arch: Optional[str]) -> Optional[dict]:
    """在资产列表中按平台（+可选架构）匹配 zip 资产。

    按文件名段精确匹配（`-` 分词），避免 x86 ⊂ x86_64 之类的子串误匹配。
    """
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if not name.endswith(".zip"):
            continue
        parts = name[:-4].split("-")  # WPSEnhancer-Windows-x86_64 → [wpsenhancer, windows, x86_64]
        if platform not in parts:
            continue
        if arch is not None and arch not in parts:
            continue
        return asset
    return None


def _current_platform() -> str:
    """返回当前系统对应的更新包平台标签。"""
    import sys
    return "windows" if sys.platform == "win32" else "macos"


def _current_arch() -> str:
    """返回当前机器架构标签（arm64 / x86_64 / x86）。

    Windows 上 platform.machine() 来自 PROCESSOR_ARCHITEW6432 /
    PROCESSOR_ARCHITECTURE（AMD64/ARM64/x86 等）；x86 与 x86_64 必须区分，
    不能把非 arm 一律当作 x86_64（32 位 Windows 会下载错包）。
    """
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "arm64"
    if machine in ("amd64", "x86_64"):
        return "x86_64"
    if machine in ("x86", "i386", "i686", "ia32"):
        return "x86"
    # 未知架构按 64 位主流处理，避免下载不到包
    return "x86_64"


@log_call("core.updater", log_args=False)
def download_file(url: str, dest: Path, timeout: int = 30,
                  use_system_proxy: bool = True) -> Path:
    """流式下载 url 到 dest（覆盖），返回 dest；失败抛 UpdaterError。"""
    if use_system_proxy:
        _apply_system_proxy()  # 下载同样走系统代理
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
