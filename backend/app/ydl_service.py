"""yt-dlp 薄封装。

刻意只做封装、不改 yt-dlp 源码：各平台反爬策略每周都在变，yt-dlp 靠高频发版对抗，
一旦 fork 改源码就再也升级不了，项目几个月后必然全面失效。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import requests
import yt_dlp

from .bilibili_adapter import BiliError, build_bilibili_info, download_bilibili, is_bilibili
from .config import FFMPEG_LOCATION, SOCKET_TIMEOUT
from .site_profiles import profile_for
from .utils import format_duration, format_size

# 从高到低，每一档对应用户看得懂的一个按钮
QUALITY_TIERS: list[tuple[int, str, str]] = [
    (2160, "4K 超清", "极致画质"),
    (1440, "2K 超清", "高码率"),
    (1080, "1080P 高清", "画质与体积均衡"),
    (720, "720P 高清", "通用之选"),
    (480, "480P 标清", "省流量"),
    (360, "360P 流畅", "体积最小"),
    (240, "240P 极速", "体积最小"),
]

AUDIO_OPTION_ID = "audio-mp3"

PLATFORM_ALIASES = {
    "BiliBili": "哔哩哔哩",
    "BiliBiliBangumi": "哔哩哔哩",
    "Youtube": "YouTube",
    "TikTok": "TikTok",
    "DouyinVideo": "抖音",
    "Douyin": "抖音",
    "Weibo": "微博",
    "KuaishouVideo": "快手",
    "Xiaohongshu": "小红书",
    "Generic": "通用解析",
}


class ParseError(RuntimeError):
    """解析失败，message 为可直接展示给用户的中文提示。"""


def _base_opts(url: str) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "socket_timeout": SOCKET_TIMEOUT,
        "retries": 3,
        "ignoreerrors": False,
    }
    if FFMPEG_LOCATION:
        opts["ffmpeg_location"] = FFMPEG_LOCATION
    return opts | profile_for(url)


def _tier_of(height: int) -> tuple[int, str, str] | None:
    for tier in QUALITY_TIERS:
        if height >= tier[0]:
            return tier
    return None


def _pick_best(formats: list[dict[str, Any]]) -> dict[str, Any] | None:
    """挑出该档位的代表格式。

    排序口径必须和下面构造的 format 选择器一致（优先 H.264 的 mp4），
    否则页面上展示的体积会和实际下载的文件对不上。
    """
    if not formats:
        return None
    return max(
        formats,
        key=lambda f: (
            str(f.get("vcodec") or "").startswith(("avc1", "h264")),
            f.get("ext") == "mp4",
            f.get("tbr") or 0,
            f.get("filesize") or f.get("filesize_approx") or 0,
        ),
    )


def _estimated_size(fmt: dict[str, Any], duration: float | None = None) -> int | None:
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    if size:
        return int(size)
    # YouTube 的部分分轨格式不返回体积，用码率乘时长估算，总比留空强
    tbr = fmt.get("tbr")
    if tbr and duration:
        return int(tbr * 1000 / 8 * duration)
    return None


def build_quality_options(info: dict[str, Any]) -> list[dict[str, Any]]:
    """把 yt-dlp 返回的几十条 format 归档成几个用户看得懂的选项。

    直接把原始 formats 丢给用户会劝退——同一清晰度往往有七八条编码不同的记录。
    """
    # 剔除故事板预览图：它们也带 height，混进来会造出 45P、90P 这种假档位
    formats = [
        f
        for f in (info.get("formats") or [])
        if f.get("format_id") and f.get("ext") != "mhtml" and f.get("protocol") != "mhtml"
    ]
    video_formats = [f for f in formats if f.get("vcodec") not in (None, "none") and f.get("height")]
    audio_formats = [f for f in formats if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")]

    duration = info.get("duration")
    best_audio = _pick_best(audio_formats)
    audio_size = _estimated_size(best_audio, duration) if best_audio else None

    grouped: dict[int, list[dict[str, Any]]] = {}
    for fmt in video_formats:
        tier = _tier_of(int(fmt["height"]))
        if tier:
            grouped.setdefault(tier[0], []).append(fmt)

    options: list[dict[str, Any]] = []
    for height, label, note in QUALITY_TIERS:
        bucket = grouped.get(height)
        if not bucket:
            continue
        best = _pick_best(bucket)
        if not best:
            continue
        needs_merge = best.get("acodec") in (None, "none")
        size = _estimated_size(best, duration)
        if size and needs_merge and audio_size:
            size += audio_size
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
                "needs_merge": bool(needs_merge),
                "recommended": False,
            }
        )

    if not options:
        # 部分站点不返回 formats 列表，只给一条直链，交给 yt-dlp 自行择优
        options.append(
            {
                "id": "video-best",
                "label": "最佳画质",
                "note": "由解析器自动选择",
                "kind": "video",
                "height": None,
                "ext": "mp4",
                "filesize": None,
                "filesize_text": "",
                "needs_merge": True,
                "recommended": True,
            }
        )
    else:
        preferred = next((o for o in options if o["height"] == 1080), options[0])
        preferred["recommended"] = True

    if audio_formats or options:
        options.append(
            {
                "id": AUDIO_OPTION_ID,
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

    return options


def _friendly_error(message: str) -> str:
    text = message.lower()
    if "unsupported url" in text:
        return "暂不支持该网站，换一个链接试试"
        # yt-dlp 没有匹配到对应的解析器
    if "private" in text or "login" in text or "sign in" in text or "cookies" in text or "not a bot" in text:
        return "该视频需要登录或为私密内容，当前无法解析。可换一条公开链接，或后续在设置中导入 cookies"
    if "no video formats" in text or "initial state" in text or "412" in text:
        return "该平台暂时拦截了解析请求，请稍后重试"
    if "not available" in text or "removed" in text or "404" in text:
        return "视频不存在或已被删除"
    if "geo" in text and "restrict" in text:
        return "该视频有地区限制，无法解析"
    if "timed out" in text or "timeout" in text:
        return "解析超时，请稍后重试"
    return "解析失败，请检查链接是否正确或稍后重试"


def parse_video(url: str) -> dict[str, Any]:
    if is_bilibili(url):
        try:
            return build_bilibili_info(url)
        except BiliError as exc:
            raise ParseError(str(exc)) from exc
        except requests.RequestException as exc:
            raise ParseError("B 站接口请求失败，请稍后重试") from exc

    opts = _base_opts(url) | {"skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            raw = ydl.extract_info(url, download=False)
            info = ydl.sanitize_info(raw)
    except yt_dlp.utils.DownloadError as exc:
        raise ParseError(_friendly_error(str(exc))) from exc
    except Exception as exc:  # 解析器内部异常形态各异，统一兜底
        raise ParseError(_friendly_error(str(exc))) from exc

    if not info:
        raise ParseError("没有解析到视频内容")

    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise ParseError("该链接下没有可下载的视频")
        info = entries[0]

    extractor = info.get("extractor_key") or info.get("extractor") or ""
    return {
        "url": info.get("webpage_url") or url,
        "title": info.get("title") or "未命名视频",
        "thumbnail": info.get("thumbnail"),
        "duration": int(info["duration"]) if info.get("duration") else None,
        "duration_text": format_duration(info.get("duration")),
        "uploader": info.get("uploader") or info.get("channel") or info.get("creator") or "",
        "platform": PLATFORM_ALIASES.get(extractor, extractor),
        "view_count": info.get("view_count"),
        "options": build_quality_options(info),
    }


def build_download_opts(
    url: str,
    option_id: str,
    out_dir: Path,
    progress_hooks: list[Callable[[dict], None]],
    postprocessor_hooks: list[Callable[[dict], None]],
) -> dict[str, Any]:
    opts = _base_opts(url) | {
        "outtmpl": str(out_dir / "%(title).60s.%(ext)s"),
        "windowsfilenames": True,
        "overwrites": True,
        "progress_hooks": progress_hooks,
        "postprocessor_hooks": postprocessor_hooks,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
    }

    if option_id == AUDIO_OPTION_ID:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
        return opts

    match = re.fullmatch(r"video-(\d+)", option_id)
    if match:
        height = int(match.group(1))
        # 优先 H.264：AV1/VP9 体积更小，但微信、旧手机和部分播放器放不出来
        opts["format"] = (
            f"bestvideo[height<={height}][vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]"
            f"/bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]"
            f"/bestvideo[height<={height}]+bestaudio"
            f"/best[height<={height}]/best"
        )
    else:
        opts["format"] = (
            "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
        )

    opts["merge_output_format"] = "mp4"
    return opts


def resolve_output_path(info: dict[str, Any], out_dir: Path) -> Path | None:
    """定位最终产物。

    合并与转码会改变扩展名，prepare_filename 的结果并不可靠，
    优先读 requested_downloads 里的真实 filepath，拿不到再回退到扫目录。
    """
    for item in info.get("requested_downloads") or []:
        candidate = item.get("filepath") or item.get("_filename")
        if candidate and Path(candidate).exists():
            return Path(candidate)

    files = [p for p in out_dir.glob("*") if p.is_file() and not p.name.endswith(".part")]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_size)


def download_video(url: str, option_id: str, out_dir: Path, on_progress, on_stage) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    if is_bilibili(url):
        try:
            return download_bilibili(url, option_id, out_dir, on_progress, on_stage)
        except BiliError as exc:
            raise ParseError(str(exc)) from exc
        except requests.RequestException as exc:
            raise ParseError("B 站视频下载失败，请稍后重试") from exc

    opts = build_download_opts(url, option_id, out_dir, [on_progress], [on_stage])

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise ParseError(_friendly_error(str(exc))) from exc

    path = resolve_output_path(info or {}, out_dir)
    if not path:
        raise ParseError("下载完成但未找到输出文件，请重试")
    return path
