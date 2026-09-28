"""用户注册/登录 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from .auth import (
    AuthError,
    create_token,
    create_user,
    decode_token,
    get_user_by_email,
    get_user_by_id,
    is_valid_email,
    verify_password,
)
from .auth_schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut

auth_router = APIRouter(prefix="/api/auth")


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """从 Authorization: Bearer <token> 解析当前登录用户，供其他路由依赖注入。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    token = authorization[len("Bearer "):].strip()
    try:
        payload = decode_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = get_user_by_id(payload.get("sub", ""))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已被删除")
    return user


def get_optional_user(authorization: str | None = Header(default=None)) -> dict | None:
    """可选登录：有合法 token 返回用户，否则返回 None（不报错）。

    用于下载/总结这类「零门槛匿名可用，但登录后能识别会员」的接口。
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        payload = decode_token(authorization[len("Bearer "):].strip())
    except AuthError:
        return None
    return get_user_by_id(payload.get("sub", ""))


@auth_router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest) -> AuthResponse:
    email = payload.email.strip().lower()
    password = payload.password

    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 位")
    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="该邮箱已注册，请直接登录")

    user = create_user(email, password)
    token = create_token(user["id"], user["email"])
    return AuthResponse(token=token, user=UserOut(id=user["id"], email=user["email"]))


@auth_router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    email = payload.email.strip().lower()
    user = get_user_by_email(email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = create_token(user["id"], user["email"])
    return AuthResponse(token=token, user=UserOut(id=user["id"], email=user["email"]))


@auth_router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user["id"], email=user["email"])
