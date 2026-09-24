"""多平台字幕提取。

AI 视频总结的第一步是拿到「可读的文本」。这里统一从各平台提取现成字幕，
输出规范化的时间轴列表 `[{start, end, text}]`（单位为秒）。

平台分流策略与下载主链路一致、但完全独立：
- 哔哩哔哩：走 `x/v2/dm/view` 公开接口拿字幕 JSON（同时含人工 CC 字幕与 AI 字幕，复用 bilibili_adapter 的 ID 解析与 view 数据）
- 抖音：无公开字幕接口，返回空列表
- 其余（YouTube / TikTok 等上千站点）：走 yt-dlp 的 subtitles / automatic_captions 元数据

本模块只做「读取」，不落盘、不下载媒体、不污染下载目录，对已有功能零影响。
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import requests
import yt_dlp

from .bilibili_adapter import API_HEADERS, extract_ids, fetch_view, is_bilibili
from .config import FFMPEG_LOCATION, SOCKET_TIMEOUT
from .douyin_adapter import is_douyin
from .site_profiles import profile_for

# 字幕语言优先级：中文 > 英文 > 其他。人工字幕优先于自动字幕。
_PREFERRED_LANGS = (
    "zh-cn",
    "zh-hans",
    "zh",
    "zh-hant",
    "zh-tw",
    "zho",
    "chi",
    "en",
    "en-us",
    "en-gb",
    "eng",
)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_TIMEOUT = (15, 60)


class SubtitleError(RuntimeError):
    """字幕获取失败，message 可直接展示。"""


def extract_subtitles(url: str) -> list[dict[str, Any]]:
    """提取视频字幕，返回 `[{start, end, text}]`（秒）。无字幕返回空列表。

    策略：平台专用字幕 API 优先，其余站点走 yt-dlp 的内嵌/自动字幕。
    """
    if is_bilibili(url):
        return _bilibili_subtitles(url)
    if is_douyin(url):
        # 抖音没有公开字幕接口，短视频通常也无字幕，返回空列表
        return []
    return _ytdlp_subtitles(url)


def transcript_to_text(cues: list[dict[str, Any]]) -> str:
    """把字幕轴转成带时间戳的纯文本，供 LLM 总结时定位章节。"""
    lines: list[str] = []
    for cue in cues:
        start = float(cue.get("start") or 0)
        text = str(cue.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"[{_fmt_ts(start)}] {text}")
    return "\n".join(lines)


# ------------------------------------------------------------------ 工具

def _fmt_ts(seconds: float) -> str:
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _lang_key(lang: str) -> str:
    return (lang or "").strip().lower().replace("_", "-")


def _pick_best_subtitles(sub_map: dict[str, Any] | None) -> list[dict[str, Any]]:
    """从 `{lang: [entries]}` 里挑出一组字幕，返回该语言的 entry 列表。"""
    if not sub_map:
        return []
    for preferred in _PREFERRED_LANGS:
        for lang, entries in sub_map.items():
            if _lang_key(lang) == preferred and entries:
                return entries
    # 兜底：取第一个非空语言
    for lang, entries in sub_map.items():
        if entries:
            return entries
    return []


def _pick_entry(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """优先选 vtt / srt（解析最稳），否则选第一个。"""
    if not entries:
        return {}
    for ext in ("vtt", "srt"):
        for entry in entries:
            if (entry.get("ext") or "").lower() == ext:
                return entry
    return entries[0]


def _download_text(url: str, referer: str = "") -> str:
    headers = {"User-Agent": _BROWSER_UA}
    if referer:
        headers["Referer"] = referer
    response = requests.get(url, headers=headers, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.text


# ------------------------------------------------------------------ 解析器

def _parse_vtt(raw: str) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    # 时间轴行：MM:SS.mmm --> MM:SS.mmm 或 HH:MM:SS.mmm
    ts_re = re.compile(
        r"((?:\d{1,2}:)?\d{1,2}:\d{2})[.,](\d{1,3})\s*-->\s*"
        r"((?:\d{1,2}:)?\d{1,2}:\d{2})[.,](\d{1,3})"
    )
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        match = ts_re.search(lines[i])
        if match:
            start = _ts_to_seconds(match.group(1), match.group(2))
            end = _ts_to_seconds(match.group(3), match.group(4))
            texts: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
                texts.append(_strip_vtt_tags(lines[i]))
                i += 1
            text = " ".join(t for t in texts if t).strip()
            if text:
                cues.append({"start": start, "end": end, "text": text})
            continue
        i += 1
    return cues


def _parse_srt(raw: str) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    ts_re = re.compile(
        r"((?:\d{1,2}:)?\d{1,2}:\d{2})[.,](\d{1,3})\s*-->\s*"
        r"((?:\d{1,2}:)?\d{1,2}:\d{2})[.,](\d{1,3})"
    )
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        match = ts_re.search(lines[i])
        if match:
            start = _ts_to_seconds(match.group(1), match.group(2))
            end = _ts_to_seconds(match.group(3), match.group(4))
            texts: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
                texts.append(lines[i].strip())
                i += 1
            text = " ".join(t for t in texts if t).strip()
            if text:
                cues.append({"start": start, "end": end, "text": text})
            continue
        i += 1
    return cues


def _parse_json3(raw: str) -> list[dict[str, Any]]:
    """YouTube 自动字幕 JSON3 格式。"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    cues: list[dict[str, Any]] = []
    for event in data.get("events") or []:
        segs = event.get("segs") or []
        if not segs:
            continue
        text = "".join(seg.get("utf8") or "" for seg in segs).strip()
        if not text:
            continue
        start = float(event.get("tStartMs") or 0) / 1000
        duration = float(event.get("dDurationMs") or 0) / 1000
        cues.append({"start": start, "end": start + duration, "text": text})
    return cues


