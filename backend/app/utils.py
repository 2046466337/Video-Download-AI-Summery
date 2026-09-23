"""展示层格式化辅助函数。"""

from __future__ import annotations


def format_duration(seconds: float | int | None) -> str:
    if not seconds:
        return ""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_size(num_bytes: float | int | None) -> str:
    if not num_bytes:
        return ""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return ""


def format_speed(bytes_per_second: float | int | None) -> str:
    if not bytes_per_second:
        return ""
    return f"{format_size(bytes_per_second)}/s"


def format_eta(seconds: float | int | None) -> str:
    if not seconds or seconds < 0:
        return ""
    total = int(seconds)
    if total < 60:
        return f"{total} 秒"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} 分 {secs} 秒"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} 小时 {minutes} 分"
