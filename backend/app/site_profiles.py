"""站点适配层。

某些平台的风控需要针对性的请求参数，这里按域名下发额外的 yt-dlp 选项，
作为不改动 yt-dlp 源码前提下的扩展点。新增平台适配只需往下面的表里加一条。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from yt_dlp.networking.impersonate import ImpersonateTarget

from .config import COOKIES_DIR, GLOBAL_COOKIES_FILE


def _chrome_impersonate() -> dict[str, Any]:
    try:
        import curl_cffi  # noqa: F401
    except ImportError:
        return {}
    # yt-dlp 要求 ImpersonateTarget 对象，传字符串 "chrome" 会直接 AssertionError
    return {"impersonate": ImpersonateTarget.from_str("chrome")}


# 实测结论：哔哩哔哩的 WAF 会对任何 User-Agent 以 "Mozilla/" 开头
# 且不带有效 buvid3 Cookie 的请求返回 412，换成非浏览器 UA 反而能正常通过。
# YouTube / TikTok 则相反，需要浏览器 TLS 指纹，有 curl_cffi 时走 impersonate。
SITE_PROFILES: dict[str, dict[str, Any]] = {
    "bilibili.com": {"http_headers": {"User-Agent": "curl/8.5.0"}},
    "b23.tv": {"http_headers": {"User-Agent": "curl/8.5.0"}},
    "bilibili.tv": {"http_headers": {"User-Agent": "curl/8.5.0"}},
    "youtube.com": _chrome_impersonate(),
    "youtu.be": _chrome_impersonate(),
    "tiktok.com": _chrome_impersonate(),
    "douyin.com": _chrome_impersonate(),
    "iesdouyin.com": _chrome_impersonate(),
}


def _root_domain(host: str) -> str:
    parts = host.lower().lstrip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def _cookie_file_for(domain: str) -> Path | None:
    candidate = COOKIES_DIR / f"{domain}.txt"
    if candidate.exists():
        return candidate
    if GLOBAL_COOKIES_FILE.exists():
        return GLOBAL_COOKIES_FILE
    return None


def profile_for(url: str) -> dict[str, Any]:
    """返回该 URL 需要叠加的 yt-dlp 选项。"""
    host = urlparse(url).hostname or ""
    domain = _root_domain(host)

    opts: dict[str, Any] = {}
    for key, value in SITE_PROFILES.items():
        if domain == key or host.endswith("." + key):
            opts = {k: dict(v) if isinstance(v, dict) else v for k, v in value.items()}
            break

    cookie_file = _cookie_file_for(domain)
    if cookie_file:
        opts["cookiefile"] = str(cookie_file)
    return opts
