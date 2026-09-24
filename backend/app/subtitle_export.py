"""字幕导出（下载）格式化。

把字幕轴 `[{start, end, text}]`（秒）格式化为 SRT / VTT / Markdown 文本，
供字幕下载接口以 attachment 方式下发。仅导出「原始字幕」，不涉及任何翻译。

独立于 subtitles.py（提取）与 summarizer.py（LLM 生成），遵循开闭原则：
新增能力不修改既有模块。
"""

from __future__ import annotations

import re
from typing import Any


def _srt_ts(seconds: float) -> str:
    """SRT 时间戳：HH:MM:SS,mmm。"""
    ms = max(0, int(round(float(seconds or 0) * 1000)))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _clock(seconds: float) -> str:
    """MM:SS 或 HH:MM:SS（Markdown 用）。"""
    total = max(0, int(float(seconds or 0)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _clean(cues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """过滤空文本，并保证 end >= start。"""
    cleaned: list[dict[str, Any]] = []
    for cue in cues or []:
        if not isinstance(cue, dict):
            continue
        text = str(cue.get("text") or "").strip()
        if not text:
            continue
        start = float(cue.get("start") or 0)
        end = float(cue.get("end") or start)
        if end < start:
            end = start
        cleaned.append({"start": start, "end": end, "text": text})
    return cleaned


def to_srt(cues: list[dict[str, Any]]) -> str:
    """生成 SRT 文本。"""
    blocks: list[str] = []
    for index, cue in enumerate(_clean(cues), start=1):
        blocks.append(
            f"{index}\n"
            f"{_srt_ts(cue['start'])} --> {_srt_ts(cue['end'])}\n"
            f"{cue['text']}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def to_vtt(cues: list[dict[str, Any]]) -> str:
    """生成 WebVTT 文本（时间戳用小数点毫秒）。"""
    blocks = ["WEBVTT", ""]
    for cue in _clean(cues):
        blocks.append(
            f"{_srt_ts(cue['start']).replace(',', '.')} --> "
            f"{_srt_ts(cue['end']).replace(',', '.')}\n"
            f"{cue['text']}"
        )
    return "\n\n".join(blocks) + "\n"


def to_markdown(cues: list[dict[str, Any]], title: str = "") -> str:
    """生成 Markdown 文本（带时间戳的行）。"""
    heading = (title or "视频").strip() or "视频"
    lines = [f"# 《{heading}》字幕", ""]
    for cue in _clean(cues):
        lines.append(f"[{_clock(cue['start'])}] {cue['text']}")
    return "\n".join(lines) + "\n"


def safe_filename(title: str) -> str:
    """清理标题，生成可用的文件名主干（不含扩展名）。"""
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", (title or "").strip()) or "字幕"
    return cleaned[:80]
