"""会员与支付出入参模型。"""

from __future__ import annotations

from pydantic import BaseModel


class CheckoutResponse(BaseModel):
    checkout_url: str
    mode: str  # mock | stripe
    order_id: str = ""


class MembershipState(BaseModel):
    active: bool
    plan: str = ""
    starts_at: str = ""
    expires_at: str = ""
    expires_text: str = ""
