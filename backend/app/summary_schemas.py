"""AI 视频总结相关出入参模型。

与下载功能的 schemas.py 相互独立，互不干扰。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SummaryRequest(BaseModel):
    url: str = Field(..., max_length=2048)
    title: str = ""
    platform: str = ""
    client_id: str = ""


class SummaryState(BaseModel):
    id: str
    status: str  # queued | running | success | failed
    stage: str
    progress: float
    title: str = ""
    platform: str = ""
    error: str = ""
    result: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=4000)


class ChatReply(BaseModel):
    answer: str
