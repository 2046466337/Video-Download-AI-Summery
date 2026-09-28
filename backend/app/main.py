"""FastAPI 应用入口。"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .auth_routes import auth_router
from .cleaner import start_cleaner
from .config import FRONTEND_DIST
from .payment_routes import payment_router
from .routes import router
from .summary_routes import summary_router

_stop_cleaner = threading.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    start_cleaner(_stop_cleaner)
    yield
    _stop_cleaner.set()


app = FastAPI(title="万能视频下载站", version="1.0.0", lifespan=lifespan)

# 开发期前端跑在 Vite dev server 上，生产期同源托管不需要跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(summary_router)
app.include_router(auth_router)
app.include_router(payment_router)

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
