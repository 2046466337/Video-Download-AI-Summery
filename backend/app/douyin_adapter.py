"""抖音站点适配。

抖音对 `aweme/v1/web/aweme/detail` 接口加了 Argus 风控（2026-09 起），
任何非浏览器请求都会返回 403 `Blocked by ArgusSecurityPlugin Uifid Not Found`，
yt-dlp 官方 DouyinIE 因此失效，且 `https://www.douyin.com/jingxuan?modal_id=...`
这种精选页链接根本不在 yt-dlp 的 URL 匹配表里。

解法：用真实浏览器（Playwright + 系统 Edge/Chromium）打开视频页，
浏览器内由抖音自己的 JS 完成挑战、拿到带签名的 `aweme_detail` 响应，
我们从中取出各清晰度的 CDN 直链（douyinvod 合并流）再下载。

直链带时效签名，因此「解析」与「下载」各自独立地重新获取一次直链，
保证下载时签名仍是新鲜的。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import requests

from .utils import format_duration, format_size

DOUYIN_HOSTS = ("douyin.com", "iesdouyin.com")

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

CDN_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Referer": "https://www.douyin.com/",
}

TIMEOUT = (10, 30)

# 清晰度档位：数字为该档的「短边像素」，从高到低
QUALITY_TIERS: list[tuple[int, str, str]] = [
    (2160, "4K 超清", "极致画质"),
    (1440, "2K 超清", "高码率"),
    (1080, "1080P 高清", "画质与体积均衡"),
    (720, "720P 高清", "通用之选"),
    (540, "540P 标清", "省流量"),
    (480, "480P 标清", "省流量"),
    (360, "360P 流畅", "体积最小"),
    (240, "240P 极速", "体积最小"),
]

# Playwright 的 sync API 不是线程安全的：并发下载时串行化所有浏览器会话
_BROWSER_LOCK = threading.Lock()

_ID_RE = re.compile(r"(?:/video/|/share/video/|/note/)(\d+)")
_MODAL_RE = re.compile(r"(?:^|[?&])modal_id=(\d+)")


class DouyinError(RuntimeError):
    """抖音适配失败，message 可直接展示。"""


def is_douyin(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in DOUYIN_HOSTS)


def _resolve_short_link(url: str) -> str:
    """v.douyin.com 短链会 302 到真实视频页，这里跟到最终地址。"""
    try:
        response = requests.get(
            url,
            headers={"User-Agent": BROWSER_UA},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        return response.url
    except requests.RequestException:
        return url


def extract_douyin_id(url: str) -> str:
    resolved = _resolve_short_link(url)
    match = _MODAL_RE.search(urlparse(resolved).query) or _MODAL_RE.search(resolved)
    if match:
        return match.group(1)
    match = _ID_RE.search(resolved)
    if match:
        return match.group(1)
    raise DouyinError("无法从链接中识别抖音视频 ID，请使用视频链接或分享短链")


def _fetch_detail_via_browser(aweme_id: str) -> dict[str, Any]:
    """用真实浏览器打开视频页，截获带签名的 aweme_detail 响应。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - 环境缺依赖
        raise DouyinError("缺少 Playwright，无法解析抖音，请先安装依赖") from exc

    url = f"https://www.douyin.com/video/{aweme_id}"
    captured: dict[str, str] = {}

    def _on_response(response: Any) -> None:
        if "aweme/v1/web/aweme/detail" not in response.url:
            return
        if "json" not in (response.headers.get("content-type") or ""):
            return
        try:
            captured["body"] = response.text()
        except Exception:  # noqa: BLE001 - 响应体读取失败就等下一次
            pass

    with _BROWSER_LOCK:
        try:
            with sync_playwright() as p:
                browser = _launch_browser(p)
                try:
                    context = browser.new_context(
                        user_agent=BROWSER_UA,
                        locale="zh-CN",
                        viewport={"width": 1440, "height": 900},
                    )
                    page = context.new_page()
                    page.on("response", _on_response)
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    for _ in range(40):  # 最多等 20 秒
                        if captured.get("body"):
                            break
                        page.wait_for_timeout(500)
                    context.close()
                finally:
                    browser.close()
        except Exception as exc:  # noqa: BLE001 - 浏览器异常统一兜底
            raise DouyinError(f"抖音页面未能加载：{exc}") from exc

    body = captured.get("body")
    if not body:
        raise DouyinError("抖音页面未能返回视频数据，可能是网络问题或触发了风控，请稍后重试")

    payload = json.loads(body)
    detail = payload.get("aweme_detail") or {}
    if not detail or not detail.get("video"):
        status_code = payload.get("status_code")
        if status_code and status_code != 0:
            raise DouyinError(f"抖音返回错误（{status_code}），该视频可能不存在或已删除")
        raise DouyinError("没有解析到抖音视频内容，该视频可能不存在或需登录")
    return detail


