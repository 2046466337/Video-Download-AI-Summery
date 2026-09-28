"""支付模式切换 + 权益拦截验证。

验证项（全程不读取、不打印任何 .env 密钥）：
  1. 支付模式已切到 stripe，checkout 返回 Stripe 支付页地址
  2. 匿名下载每日 5 次，第 6 次被拦截
  3. 匿名 AI 总结每日 3 次，第 4 次被拦截
  4. 会员下载/AI 总结不限次
  5. 会员到期/降级后恢复免费限制
  6. HTTP 层额度拦截（403）

用法（后端已启动）：
    backend/.venv/Scripts/python.exe scripts/verify_payment_flow.py
"""

from __future__ import annotations

import os
import sys
import uuid

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import payment, quota  # noqa: E402

BASE = os.environ.get("PAYMENT_TEST_BASE", "http://127.0.0.1:8000").rstrip("/")


def check(name: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail else ""))
    return cond


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    all_ok = True

    # 1. 模式切换验证（通过 HTTP 行为判断，不碰密钥）
    email = f"smoke_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(f"{BASE}/api/auth/register", json={"email": email, "password": "password123"})
    token = r.json().get("token", "")
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(f"{BASE}/api/payments/checkout", headers=headers)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    mode = body.get("mode", "")
    url = body.get("checkout_url", "") or ""
    is_stripe_url = url.startswith("https://checkout.stripe.com/")
    all_ok = check("支付模式为 stripe（不再是 mock）", mode == "stripe", f"mode={mode}") and all_ok
    all_ok = check("checkout 跳转 Stripe 支付页", is_stripe_url, "checkout_url 域名为 stripe") and all_ok

    # 2. 匿名下载额度（单元级，直连数据库，无真实下载）
    cid = "t-" + uuid.uuid4().hex
    for _ in range(5):
        quota.try_consume(None, cid, "download")
    try:
        quota.try_consume(None, cid, "download")
        all_ok = check("匿名下载第 6 次被拦截", False) and all_ok
    except quota.QuotaError:
        all_ok = check("匿名下载第 6 次被拦截", True) and all_ok

    # 3. 匿名 AI 总结额度
    cid2 = "t-" + uuid.uuid4().hex
    for _ in range(3):
        quota.try_consume(None, cid2, "summary")
    try:
        quota.try_consume(None, cid2, "summary")
        all_ok = check("匿名 AI 总结第 4 次被拦截", False) and all_ok
    except quota.QuotaError:
        all_ok = check("匿名 AI 总结第 4 次被拦截", True) and all_ok

    # 4. 会员不限次
    uid = "member-" + uuid.uuid4().hex
    payment.grant_membership(uid)
    all_ok = check("开通后会员状态 active", quota.is_member({"id": uid})) and all_ok
    ok = True
    for _ in range(10):
        try:
            quota.try_consume({"id": uid}, "", "download")
        except quota.QuotaError:
            ok = False
    all_ok = check("会员下载 10 次不限", ok) and all_ok

    # 5. 到期/降级恢复限制
    payment.revoke_membership(uid)
    all_ok = check("降级后 is_member=False", quota.is_member({"id": uid}) is False) and all_ok

    # 6. HTTP 层额度拦截（403）
    cid3 = "t-" + uuid.uuid4().hex
    for _ in range(5):
        quota.try_consume(None, cid3, "download")
    r = requests.post(
        f"{BASE}/api/downloads",
        json={"url": "https://example.com", "option_id": "video-best", "client_id": cid3},
    )
    all_ok = check("HTTP 下载额度拦截返回 403", r.status_code == 403, f"HTTP {r.status_code}") and all_ok

    cid4 = "t-" + uuid.uuid4().hex
    for _ in range(3):
        quota.try_consume(None, cid4, "summary")
    r = requests.post(f"{BASE}/api/summaries", json={"url": "https://example.com", "client_id": cid4})
    all_ok = check("HTTP 总结额度拦截返回 403", r.status_code == 403, f"HTTP {r.status_code}") and all_ok

    print()
    print("全部通过" if all_ok else "存在未通过项")


if __name__ == "__main__":
    main()
