"""AI 视频总结任务管理。

与下载的 task_manager.py 同构但完全独立：独立线程池、独立任务表、独立状态机。
总结任务成功后仍持有字幕与结果，用于支持后续的 AI 追问。
"""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from datetime import datetime, timezone

from . import ai_client, db, subtitles
from .config import DB_PATH
from .summarizer import ask_question, summarize


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

SUMMARY_MAX_CONCURRENT = int(os.getenv("SUMMARY_MAX_CONCURRENT", "2"))

STAGE_QUEUED = "排队中"
STAGE_SUBTITLES = "提取字幕"
STAGE_SUMMARIZING = "总结中"
STAGE_DONE = "已完成"
STAGE_FAILED = "失败"


def _init_summary_db() -> None:
    """独立建 summary_records 表，不修改 db.py 的既有 SCHEMA。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS summary_records (
                id          TEXT PRIMARY KEY,
                url         TEXT NOT NULL,
                title       TEXT,
                platform    TEXT,
                status      TEXT NOT NULL,
                result_json TEXT,
                error       TEXT,
                created_at  TEXT NOT NULL,
                finished_at TEXT
            )
            """
        )


@dataclass
class SummaryTask:
    id: str
    url: str
    title: str
    platform: str = ""
    status: str = "queued"  # queued | running | success | failed
    stage: str = STAGE_QUEUED
    progress: float = 0.0
    error: str = ""
    transcript: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "id": self.id,
                "status": self.status,
                "stage": self.stage,
                "progress": round(self.progress, 1),
                "title": self.title,
                "platform": self.platform,
                "error": self.error,
                "result": self.result,
            }


class SummaryManager:
    def __init__(self) -> None:
        _init_summary_db()
        self._tasks: dict[str, SummaryTask] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(
            max_workers=SUMMARY_MAX_CONCURRENT, thread_name_prefix="summarizer"
        )

    def submit(self, url: str, title: str, platform: str = "") -> SummaryTask:
        task = SummaryTask(
            id=uuid.uuid4().hex,
            url=url,
            title=title or "未命名视频",
            platform=platform,
        )
        with self._lock:
            self._tasks[task.id] = task
        self._record(task.id, task.url, task.title, task.platform, "queued")
        self._pool.submit(self._run, task)
        return task

    def get(self, task_id: str) -> SummaryTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def ask(self, task_id: str, question: str) -> str:
        task = self.get(task_id)
        if not task:
            raise RuntimeError("总结任务不存在或已过期")
        if task.status != "success" or not task.result:
            raise RuntimeError("请先完成视频总结后再提问")

        transcript_text = subtitles.transcript_to_text(task.transcript)
        summary_text = str(task.result.get("summary") or "")
        return ask_question(question, task.title, transcript_text, summary_text)

    # ------------------------------------------------------------------ 内部

    def _run(self, task: SummaryTask) -> None:
        with task.lock:
            task.status = "running"
            task.stage = STAGE_SUBTITLES
            task.progress = 10.0

        try:
            if not ai_client.is_configured():
                raise ai_client.AIClientError(
                    "尚未配置 AI 服务，请在服务端设置 DEEPSEEK_API_KEY 环境变量后重试"
                )

            cues = subtitles.extract_subtitles(task.url)
            if not cues:
                raise RuntimeError(
                    "该视频没有可用的字幕，暂时无法 AI 总结。"
                    "（B 站需 UP 主上传字幕，YouTube 可用自动字幕）"
                )
            task.transcript = cues

            with task.lock:
                task.stage = STAGE_SUMMARIZING
                task.progress = 50.0

            text = subtitles.transcript_to_text(cues)
            result = summarize(task.title, text)

            with task.lock:
                task.status = "success"
                task.stage = STAGE_DONE
                task.progress = 100.0
                task.result = result
            self._record(task.id, task.url, task.title, task.platform, "success", result)
        except Exception as exc:  # noqa: BLE001 - 兜底，避免线程静默退出
            message = str(exc) or "总结失败，请稍后重试"
            with task.lock:
                task.status = "failed"
                task.stage = STAGE_FAILED
                task.error = message
            self._record(task.id, task.url, task.title, task.platform, "failed", error=message)

    def _record(
        self,
        task_id: str,
        url: str,
        title: str,
        platform: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        import json

        try:
            with db.connect() as conn:
                if status == "queued":
                    conn.execute(
                        "INSERT OR REPLACE INTO summary_records"
                        "(id, url, title, platform, status, created_at)"
                        " VALUES(?,?,?,?,?,?)",
                        (task_id, url, title, platform, status, _now_iso()),
                    )
                else:
                    conn.execute(
                        "UPDATE summary_records SET status=?, result_json=?, error=?, finished_at=? WHERE id=?",
                        (
                            status,
                            json.dumps(result, ensure_ascii=False) if result else None,
                            error,
                            _now_iso(),
                            task_id,
                        ),
                    )
        except Exception:  # noqa: BLE001 - 落库失败不影响总结主流程
            pass


summary_manager = SummaryManager()