def _launch_browser(p: Any) -> Any:
    """优先用系统 Edge（免下载），否则用 Playwright 自带的 Chromium。"""
    try:
        return p.chromium.launch(headless=True, channel="msedge")
    except Exception:
        return p.chromium.launch(headless=True)


def _normalize_height(height: int) -> int:
    for std in (2160, 1440, 1080, 720, 540, 480, 360, 240):
        if height >= std:
            return std
    return 240


def _is_progressive(url: str) -> bool:
    """合并流（音视频一体的 mp4）不含 media-video / media-audio 分轨标记。"""
    return "media-video" not in url and "media-audio" not in url and "douyinvod" in url


def _codec_rank(item: dict[str, Any]) -> int:
    """H264 最好（0），HEVC 次之（1），ByteVC1 私有编码兼容性最差（2）。"""
    if item.get("is_bytevc1"):
        return 2
    if item.get("is_h265"):
        return 1
    return 0


def _collect_streams(detail: dict[str, Any]) -> list[dict[str, Any]]:
    """收集全部合并流（progressive mp4），补上 height/size 字段。"""
    video = detail.get("video") or {}
    streams: list[dict[str, Any]] = []
    for item in video.get("bit_rate") or []:
        play = item.get("play_addr") or {}
        urls = play.get("url_list") or []
        if not urls or not _is_progressive(urls[0]):
            continue
        height = int(play.get("height") or 0)
        if not height:
            continue
        streams.append(
            {
                "height": height,
                "size": int(play.get("data_size") or 0),
                "bitrate": int(item.get("bit_rate") or 0),
                "urls": urls,
                "codec_rank": _codec_rank(item),
            }
        )
    return streams


def _pick_for_height(streams: list[dict[str, Any]], target_height: int) -> dict[str, Any] | None:
    """在目标档位里选一条流：编码兼容性优先，再选码率最高。"""
    candidates = [s for s in streams if _normalize_height(s["height"]) == target_height]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda s: (-s["codec_rank"], s["bitrate"]),
    )


def build_douyin_info(url: str) -> dict[str, Any]:
    aweme_id = extract_douyin_id(url)
    detail = _fetch_detail_via_browser(aweme_id)
    video = detail.get("video") or {}
    streams = _collect_streams(detail)
    if not streams:
        raise DouyinError("该视频没有可下载的清晰度，可能是图集或需登录")

    duration_ms = int(video.get("duration") or 0)
    duration = int(duration_ms / 1000) if duration_ms else None

    options: list[dict[str, Any]] = []
    for height, label, note in QUALITY_TIERS:
        chosen = _pick_for_height(streams, height)
        if not chosen:
            continue
        if chosen["codec_rank"] > 0:
            note = "HEVC 编码，部分设备可能无法播放"
        options.append(
            {
                "id": f"video-{height}",
                "label": label,
                "note": note,
                "kind": "video",
                "height": height,
                "ext": "mp4",
                "filesize": chosen["size"] or None,
                "filesize_text": format_size(chosen["size"]),
                "needs_merge": False,
                "recommended": False,
            }
        )

    if not options:
        raise DouyinError("没有可用的清晰度，请稍后重试")

    preferred = next((o for o in options if o["height"] == 1080), options[0])
    preferred["recommended"] = True

    # 音频选项：从最低档合并流抽取，避免单独处理 DASH 音频分片
    options.append(
        {
            "id": "audio-mp3",
            "label": "仅音频 MP3",
            "note": "播客 / 音乐 / 网课",
            "kind": "audio",
            "height": None,
            "ext": "mp3",
            "filesize": None,
            "filesize_text": "",
            "needs_merge": False,
            "recommended": False,
        }
    )

    cover = ((video.get("cover") or {}).get("url_list") or []) or (
        (video.get("origin_cover") or {}).get("url_list") or []
    )
    author = detail.get("author") or {}
    statistics = detail.get("statistics") or {}

    return {
        "url": f"https://www.douyin.com/video/{aweme_id}",
        "title": detail.get("desc") or "未命名视频",
        "thumbnail": cover[0] if cover else None,
        "duration": duration,
        "duration_text": format_duration(duration),
        "uploader": author.get("nickname") or "",
        "platform": "抖音",
        "view_count": statistics.get("digg_count"),
        "options": options,
    }


