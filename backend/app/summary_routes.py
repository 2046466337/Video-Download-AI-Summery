"""AI 视频总结 API 路由。

独立于下载路由 routes.py，用单独 APIRouter，由 main.py 纯追加一行挂载。
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .ai_client import AIClientError
from .security import UnsafeUrlError, validate_url
from .subtitles import SubtitleError
from .summary_manager import summary_manager
from .summary_schemas import ChatReply, ChatRequest, SummaryRequest, SummaryState

summary_router = APIRouter(prefix="/api")


@summary_router.post("/summaries", response_model=SummaryState)
async def create_summary(payload: SummaryRequest) -> SummaryState:
    try:
        url = validate_url(payload.url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task = summary_manager.submit(url=url, title=payload.title, platform=payload.platform)
    return SummaryState(**task.snapshot())


@summary_router.get("/summaries/{task_id}", response_model=SummaryState)
async def get_summary(task_id: str) -> SummaryState:
    task = summary_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="总结任务不存在或已过期")
    return SummaryState(**task.snapshot())


@summary_router.post("/summaries/{task_id}/chat", response_model=ChatReply)
async def chat_summary(task_id: str, payload: ChatRequest) -> ChatReply:
    question = (payload.message or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="请输入要提问的内容")

    try:
        answer = await asyncio.to_thread(summary_manager.ask, task_id, question)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (AIClientError, SubtitleError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ChatReply(answer=answer)


@summary_router.get("/summaries/{task_id}/stream")
def stream_summary(task_id: str, module: str, question: str = "") -> StreamingResponse:
    """按模块流式输出总结内容（SSE）。

    module ∈ {summary, subtitle, mindmap, chat}。
    事件类型：
      phase  — data: {"phase": "summary|points|transcript|chapters|mindmap|answer"}
      delta  — data: {"content": "文本分片"}
      done   — data: {}（正常结束）
      error  — data: {"message": "..."}（异常结束，不再有 done）

    同步 def 端点 + 同步生成器：Starlette 会在线程池里迭代，不阻塞事件循环。
    """
    task = summary_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="总结任务不存在或已过期")

    def event_stream():
        try:
            for event, data in summary_manager.stream(task_id, module, question):
                if event == "phase":
                    payload = {"phase": data}
                else:  # delta
                    payload = {"content": data}
                yield f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except (AIClientError, SubtitleError, RuntimeError) as exc:
            yield (
                "event: error\n"
                f"data: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
