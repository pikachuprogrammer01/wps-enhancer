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
import time
import urllib.error
import urllib.request

import certifi
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.exceptions import WpsEnhancerError
from core.logger import get_logger, log_call

# GitHub 仓库（公开仓库无需 token）
REPO = "pikachuprogrammer01/wps-enhancer"
_UA = "wps-enhancer-updater/1.0"
_DEFAULT_TIMEOUT = 8
# 下载失败重试退避（秒）
_BACKOFF = (1, 3, 7)
# 网页端 Release 页的 tag 链接，如 /owner/repo/releases/tag/v1.0.2
_HTML_TAG_RE = re.compile(r"/releases/tag/(v[\d.]+)")
# 资产文件名的平台段原始大小写（CI 产物名：WPSEnhancer-macOS-*.zip）
_ASSET_PLATFORM = {"macos": "macOS", "windows": "Windows"}


class UpdaterError(WpsEnhancerError):
    """更新检查/下载失败（网络、解析、响应异常）。"""


class _NoRelease(UpdaterError):
    """仓库确实没有已发布版本（404）——回退网页端也没有意义。"""


class _InvalidUpdateSource(UpdaterError):
    """自定义更新源配置错误（JSON 格式/字段缺失）——回退会掩盖配置问题。"""


@dataclass
class ReleaseInfo:
    """GitHub Release 摘要信息。"""
    tag_name: str          # 版本 tag，如 v1.1.0
    html_url: str          # Release 页面
    zip_url: Optional[str] = None   # 更新包下载地址（zip 资产）
    zip_size: Optional[int] = None  # 更新包字节数
    published_at: str = ""
    notes: str = ""        # 更新说明（自定义源/Release body）


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
    update_url: Optional[str] = None,
) -> ReleaseInfo:
    """查询最新版本（网络/解析失败抛 UpdaterError）。

    platform：更新包平台标签（"macos"/"windows"，默认按当前系统）；
    arch：架构标签（"arm64"/"x86_64"/"x86"，默认按当前机器）。
    use_system_proxy：是否自动读取并使用系统代理（打包版无 shell 代理环境）。
    update_url：自定义更新源（update.json 地址）。配置后优先使用自定义源
    （国内访问 GitHub 不稳定时可托管到 Gitee/OSS 等可达地址），失败回退 GitHub。
    资产匹配：优先「平台+架构」精确匹配，回退「仅平台」匹配（兼容旧资产）。
    网络策略：api.github.com 失败（非 404）自动回退 github.com 网页端
    （fastly CDN 连通性通常更好，国内访问更稳）。
    """
    platform = platform or _current_platform()
    arch = arch or _current_arch()
    if use_system_proxy:
        _apply_system_proxy()  # 打包版无 shell 代理环境：从系统代理补上
    if update_url:
        try:
            return _check_via_custom(update_url, timeout, platform, arch)
        except _InvalidUpdateSource:
            raise  # 源配置错误必须暴露，回退会掩盖问题
        except UpdaterError as e:
            get_logger("core.updater").warning(
                f"自定义更新源不可达，回退 GitHub：{e}",
            )
    try:
        return _check_via_api(repo, timeout, platform, arch)
    except _NoRelease:
        raise  # 仓库确实无 Release，网页端也不会有
    except UpdaterError as api_err:
        # 网络不稳/超时/状态码异常 → 回退网页端（tag 提取 + 资产 URL 构造）
        try:
            return _check_via_html(repo, timeout, platform, arch)
        except UpdaterError as html_err:
            raise UpdaterError(
                f"检查更新失败（API 与网页两种方式均不可达）：{html_err}"
            ) from api_err


