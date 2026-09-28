"""AI 视频总结 API 路由。

独立于下载路由 routes.py，用单独 APIRouter，由 main.py 纯追加一行挂载。
"""

from __future__ import annotations

import asyncio
import json

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from .ai_client import AIClientError
from .auth_routes import get_optional_user
from .quota import QuotaError, try_consume
from .security import UnsafeUrlError, validate_url
from .subtitle_export import safe_filename, to_markdown, to_srt, to_vtt
from .subtitles import SubtitleError
from .summary_manager import summary_manager
from .summary_schemas import ChatReply, ChatRequest, SummaryRequest, SummaryState

summary_router = APIRouter(prefix="/api")


@summary_router.post("/summaries", response_model=SummaryState)
async def create_summary(
    payload: SummaryRequest,
    user: dict | None = Depends(get_optional_user),
) -> SummaryState:
    try:
        url = validate_url(payload.url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 权益拦截：免费用户每日 AI 总结 3 次，会员不限
    try:
        try_consume(user, payload.client_id, "summary")
    except QuotaError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    task = summary_manager.submit(url=url, title=payload.title, platform=payload.platform)
    return SummaryState(**task.snapshot())


@summary_router.get("/summaries/{task_id}", response_model=SummaryState)
async def get_summary(task_id: str) -> SummaryState:
    task = summary_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="总结任务不存在或已过期")
    return SummaryState(**task.snapshot())


@summary_router.get("/summaries/{task_id}/subtitles")
async def export_subtitles(task_id: str, format: str = "srt") -> Response:
    """导出视频原始字幕（不含翻译），格式 srt | vtt | md。

    直接读取任务已提取的字幕轴生成文本，以 attachment 触发浏览器默认下载。
    """
    task = summary_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="总结任务不存在或已过期")
    if not task.transcript:
        raise HTTPException(status_code=404, detail="字幕不存在或尚未生成")

    fmt = (format or "srt").strip().lower()
    stem = safe_filename(task.title)
    if fmt == "srt":
        content = to_srt(task.transcript)
        ext, media_type = ".srt", "application/x-subrip"
    elif fmt == "vtt":
        content = to_vtt(task.transcript)
        ext, media_type = ".vtt", "text/vtt"
    elif fmt == "md":
        content = to_markdown(task.transcript, task.title)
        ext, media_type = ".md", "text/markdown; charset=utf-8"
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式，可选 srt / vtt / md")

    # 兼容老客户端：提供纯 ASCII 回退文件名，正文用 RFC 5987 的 UTF-8 文件名
    ascii_stem = stem.encode("ascii", "ignore").decode("ascii").strip(" .-_") or "subtitles"
    disposition = (
        f"attachment; filename=\"{ascii_stem}{ext}\"; "
        f"filename*=UTF-8''{quote(f'{stem}{ext}')}"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


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
