"""URL 安全校验。

解析接口接受任意用户输入的 URL 并由服务端发起请求，如果不做限制，
它就会变成一个打内网的跳板（SSRF）。这里在解析前把协议和目标 IP 卡死。
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

# 抖音、小红书等的分享内容是一整段文案夹着链接，直接粘过来就该能用
URL_IN_TEXT = re.compile(r"https?://[^\s\u4e00-\u9fff，。、！？；：\"'）】]+")


class UnsafeUrlError(ValueError):
    """用户提交的 URL 不允许被服务端访问。"""


def _is_public_ip(raw_ip: str) -> bool:
    try:
        ip = ipaddress.ip_address(raw_ip)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_url(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        raise UnsafeUrlError("请输入视频链接")

    found = URL_IN_TEXT.search(url)
    if found:
        url = found.group(0)
    elif "://" not in url:
        url = "https://" + url.split()[0]

    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError("只支持 http/https 链接")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeUrlError("链接格式不正确，请检查后重试")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addr_info = None
    for attempt in range(2):
        try:
            # 限定 SOCK_STREAM，避免同一域名被重复查询三次，偶发解析失败明显减少
            addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
            break
        except socket.gaierror as exc:
            if attempt:
                raise UnsafeUrlError("无法解析该域名，请检查链接是否正确") from exc

    resolved = {item[4][0] for item in (addr_info or [])}
    if not resolved or not all(_is_public_ip(ip) for ip in resolved):
        raise UnsafeUrlError("该地址不在允许访问的范围内")

    return url
