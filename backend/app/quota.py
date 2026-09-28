"""免费额度与权益拦截：每日下载 5 次、AI 总结 3 次；会员不受限。

额度主体：登录用户用 user_id，匿名用户用客户端标识 client_id。
日期按 Asia/Shanghai（用户所在地）计算，每日 0 点自动重置。
会员状态实时判定（到期自动降级为免费用户，额度自然恢复生效），
因此「会员到期 → 恢复限制」无需额外定时任务，由本模块即时完成。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import db
from .payment import get_membership

FREE_DOWNLOAD_LIMIT = 5
FREE_SUMMARY_LIMIT = 3

# 中国标准时间 UTC+8（无夏令时），避免依赖 tzdata 包（Windows 下 zoneinfo 需要它）
CST = timezone(timedelta(hours=8))


class QuotaError(RuntimeError):
    """额度不足，message 可直接展示给用户。"""


def _today() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d")


def is_member(user: dict | None) -> bool:
    """是否为有效会员。实时判定：会员到期后自动返回 False。"""
    if not user:
        return False
    try:
        return bool(get_membership(user["id"])["active"])
    except Exception:  # noqa: BLE001 - 会员判定失败按免费用户处理
        return False


def resolve_subject(user: dict | None, client_id: str) -> str:
    """额度主体：登录用户优先，否则用客户端标识。"""
    if user:
        return f"u:{user['id']}"
    cid = (client_id or "").strip()
    if cid:
        return f"c:{cid}"
    return ""


def try_consume(user: dict | None, client_id: str, kind: str) -> None:
    """检查并原子扣减额度。会员跳过；额度不足抛 QuotaError。

    kind ∈ {"download", "summary"}。
    用「条件 UPDATE」保证并发下不会超限：只有当当前计数 < 上限时才 +1。
    """
    if is_member(user):
        return
    subject = resolve_subject(user, client_id)
    if not subject:
        # 无法识别主体（正常前端总会带 client_id），放行但无法计数
        return

    if kind == "download":
        col, limit, name = "downloads", FREE_DOWNLOAD_LIMIT, "下载"
    else:
        col, limit, name = "summaries", FREE_SUMMARY_LIMIT, "AI 总结"

    today = _today()
    with db.connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO usage_counters(subject, date, downloads, summaries) "
            "VALUES(?,?,0,0)",
            (subject, today),
        )
        cur = conn.execute(
            f"UPDATE usage_counters SET {col} = {col} + 1 "
            f"WHERE subject = ? AND date = ? AND {col} < ?",
            (subject, today, limit),
        )
        if cur.rowcount == 1:
            return

    raise QuotaError(f"今日免费{name}次数已用完，升级 Pro 解锁不限次数")


def usage_snapshot(user: dict | None, client_id: str) -> dict:
    """返回当前主体的今日已用/上限，供前端展示（可选）。"""
    subject = resolve_subject(user, client_id)
    if not subject:
        return {"downloads_used": 0, "downloads_limit": FREE_DOWNLOAD_LIMIT,
                "summaries_used": 0, "summaries_limit": FREE_SUMMARY_LIMIT,
                "is_member": is_member(user)}
    today = _today()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT downloads, summaries FROM usage_counters WHERE subject=? AND date=?",
            (subject, today),
        ).fetchone()
    return {
        "downloads_used": row["downloads"] if row else 0,
        "downloads_limit": FREE_DOWNLOAD_LIMIT,
        "summaries_used": row["summaries"] if row else 0,
        "summaries_limit": FREE_SUMMARY_LIMIT,
        "is_member": is_member(user),
    }
