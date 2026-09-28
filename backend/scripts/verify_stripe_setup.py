"""Stripe 配置体检：一键检查真实支付是否已就绪。

用法（需先填好 .env 里的三个 Stripe 密钥）：
    backend/.venv/Scripts/python.exe scripts/verify_stripe_setup.py

检查项：
  1. 三个密钥是否已配置
  2. sk_test 密钥是否有效（调用 Stripe API 拿账户信息验证）
  3. price_id 是否存在、币种与金额
  4. 提示 webhook 转发是否已启动
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import (  # noqa: E402
    PAYMENT_MODE,
    SITE_URL,
    STRIPE_PRICE_ID,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)


def check(name: str, cond: bool, detail: str = "") -> bool:
    mark = "OK  " if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail else ""))
    return cond


def _mask(key: str) -> str:
    return key[:12] + "..." if key else "未配置"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print(f"当前支付模式：{PAYMENT_MODE}")
    print()

    ok = check("PAYMENT_MODE 为 stripe", PAYMENT_MODE == "stripe", PAYMENT_MODE)
    ok = check("STRIPE_SECRET_KEY 已配置", bool(STRIPE_SECRET_KEY), _mask(STRIPE_SECRET_KEY)) and ok
    ok = (
        check("STRIPE_WEBHOOK_SECRET 已配置", bool(STRIPE_WEBHOOK_SECRET), _mask(STRIPE_WEBHOOK_SECRET))
        and ok
    )
    ok = check("STRIPE_PRICE_ID 已配置", bool(STRIPE_PRICE_ID), STRIPE_PRICE_ID or "未配置") and ok
    print(f"        SITE_URL = {SITE_URL}")
    print()

    # 验证密钥有效性（真正调一次 Stripe API）
    if STRIPE_SECRET_KEY:
        try:
            import stripe

            stripe.api_key = STRIPE_SECRET_KEY
            account = stripe.Account.retrieve()
            ok = check("sk_test 密钥有效（能连上 Stripe）", True, f"账户 ID: {account.id}") and ok
        except Exception as exc:  # noqa: BLE001
            ok = check("sk_test 密钥有效（能连上 Stripe）", False, str(exc)) and ok
    print()

    # 验证 price 是否存在
    if STRIPE_SECRET_KEY and STRIPE_PRICE_ID:
        try:
            import stripe

            stripe.api_key = STRIPE_SECRET_KEY
            price = stripe.Price.retrieve(STRIPE_PRICE_ID)
            if price.recurring:
                desc = f"{price.unit_amount} {price.currency} / 循环订阅"
            else:
                desc = f"{price.unit_amount} {price.currency} / 一次性"
            ok = check("price_id 有效", True, desc) and ok
        except Exception as exc:  # noqa: BLE001
            ok = check("price_id 有效", False, str(exc)) and ok
    print()

    # 提示 webhook
    print("【最后一步】确认 webhook 转发正在运行（另开一个终端执行）：")
    print("  stripe listen --forward-to http://127.0.0.1:8000/api/webhooks/stripe")
    print("  然后把它打印出的 whsec_xxx 填进 .env 的 STRIPE_WEBHOOK_SECRET（若还没填）。")
    print()

    if ok:
        print("✅ 配置就绪，可以开始真实支付测试了")
    else:
        print("❌ 还有配置未就绪，请按上面的 FAIL 项补全后重跑本脚本")


if __name__ == "__main__":
    main()
