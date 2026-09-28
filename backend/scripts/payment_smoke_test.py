"""会员支付链路冒烟测试。

覆盖：注册 → 登录 → me → 会员状态（空）→ 创建订单（mock）→ 模拟支付 → 会员生效
      → 续费顺延 → 未登录 401 → webhook 在 mock 模式被拒。

用法（需先启动后端）：
    backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    然后另开终端：
    backend/.venv/Scripts/python.exe scripts/payment_smoke_test.py
"""

from __future__ import annotations

import os
import sys
import uuid

import requests

BASE = os.environ.get("PAYMENT_TEST_BASE", "http://127.0.0.1:8000").rstrip("/")


def _email() -> str:
    return f"smoke_{uuid.uuid4().hex[:10]}@example.com"


def check(name: str, cond: bool, detail: str = "") -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        sys.exit(1)


def main() -> None:
    # Windows 控制台默认 GBK，避免中文/符号编码崩溃
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    email = _email()
    password = "password123"

    # 1. 注册
    r = requests.post(f"{BASE}/api/auth/register", json={"email": email, "password": password})
    check("注册返回 200", r.status_code == 200, str(r.status_code))
    token = r.json()["token"]
    check("注册返回 token", bool(token))

    # 2. 重复注册应 409
    r = requests.post(f"{BASE}/api/auth/register", json={"email": email, "password": password})
    check("重复注册返回 409", r.status_code == 409, str(r.status_code))

    # 3. 登录
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    check("登录返回 200", r.status_code == 200, str(r.status_code))

    # 4. 错误密码 401
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": "wrongpass"})
    check("错误密码返回 401", r.status_code == 401, str(r.status_code))

    headers = {"Authorization": f"Bearer {token}"}

    # 5. me
    r = requests.get(f"{BASE}/api/auth/me", headers=headers)
    check("me 返回 200", r.status_code == 200, str(r.status_code))
    check("me 邮箱一致", r.json()["email"] == email)

    # 6. 未登录访问会员状态 401
    r = requests.get(f"{BASE}/api/membership")
    check("未登录访问会员状态 401", r.status_code == 401, str(r.status_code))

    # 7. 初始会员状态为空
    r = requests.get(f"{BASE}/api/membership", headers=headers)
    check("初始会员 active=false", r.json()["active"] is False)

    # 8. 创建订单（mock 模式）
    r = requests.post(f"{BASE}/api/payments/checkout", headers=headers)
    check("创建订单返回 200", r.status_code == 200, str(r.status_code))
    body = r.json()
    check("订单模式为 mock", body["mode"] == "mock", body.get("mode", ""))

    # 9. 模拟支付
    r = requests.post(f"{BASE}/api/payments/mock/complete", headers=headers)
    check("模拟支付返回 200", r.status_code == 200, str(r.status_code))
    first = r.json()
    check("模拟支付后 active=true", first["active"] is True)
    check("有到期时间", bool(first["expires_text"]), first["expires_text"])

    # 10. 续费顺延：再次购买应从当前到期时间顺延
    r = requests.post(f"{BASE}/api/payments/mock/complete", headers=headers)
    check("再次模拟支付返回 200", r.status_code == 200, str(r.status_code))
    second = r.json()
    check(
        "续费顺延（到期时间后移）",
        second["expires_at"] >= first["expires_at"],
        f"{first['expires_at']} -> {second['expires_at']}",
    )

    # 11. webhook 在 mock 模式被拒
    r = requests.post(f"{BASE}/api/webhooks/stripe", data=b"{}")
    check("mock 模式 webhook 返回 400", r.status_code == 400, str(r.status_code))

    print("\n全部通过")


if __name__ == "__main__":
    main()