def _check_via_custom(update_url: str, timeout: int, platform: str = "",
                      arch: str = "") -> ReleaseInfo:
    """通过自定义更新源查询最新版本（update.json）。

    格式（多平台）：
        {"version": "1.1.0", "urls": {"macos-arm64": "…zip", "windows-x86_64": "…zip"},
         "notes": "说明"}
    兼容旧格式（单平台）：
        {"version": "1.1.0", "url": "…zip", "notes": "说明"}
    字段缺失/格式错误抛 _InvalidUpdateSource（明确提示，不静默）。
    """
    req = urllib.request.Request(update_url, headers={"User-Agent": _UA})
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            if resp.status != 200:
                raise UpdaterError(f"自定义更新源返回状态码 {resp.status}")
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise UpdaterError(f"自定义更新源返回状态码 {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise UpdaterError(f"无法连接自定义更新源：{e}") from e
    except (ssl.SSLError, OSError) as e:
        raise UpdaterError(f"网络或证书异常：{e}") from e
    except json.JSONDecodeError as e:
        raise _InvalidUpdateSource(
            f"自定义更新源格式错误（非 JSON）：{e}",
        ) from e

    version = str(data.get("version", "")).strip()
    if not version:
        raise _InvalidUpdateSource("自定义更新源缺少 version 字段")
    tag = version if version.startswith("v") else f"v{version}"
    # 多平台 urls 映射优先，兼容旧版单 url
    urls = data.get("urls") if isinstance(data.get("urls"), dict) else {}
    zip_url = ""
    if urls:
        key = f"{platform}-{arch}" if platform and arch else ""
        zip_url = str(urls.get(key, "")).strip()
        if not zip_url:
            raise _InvalidUpdateSource(
                f"自定义更新源缺少 {key or 'platform-arch'} 的下载地址（urls.{key}）",
            )
    else:
        zip_url = str(data.get("url", "")).strip()
        if not zip_url:
            raise _InvalidUpdateSource("自定义更新源缺少 url 字段")
    return ReleaseInfo(
        tag_name=tag,
        html_url=update_url,
        zip_url=zip_url,
        zip_size=None,
        published_at="",
        notes=str(data.get("notes", "")),
    )


def _check_via_api(
    repo: str, timeout: int, platform: str, arch: str,
) -> ReleaseInfo:
    """通过 GitHub API 查询最新 Release（失败抛 UpdaterError）。"""
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
            raise _NoRelease("仓库暂无已发布的版本（Release）") from e
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


def _check_via_html(
    repo: str, timeout: int, platform: str, arch: str,
) -> ReleaseInfo:
    """回退通道：解析 github.com 网页端 /releases/latest（不依赖 API）。

    网页端由 fastly CDN 加速，连通性通常优于 api.github.com；
    tag 从页面 HTML 提取，zip 资产 URL 按已知命名规则构造
    （WPSEnhancer-{platform}-{arch}.zip）。
    """
    url = f"https://github.com/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise _NoRelease("仓库暂无已发布的版本（Release）") from e
        raise UpdaterError(f"GitHub 返回状态码 {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise UpdaterError(f"无法连接 GitHub：{e}") from e
    except (ssl.SSLError, OSError) as e:
        raise UpdaterError(f"网络或证书异常：{e}") from e

    m = _HTML_TAG_RE.search(html)
    if not m:
        raise UpdaterError("无法解析更新信息（页面格式异常）")
    tag = m.group(1)
    asset_name = (
        f"WPSEnhancer-{_ASSET_PLATFORM.get(platform, platform)}-{arch}.zip"
    )
    return ReleaseInfo(
        tag_name=tag,
        html_url=f"https://github.com/{repo}/releases/tag/{tag}",
        zip_url=(
            f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"
        ),
        zip_size=None,
        published_at="",
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


def verify_zip_integrity(path: Path) -> None:
    """校验 zip 完整可读（坏包抛 UpdaterError，防止替换损坏的更新包）。"""
    import zipfile
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                zf.open(info).read(1)  # 逐条目探测损坏（CRC 校验在 read 时触发）
    except (zipfile.BadZipFile, OSError, RuntimeError) as e:
        raise UpdaterError(f"更新包损坏（{e}），请删除后重新下载") from e


@log_call("core.updater", log_args=False)
def download_file(url: str, dest: Path, timeout: int = 30,
                  use_system_proxy: bool = True,
                  retries: int = 3) -> Path:
    """流式下载 url 到 dest（覆盖），返回 dest；失败抛 UpdaterError。

    retries：网络抖动自动重试次数（1s/3s/7s 退避），失败后重试自恢复。
    重试之间使用短退避，避免雪崩；全部重试耗尽才报错。
    """
    if use_system_proxy:
        _apply_system_proxy()  # 下载同样走系统代理
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    context = ssl.create_default_context(cafile=certifi.where())
    last_err: Exception = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout,
                                        context=context) as resp, \
                    open(dest, "wb") as f:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            return dest
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt < retries:
                get_logger("core.updater").warning(
                    f"下载失败（第 {attempt + 1} 次），{_BACKOFF[attempt]}s 后重试：{e}",
                )
                time.sleep(_BACKOFF[attempt])
    raise UpdaterError(f"下载更新包失败：{last_err}") from last_err