def _parse_bilibili_json(raw: str) -> list[dict[str, Any]]:
    """B 站字幕 JSON：body 里 from/to 为秒，content 为文本。"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    cues: list[dict[str, Any]] = []
    for item in data.get("body") or []:
        text = str(item.get("content") or "").strip()
        if not text:
            continue
        cues.append(
            {
                "start": float(item.get("from") or 0),
                "end": float(item.get("to") or 0),
                "text": text,
            }
        )
    return cues


def _strip_vtt_tags(line: str) -> str:
    # 去掉 WebVTT 里的内联样式标签（<c>, <00:00:00.000> 等）
    return re.sub(r"<[^>]+>", "", line).strip()


def _ts_to_seconds(clock: str, millis: str) -> float:
    parts = clock.split(":")
    parts = [int(p) for p in parts]
    if len(parts) == 2:
        h, m = 0, parts[0]
        s = parts[1]
    else:
        h, m, s = parts[0], parts[1], parts[2]
    return h * 3600 + m * 60 + s + int(millis.ljust(3, "0")) / 1000


# ------------------------------------------------------------------ B 站

def _bilibili_subtitles(url: str) -> list[dict[str, Any]]:
    bvid, aid, page = extract_ids(url)
    if not bvid and not aid:
        raise SubtitleError("无法从链接中识别 B 站视频 ID")
    view = fetch_view(bvid, aid)
    pages = view.get("pages") or []
    page_info = pages[page - 1] if 0 < page <= len(pages) else (pages[0] if pages else {})
    cid = page_info.get("cid") or view.get("cid")
    if not cid:
        return []

    # dm/view 接口能同时返回人工 CC 字幕与 AI 字幕（AI 字幕 lan 带 ai- 前缀），
    # 相比 x/player/v2 覆盖更多视频（尤其只有 AI 字幕、没有人工字幕的）。
    aid = view.get("aid") or aid
    if not aid:
        return []
    params: dict[str, Any] = {"aid": aid, "oid": int(cid), "type": 1}

    response = requests.get(
        "https://api.bilibili.com/x/v2/dm/view", headers=API_HEADERS, params=params, timeout=_TIMEOUT
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in (0, None):
        return []
    subtitles = (((payload.get("data") or {}).get("subtitle")) or {}).get("subtitles") or []
    if not subtitles:
        return []

    # 优先人工中文字幕，其次 AI 中文字幕，最后取第一个
    chosen = next(
        (s for s in subtitles if _lang_key(s.get("lan") or "") in ("zh-cn", "zh-hans", "zh")),
        next(
            (s for s in subtitles if _lang_key(s.get("lan") or "") == "ai-zh"),
            subtitles[0],
        ),
    )
    sub_url = chosen.get("subtitle_url") or chosen.get("url") or ""
    if not sub_url:
        return []
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url
    if sub_url.startswith("http://"):
        sub_url = "https://" + sub_url[7:]
    raw = _download_text(sub_url, referer="https://www.bilibili.com/")
    return _parse_bilibili_json(raw)


# ------------------------------------------------------------------ yt-dlp 站点

def _base_opts(url: str) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": SOCKET_TIMEOUT,
        "retries": 2,
        "ignoreerrors": False,
    }
    if FFMPEG_LOCATION:
        opts["ffmpeg_location"] = FFMPEG_LOCATION
    return opts | profile_for(url)


def _ytdlp_subtitles(url: str) -> list[dict[str, Any]]:
    try:
        with yt_dlp.YoutubeDL(_base_opts(url)) as ydl:
            raw = ydl.extract_info(url, download=False)
            info = ydl.sanitize_info(raw)
    except Exception as exc:  # noqa: BLE001 - 解析失败即视为无字幕
        raise SubtitleError(f"视频解析失败，无法获取字幕：{exc}") from exc

    if not info:
        raise SubtitleError("没有解析到视频内容")

    manual = _pick_best_subtitles(info.get("subtitles"))
    automatic = _pick_best_subtitles(info.get("automatic_captions"))
    # 人工字幕优先，其次自动字幕
    entries = manual or automatic
    if not entries:
        return []

    entry = _pick_entry(entries)
    sub_url = entry.get("url") or ""
    if not sub_url:
        return []

    # YouTube 自动字幕默认 json3，可通过替换 fmt 得到 vtt，解析更稳
    if "fmt=json3" in sub_url and "youtube" in (urlparse(url).hostname or ""):
        sub_url = sub_url.replace("fmt=json3", "fmt=vtt")

    ext = (entry.get("ext") or "").lower()
    try:
        raw = _download_text(sub_url)
    except requests.RequestException as exc:
        raise SubtitleError(f"字幕下载失败：{exc}") from exc

    if ext == "vtt" or sub_url.endswith("vtt") or raw.lstrip().startswith("WEBVTT"):
        return _parse_vtt(raw)
    if ext == "srt" or sub_url.endswith("srt"):
        return _parse_srt(raw)
    if ext == "json3" or sub_url.endswith("json3"):
        return _parse_json3(raw)

    # 未知格式：按内容嗅探
    if raw.lstrip().startswith("WEBVTT"):
        return _parse_vtt(raw)
    if "-->" in raw[:2000]:
        return _parse_srt(raw)
    return _parse_json3(raw)
