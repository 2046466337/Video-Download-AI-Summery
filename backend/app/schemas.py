"""接口出入参模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    url: str = Field(..., max_length=2048)


class QualityOption(BaseModel):
    id: str
    label: str
    note: str = ""
    kind: str  # video | audio
    height: int | None = None
    ext: str = "mp4"
    filesize: int | None = None
    filesize_text: str = ""
    needs_merge: bool = False
    recommended: bool = False


class VideoInfo(BaseModel):
    url: str
    title: str
    thumbnail: str | None = None
    duration: int | None = None
    duration_text: str = ""
    uploader: str = ""
    platform: str = ""
    view_count: int | None = None
    options: list[QualityOption] = []


class DownloadRequest(BaseModel):
    url: str = Field(..., max_length=2048)
    option_id: str
    title: str = ""
    quality: str = ""
    platform: str = ""
    # 解析阶段已知的预估总体积。音视频分轨会触发两轮下载，
    # 没有这个基准的话进度条会在第二轮从头再来一次。
    expected_size: int | None = None


class TaskState(BaseModel):
    id: str
    status: str  # queued | running | success | failed
    stage: str
    progress: float
    title: str
    quality: str = ""
    speed_text: str = ""
    eta_text: str = ""
    downloaded_text: str = ""
    total_text: str = ""
    filename: str = ""
    filesize_text: str = ""
    download_url: str = ""
    error: str = ""
