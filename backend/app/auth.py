"""邮箱 + 密码注册登录与 JWT 鉴权。

刻意保持轻量：密码用标准库 PBKDF2（随机盐 + 恒时比较），
JWT 用 PyJWT（HS256），不引入 bcrypt/argon2 的编译依赖。
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from . import db
from .config import DATA_DIR

# 密钥：优先环境变量 JWT_SECRET；否则自动生成并持久化，保证重启后 token 不失效
_JWT_SECRET_FILE = DATA_DIR / ".jwt_secret"
TOKEN_TTL_HOURS = 24 * 7
PBKDF2_ITERATIONS = 310_000

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(RuntimeError):
    """鉴权相关业务异常，message 可直接展示给用户。"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_jwt_secret() -> str:
    env_secret = os.getenv("JWT_SECRET", "").strip()
    if env_secret:
        return env_secret
    if _JWT_SECRET_FILE.exists():
        existing = _JWT_SECRET_FILE.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    secret = secrets.token_urlsafe(48)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _JWT_SECRET_FILE.write_text(secret, encoding="utf-8")
    try:
        os.chmod(_JWT_SECRET_FILE, 0o600)
    except OSError:
        pass
    return secret


JWT_SECRET = _load_jwt_secret()


# ------------------------------------------------------------------ 密码

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


# ------------------------------------------------------------------ JWT

def create_token(user_id: str, email: str) -> str:
    now = _now()
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AuthError("登录已过期或无效，请重新登录") from exc


# ------------------------------------------------------------------ 用户

def create_user(email: str, password: str) -> dict[str, Any]:
    user_id = uuid.uuid4().hex
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO users(id, email, password_hash, created_at) VALUES(?,?,?,?)",
            (user_id, email, hash_password(password), _now().isoformat(timespec="seconds")),
        )
    return {"id": user_id, "email": email}


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None
