"""会员与支付 API 路由。

独立于下载/总结路由，用单独 APIRouter 挂载，遵循「付费不污染主链路」约定。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth_routes import get_current_user
from .payment import (
    PaymentError,
    create_checkout,
    get_membership,
    grant_membership,
    handle_checkout_completed,
    is_stripe_mode,
    mark_event_processed,
    revoke_membership,
    verify_webhook,
)
from .payment_schemas import CheckoutResponse, MembershipState

payment_router = APIRouter(prefix="/api")


@payment_router.post("/payments/checkout", response_model=CheckoutResponse)
async def checkout(user: dict = Depends(get_current_user)) -> CheckoutResponse:
    try:
        result = create_checkout(user["id"])
    except PaymentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CheckoutResponse(**result)


@payment_router.get("/membership", response_model=MembershipState)
async def membership(user: dict = Depends(get_current_user)) -> MembershipState:
    return MembershipState(**get_membership(user["id"]))


@payment_router.post("/payments/mock/complete", response_model=MembershipState)
async def mock_complete(user: dict = Depends(get_current_user)) -> MembershipState:
    """mock 模式专用：模拟支付成功，走与真实 webhook 相同的落库逻辑。"""
    if is_stripe_mode():
        raise HTTPException(status_code=400, detail="当前为 Stripe 真实模式，此接口不可用")
    return MembershipState(**grant_membership(user["id"]))


@payment_router.post("/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict:
    """Stripe 回调：验签 + 幂等去重后落库。"""
    if not is_stripe_mode():
        raise HTTPException(status_code=400, detail="当前未启用 Stripe 模式")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = verify_webhook(payload, sig_header)
    except PaymentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if event.type == "checkout.session.completed":
        if not mark_event_processed(event.id):
            return {"received": True}  # 重复事件，幂等跳过
        session = event.data.object
        user_id = _extract_user_id(session)
        if not user_id:
            raise HTTPException(status_code=400, detail="支付事件缺少用户标识")
        handle_checkout_completed(session.id, user_id)

    # 订阅到期/取消 或 扣款失败 → 降级为免费用户，恢复额度限制
    elif event.type in ("customer.subscription.deleted", "invoice.payment_failed"):
        if not mark_event_processed(event.id):
            return {"received": True}
        obj = event.data.object
        user_id = _extract_user_id(obj)
        if user_id:
            revoke_membership(user_id)

    return {"received": True}


def _extract_user_id(obj) -> str:
    """从 Stripe 对象里安全取出 user_id。

    Stripe 返回的 metadata 是 StripeObject（不是 dict），必须 .to_dict() 转成
    普通字典后才能用 .get()。user_id 优先取 metadata.user_id，其次 client_reference_id。
    """
    metadata = getattr(obj, "metadata", None)
    meta = metadata.to_dict() if metadata is not None else {}
    user_id = meta.get("user_id") or ""
    if not user_id:
        user_id = getattr(obj, "client_reference_id", None) or ""
    return user_id
