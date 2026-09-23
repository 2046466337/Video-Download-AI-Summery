"""下载任务管理。

yt-dlp 是同步阻塞的，直接在事件循环里跑会卡死整个服务，
所以全部丢进受限并发的线程池，进度通过 hook 回写内存快照供前端轮询。
"""

from __future__ import annotations

import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import db
from .config import DOWNLOAD_DIR, MAX_CONCURRENT_DOWNLOADS
from .utils import format_eta, format_size, format_speed
from .ydl_service import ParseError, download_video

STAGE_QUEUED = "排队中"
STAGE_DOWNLOADING = "下载中"
STAGE_MERGING = "合并音视频"
STAGE_CONVERTING = "转换音频"
STAGE_DONE = "已完成"
STAGE_FAILED = "失败"


@dataclass
class Task:
    id: str
    url: str
    option_id: str
    title: str
    quality: str
    platform: str = ""
    status: str = "queued"  # queued | running | success | failed
    stage: str = STAGE_QUEUED
    progress: float = 0.0
    speed: float = 0.0
    eta: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    expected_size: int = 0
    completed_bytes: int = 0
    filename: str = ""
    filepath: str = ""
    filesize: int = 0
    error: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "id": self.id,
                "status": self.status,
                "stage": self.stage,
                "progress": round(self.progress, 1),
                "title": self.title,
                "quality": self.quality,
                "speed_text": format_speed(self.speed),
                "eta_text": format_eta(self.eta),
                "downloaded_text": format_size(self.downloaded_bytes),
                "total_text": format_size(self.total_bytes),
                "filename": self.filename,
                "filesize_text": format_size(self.filesize),
                "download_url": f"/api/files/{self.id}" if self.status == "success" else "",
                "error": self.error,
            }


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(
            max_workers=MAX_CONCURRENT_DOWNLOADS, thread_name_prefix="downloader"
        )

    def submit(
        self,
        url: str,
        option_id: str,
        title: str,
        quality: str,
        platform: str = "",
        expected_size: int = 0,
    ) -> Task:
        task = Task(
            id=uuid.uuid4().hex,
            url=url,
            option_id=option_id,
            title=title or "未命名视频",
            quality=quality,
            platform=platform,
            expected_size=max(0, expected_size or 0),
        )
        with self._lock:
            self._tasks[task.id] = task
        db.create_record(task.id, url, task.title, platform, option_id, quality)
        self._pool.submit(self._run, task)
        return task

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def all_snapshots(self) -> list[dict[str, Any]]:
        with self._lock:
            tasks = list(self._tasks.values())
        return [t.snapshot() for t in tasks]

    def forget(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)

    # ------------------------------------------------------------------ 内部

    def _run(self, task: Task) -> None:
        out_dir = DOWNLOAD_DIR / task.id
        with task.lock:
            task.status = "running"
            task.stage = STAGE_DOWNLOADING

        try:
            path = download_video(
                task.url,
                task.option_id,
                out_dir,
                on_progress=lambda d: self._on_progress(task, d),
                on_stage=lambda d: self._on_stage(task, d),
            )
        except ParseError as exc:
            self._fail(task, str(exc), out_dir)
            return
        except Exception as exc:  # noqa: BLE001 - 兜底，避免线程静默退出
            self._fail(task, f"下载失败：{exc}", out_dir)
            return

        size = path.stat().st_size
        with task.lock:
            task.status = "success"
            task.stage = STAGE_DONE
            task.progress = 100.0
            task.speed = 0.0
            task.eta = 0.0
            task.filename = path.name
            task.filepath = str(path)
            task.filesize = size
        db.finish_record(task.id, "success", path.name, size)

    def _fail(self, task: Task, message: str, out_dir: Path) -> None:
        with task.lock:
            task.status = "failed"
            task.stage = STAGE_FAILED
            task.error = message
        db.finish_record(task.id, "failed", error=message)
        shutil.rmtree(out_dir, ignore_errors=True)

    def _on_progress(self, task: Task, data: dict[str, Any]) -> None:
        status = data.get("status")
        if status == "downloading":
            stream_total = int(data.get("total_bytes") or data.get("total_bytes_estimate") or 0)
            stream_done = int(data.get("downloaded_bytes") or 0)
            with task.lock:
                task.stage = STAGE_DOWNLOADING
                task.speed = float(data.get("speed") or 0)
                task.eta = float(data.get("eta") or 0)
                task.downloaded_bytes = task.completed_bytes + stream_done
                task.total_bytes = max(
                    task.expected_size, task.completed_bytes + stream_total
                )
                if task.total_bytes:
                    percent = task.downloaded_bytes / task.total_bytes * 100
                    # 只增不减，收尾封顶 99 留给合并/转码阶段
                    task.progress = min(99.0, max(task.progress, percent))
        elif status == "finished":
            done = int(data.get("total_bytes") or data.get("downloaded_bytes") or 0)
            with task.lock:
                task.completed_bytes += done
                task.downloaded_bytes = task.completed_bytes
                task.speed = 0.0
                task.eta = 0.0

    def _on_stage(self, task: Task, data: dict[str, Any]) -> None:
        if data.get("status") != "started":
            return
        name = data.get("postprocessor") or ""
        with task.lock:
            if name == "Merger":
                task.stage = STAGE_MERGING
            elif name in ("FFmpegExtractAudio", "ExtractAudio"):
                task.stage = STAGE_CONVERTING


task_manager = TaskManager()
