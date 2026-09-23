"""哔哩哔哩站点适配。

yt-dlp 官方 extractor 依赖网页里的 __INITIAL_STATE__。B 站 WAF 对浏览器 UA 返回 412，
对非浏览器 UA 又吐出不含该字段的页面，导致「封面能解析、所有清晰度都下不下来」。

这里不改 yt-dlp 源码，只用它的公开 API：
- 接口请求用 curl UA + Origin/Referer，避开 412
- 拉 CDN 流用浏览器 UA，避开 403
- playurl 带 try_look=1，游客也能拿到 720/1080
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import requests

from .utils import format_duration, format_size

API_HEADERS = {
    "User-Agent": "curl/8.5.0",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}

CDN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
}

BILI_HOSTS = ("bilibili.com", "b23.tv", "bilibili.tv")
BV_RE = re.compile(r"(BV[0-9A-Za-z]+)")
AV_RE = re.compile(r"(?:/video/av|/video/AV)(\d+)", re.I)
TIMEOUT = (10, 25)

QUALITY_TIERS: list[tuple[int, str, str]] = [
    (2160, "4K 超清", "极致画质"),
    (1440, "2K 超清", "高码率"),
    (1080, "1080P 高清", "画质与体积均衡"),
    (720, "720P 高清", "通用之选"),
    (480, "480P 标清", "省流量"),
    (360, "360P 流畅", "体积最小"),
    (240, "240P 极速", "体积最小"),
]


class BiliError(RuntimeError):
    """B 站适配失败，message 可直接展示。"""


def is_bilibili(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in BILI_HOSTS)


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(url, headers=API_HEADERS, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in (0, None):
        raise BiliError(payload.get("message") or "B 站接口返回错误")
    return payload.get("data") or {}


def resolve_bilibili_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host == "b23.tv" or host.endswith(".b23.tv"):
        response = requests.get(url, headers=API_HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return response.url
    return url


def extract_ids(url: str) -> tuple[str | None, str | None, int]:
    resolved = resolve_bilibili_url(url)
    query = parse_qs(urlparse(resolved).query)
    page = int((query.get("p") or ["1"])[0] or 1)
    bv = BV_RE.search(resolved)
    av = AV_RE.search(resolved)
    return (bv.group(1) if bv else None, av.group(1) if av else None, max(page, 1))


def _tier_of(height: int) -> tuple[int, str, str] | None:
    for tier in QUALITY_TIERS:
        if height >= tier[0]:
            return tier
    return None


def _pick_video(items: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        items,
        key=lambda f: (
            str(f.get("codecs") or "").startswith("avc1"),
            f.get("bandwidth") or 0,
        ),
    )


def fetch_view(bvid: str | None, aid: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {"bvid": bvid} if bvid else {"aid": aid}
    data = _get_json("https://api.bilibili.com/x/web-interface/view", params)
    if not data:
        raise BiliError("没有解析到视频内容")
    return data


def fetch_playurl(bvid: str | None, cid: int) -> dict[str, Any]:
    params: dict[str, Any] = {
        "cid": cid,
        "qn": 80,
        "fnval": 16,
        "fourk": 1,
        "try_look": 1,
    }
    if bvid:
        params["bvid"] = bvid
    return _get_json("https://api.bilibili.com/x/player/playurl", params)


def _stream_url(item: dict[str, Any]) -> str:
    return item.get("baseUrl") or item.get("base_url") or item.get("url") or ""


def _backup_urls(item: dict[str, Any]) -> list[str]:
    urls = []
    primary = _stream_url(item)
    if primary:
        urls.append(primary)
    for key in ("backupUrl", "backup_url"):
        extra = item.get(key) or []
        urls.extend(u for u in extra if u)
    return urls


def build_bilibili_info(url: str) -> dict[str, Any]:
    bvid, aid, page = extract_ids(url)
    if not bvid and not aid:
        raise BiliError("无法从链接中识别 B 站视频 ID")

    view = fetch_view(bvid, aid)
    pages = view.get("pages") or []
    page_info = pages[page - 1] if 0 < page <= len(pages) else (pages[0] if pages else {})
    cid = page_info.get("cid") or view.get("cid")
    if not cid:
        raise BiliError("没有拿到视频分 P 信息")

    play = fetch_playurl(view.get("bvid") or bvid, int(cid))
    dash = play.get("dash") or {}
    videos = dash.get("video") or []
    audios = dash.get("audio") or []
    duration = int(view.get("duration") or 0)
    best_audio = max(audios, key=lambda a: a.get("bandwidth") or 0) if audios else None
    audio_bps = (best_audio or {}).get("bandwidth") or 0

    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in videos:
        height = int(item.get("height") or 0)
        tier = _tier_of(height)
        if not tier:
            continue
        grouped.setdefault(tier[0], []).append(item)

    options: list[dict[str, Any]] = []
    for height, label, note in QUALITY_TIERS:
        bucket = grouped.get(height)
        if not bucket:
            continue
        best = _pick_video(bucket)
        size = None
        bitrate = best.get("bandwidth") or 0
        if bitrate and duration:
            size = int((bitrate + audio_bps) / 8 * duration)
        options.append(
            {
                "id": f"video-{height}",
                "label": label,
                "note": note,
                "kind": "video",
                "height": height,
                "ext": "mp4",
                "filesize": size,
                "filesize_text": format_size(size),
                "needs_merge": True,
                "recommended": False,
            }
        )

    if not options:
        raise BiliError("没有可用的清晰度，请稍后重试")

    preferred = next((o for o in options if o["height"] == 1080), options[0])
    preferred["recommended"] = True

    if best_audio:
        audio_size = int(audio_bps / 8 * duration) if audio_bps and duration else None
        options.append(
            {
                "id": "audio-mp3",
                "label": "仅音频 MP3",
                "note": "播客 / 音乐 / 网课",
                "kind": "audio",
                "height": None,
                "ext": "mp3",
                "filesize": audio_size,
                "filesize_text": format_size(audio_size),
                "needs_merge": False,
                "recommended": False,
            }
        )

    owner = view.get("owner") or {}
    stat = view.get("stat") or {}
    thumbnail = view.get("pic") or ""
    if thumbnail.startswith("http://"):
        thumbnail = "https://" + thumbnail[len("http://") :]

    title = view.get("title") or "未命名视频"
    if len(pages) > 1 and page_info.get("part"):
        title = f"{title} p{page:02d} {page_info['part']}"

    return {
        "url": f"https://www.bilibili.com/video/{view.get('bvid') or bvid}/",
        "title": title,
        "thumbnail": thumbnail or None,
        "duration": duration or None,
        "duration_text": format_duration(duration),
        "uploader": owner.get("name") or "",
        "platform": "哔哩哔哩",
        "view_count": stat.get("view"),
        "options": options,
    }


def _safe_name(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", title).strip() or "video"
    return cleaned[:60]


def _ffmpeg_bin() -> str:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise BiliError("未找到 FFmpeg，无法合并音视频")
    return binary


def _download_url(urls: list[str], dest: Path, on_progress: Callable[[dict], None]) -> None:
    last_error: Exception | None = None
    for url in urls:
        try:
            with requests.get(url, headers=CDN_HEADERS, stream=True, timeout=(10, 60)) as response:
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
            on_progress(
                {"status": "finished", "downloaded_bytes": done, "total_bytes": total or done}
            )
            return
        except Exception as exc:  # noqa: BLE001 - 换备用 CDN 再试
            last_error = exc
            continue
    raise BiliError(f"视频流下载失败：{last_error}")


def download_bilibili(
    url: str,
    option_id: str,
    out_dir: Path,
    on_progress: Callable[[dict], None],
    on_stage: Callable[[dict], None],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    bvid, aid, page = extract_ids(url)
    view = fetch_view(bvid, aid)
    pages = view.get("pages") or []
    page_info = pages[page - 1] if 0 < page <= len(pages) else (pages[0] if pages else {})
    cid = int(page_info.get("cid") or view.get("cid"))
    play = fetch_playurl(view.get("bvid") or bvid, cid)
    dash = play.get("dash") or {}
    videos = dash.get("video") or []
    audios = dash.get("audio") or []
    if not videos or not audios:
        raise BiliError("没有可用的音视频流")

    title = view.get("title") or "未命名视频"
    stem = _safe_name(title)

    best_audio = max(audios, key=lambda a: a.get("bandwidth") or 0)
    ffmpeg = _ffmpeg_bin()

    if option_id == "audio-mp3":
        audio_part = out_dir / f"{stem}.audio"
        on_stage({"status": "started", "postprocessor": "ExtractAudio"})
        _download_url(_backup_urls(best_audio), audio_part, on_progress)
        on_stage({"status": "started", "postprocessor": "FFmpegExtractAudio"})
        output = out_dir / f"{stem}.mp3"
        result = subprocess.run(
            [ffmpeg, "-y", "-i", str(audio_part), "-vn", "-b:a", "192k", str(output)],
            capture_output=True,
        )
        audio_part.unlink(missing_ok=True)
        if result.returncode != 0 or not output.exists():
            raise BiliError("音频转换失败，请确认已安装 FFmpeg")
        return output

    match = re.fullmatch(r"video-(\d+)", option_id)
    target_height = int(match.group(1)) if match else 10_000
    candidates = [v for v in videos if int(v.get("height") or 0) <= target_height]
    if not candidates:
        candidates = videos
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in candidates:
        height = int(item.get("height") or 0)
        grouped.setdefault(height, []).append(item)
    chosen_height = max(grouped)
    video_item = _pick_video(grouped[chosen_height])

    video_part = out_dir / f"{stem}.video"
    audio_part = out_dir / f"{stem}.audio"
    _download_url(_backup_urls(video_item), video_part, on_progress)
    _download_url(_backup_urls(best_audio), audio_part, on_progress)

    on_stage({"status": "started", "postprocessor": "Merger"})
    output = out_dir / f"{stem}.mp4"
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_part),
            "-i",
            str(audio_part),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ],
        capture_output=True,
        )
    video_part.unlink(missing_ok=True)
    audio_part.unlink(missing_ok=True)
    if result.returncode != 0 or not output.exists():
        raise BiliError("音视频合并失败，请确认已安装 FFmpeg")
    return output