def _safe_name(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", title).strip() or "video"
    return cleaned[:60]


def _ffmpeg_bin() -> str:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise DouyinError("未找到 FFmpeg，无法处理音频")
    return binary


def _download_url(url: str, dest: Path, on_progress: Callable[[dict], None]) -> None:
    response = requests.get(url, headers=CDN_HEADERS, stream=True, timeout=(10, 60))
    response.raise_for_status()
    total = int(response.headers.get("Content-Length") or 0)
    done = 0
    started = time.time()
    with dest.open("wb") as handle:
        for chunk in response.iter_content(256 * 1024):
            if not chunk:
                continue
            handle.write(chunk)
            done += len(chunk)
            elapsed = max(time.time() - started, 0.001)
            speed = done / elapsed
            remain = (total - done) / speed if total and speed else 0
            on_progress(
                {
                    "status": "downloading",
                    "downloaded_bytes": done,
                    "total_bytes": total,
                    "speed": speed,
                    "eta": remain,
                }
            )
    on_progress({"status": "finished", "downloaded_bytes": done, "total_bytes": total or done})


def _stream_for(detail: dict[str, Any], target_height: int) -> dict[str, Any]:
    streams = _collect_streams(detail)
    chosen = _pick_for_height(streams, target_height)
    if not chosen:
        # 目标档位没有，退而求其次选最接近的更高档
        fallback = max(streams, key=lambda s: s["height"], default=None)
        if not fallback:
            raise DouyinError("没有可用的视频流")
        return fallback
    return chosen


def download_douyin(
    url: str,
    option_id: str,
    out_dir: Path,
    on_progress: Callable[[dict], None],
    on_stage: Callable[[dict], None],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    aweme_id = extract_douyin_id(url)
    # 重新获取直链，保证下载时签名未过期
    detail = _fetch_detail_via_browser(aweme_id)
    title = detail.get("desc") or "未命名视频"
    stem = _safe_name(title)

    if option_id == "audio-mp3":
        stream = _stream_for(detail, 540)
        source = out_dir / f"{stem}.source.mp4"
        on_stage({"status": "started", "postprocessor": "ExtractAudio"})
        _download_url(stream["urls"][0], source, on_progress)
        on_stage({"status": "started", "postprocessor": "FFmpegExtractAudio"})
        output = out_dir / f"{stem}.mp3"
        result = subprocess.run(
            [_ffmpeg_bin(), "-y", "-i", str(source), "-vn", "-b:a", "192k", str(output)],
            capture_output=True,
        )
        source.unlink(missing_ok=True)
        if result.returncode != 0 or not output.exists():
            raise DouyinError("音频转换失败，请确认已安装 FFmpeg")
        return output

    match = re.fullmatch(r"video-(\d+)", option_id)
    target_height = int(match.group(1)) if match else 720
    stream = _stream_for(detail, target_height)
    output = out_dir / f"{stem}.mp4"
    _download_url(stream["urls"][0], output, on_progress)
    return output
