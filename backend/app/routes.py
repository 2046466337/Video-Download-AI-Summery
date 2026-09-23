"""API 路由。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from . import db
from .schemas import DownloadRequest, ParseRequest, TaskState, VideoInfo
from .security import UnsafeUrlError, validate_url
from .task_manager import task_manager
from .ydl_service import ParseError, parse_video

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/stats")
async def stats() -> dict[str, int]:
    return {"total_downloads": db.get_total_downloads()}


@router.post("/parse", response_model=VideoInfo)
async def parse(payload: ParseRequest) -> VideoInfo:
    try:
        url = validate_url(payload.url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        info = await asyncio.to_thread(parse_video, url)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return VideoInfo(**info)


@router.post("/downloads", response_model=TaskState)
async def create_download(payload: DownloadRequest) -> TaskState:
    try:
        url = validate_url(payload.url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task = task_manager.submit(
        url=url,
        option_id=payload.option_id,
        title=payload.title,
        quality=payload.quality or payload.option_id,
        platform=payload.platform,
        expected_size=payload.expected_size or 0,
    )
    return TaskState(**task.snapshot())


@router.get("/downloads/{task_id}", response_model=TaskState)
async def get_download(task_id: str) -> TaskState:
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return TaskState(**task.snapshot())


@router.get("/files/{task_id}")
async def download_file(task_id: str) -> FileResponse:
    task = task_manager.get(task_id)
    if not task or task.status != "success":
        raise HTTPException(status_code=404, detail="文件不存在或尚未下载完成")

    path = Path(task.filepath)
    if not path.exists():
        raise HTTPException(status_code=410, detail="文件已过期并被清理，请重新下载")

    # 移动端 Safari 对 JS blob 下载支持很差，必须由后端用 attachment 让浏览器接管
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/octet-stream",
        content_disposition_type="attachment",
    )
