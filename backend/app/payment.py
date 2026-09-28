"""支付与会员管理：Stripe Checkout 与 mock 双模式，共用同一套落库逻辑。

mock 模式：本地模拟支付，无需 Stripe 账号与外网，离线即可跑通全链路。
stripe 模式：真实 Stripe Checkout + webhook 回调，需外网 + 测试密钥。

幂等（防重复付款）三层保障：
  1. 创建 Checkout Session 传 idempotency_key（唯一订单号），网络重试不会重复建单；
  2. webhook_events 表以 event_id 主键去重，Stripe 重发同一事件直接跳过；
  3. memberships.stripe_session_id 唯一约束，同一支付会话只落库一次。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db
from .config import (
    MEMBERSHIP_DAYS,
    PAYMENT_MODE,
    SITE_URL,
    STRIPE_PRICE_ID,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)

PLAN_ID = "pro"
PLAN_NAME = "Pro 会员"


class PaymentError(RuntimeError):
    """支付相关业务异常，message 可直接展示给用户。"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_stripe_mode() -> bool:
    return PAYMENT_MODE == "stripe"


def _get_stripe():
    if not STRIPE_SECRET_KEY:
        raise PaymentError("尚未配置 STRIPE_SECRET_KEY，无法使用真实支付")
    import stripe

    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def create_checkout(user_id: str) -> dict[str, str]:
    """创建支付订单，返回可跳转的支付地址。order_id 用作幂等键，避免重试重复建单。"""
    order_id = uuid.uuid4().hex
    success_url = f"{SITE_URL}/?payment=success"
    cancel_url = f"{SITE_URL}/?payment=cancel"

    if not is_stripe_mode():
        return {
            "checkout_url": f"{SITE_URL}/?mock_payment=1",
            "mode": "mock",
            "order_id": order_id,
        }

    if not STRIPE_PRICE_ID:
        raise PaymentError("尚未配置 STRIPE_PRICE_ID（Stripe 里的价格对象 ID）")

    stripe = _get_stripe()
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=user_id,
        metadata={"user_id": user_id, "order_id": order_id},
        idempotency_key=order_id,
    )
    if not session.url:
        raise PaymentError("支付链接生成失败，请稍后重试")
    return {"checkout_url": session.url, "mode": "stripe", "order_id": order_id}


def get_membership(user_id: str) -> dict[str, Any]:
    """读取会员状态；即使已过期也返回记录，active 由到期时间实时判定。"""
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM memberships WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return {"active": False, "plan": "", "starts_at": "", "expires_at": "", "expires_text": ""}

    now = _now()
    expires = datetime.fromisoformat(row["expires_at"])
    active = row["status"] == "active" and expires > now
    return {
        "active": active,
        "plan": row["plan"],
        "starts_at": row["starts_at"],
        "expires_at": row["expires_at"],
        "expires_text": expires.strftime("%Y-%m-%d"),
    }


def grant_membership(
    user_id: str,
    plan: str = PLAN_ID,
    stripe_session_id: str = "",
    days: int = MEMBERSHIP_DAYS,
) -> dict[str, Any]:
    """开通会员。若已有未过期会员则从当前到期时间顺延，否则从现在起算。"""
    now = _now()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT expires_at FROM memberships WHERE user_id=? AND status='active'",
            (user_id,),
        ).fetchone()

        start = now
        if row:
            try:
                existing = datetime.fromisoformat(row["expires_at"])
                if existing > now:
                    start = existing
            except ValueError:
                pass

        expires = start + timedelta(days=days)
        now_iso = now.isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO memberships
                (user_id, plan, status, starts_at, expires_at, stripe_session_id, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                plan=excluded.plan,
                status='active',
                starts_at=excluded.starts_at,
                expires_at=excluded.expires_at,
                stripe_session_id=excluded.stripe_session_id,
                updated_at=excluded.updated_at
            """,
            (
                user_id,
                plan,
                "active",
                start.isoformat(timespec="seconds"),
                expires.isoformat(timespec="seconds"),
                stripe_session_id or None,
                now_iso,
                now_iso,
            ),
        )
    return get_membership(user_id)


def mark_event_processed(event_id: str) -> bool:
    """幂等去重：记录已处理的 webhook 事件，返回是否为首次处理。"""
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO webhook_events(event_id, processed_at) VALUES(?,?)",
            (event_id, _now().isoformat(timespec="seconds")),
        )
        return cur.rowcount == 1


def handle_checkout_completed(session_id: str, user_id: str) -> dict[str, Any]:
    """处理支付完成事件。双重幂等：同一支付会话只落库一次。"""
    with db.connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM memberships WHERE stripe_session_id=?", (session_id,)
        ).fetchone()
    if exists:
        return get_membership(user_id)
    return grant_membership(user_id, plan=PLAN_ID, stripe_session_id=session_id)


def revoke_membership(user_id: str) -> None:
    """降级为免费用户：把会员状态置为 expired，到期时间改为当前。

    触发场景：订阅取消/到期（customer.subscription.deleted）、扣款失败
    （invoice.payment_failed）。降级后 quota.is_member 实时判定为 False，
    免费额度限制立即恢复生效，无需额外定时任务。
    """
    now = _now()
    with db.connect() as conn:
        conn.execute(
            "UPDATE memberships SET status='expired', expires_at=?, updated_at=? WHERE user_id=?",
            (now.isoformat(timespec="seconds"), now.isoformat(timespec="seconds"), user_id),
        )


def verify_webhook(payload: bytes, sig_header: str):
    """校验 webhook 签名并返回事件对象（仅在 stripe 模式使用）。"""
    if not STRIPE_WEBHOOK_SECRET:
        raise PaymentError("尚未配置 STRIPE_WEBHOOK_SECRET")
    import stripe

    try:
        return stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.SignatureVerificationError as exc:
        raise PaymentError("Webhook 签名校验失败") from exc
    except ValueError as exc:
        raise PaymentError("Webhook 载荷解析失败") from exc
