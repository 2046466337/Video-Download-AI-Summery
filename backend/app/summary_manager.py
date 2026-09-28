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

from . import ai_client, db, subtitles, summarizer
from .config import DB_PATH
from .summarizer import ask_question


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

SUMMARY_MAX_CONCURRENT = int(os.getenv("SUMMARY_MAX_CONCURRENT", "2"))

STAGE_QUEUED = "排队中"
STAGE_SUBTITLES = "提取字幕"
STAGE_SUMMARIZING = "总结中"
STAGE_DONE = "已完成"
STAGE_FAILED = "失败"

# 无字幕时展示给用户的提示（抖音需作者上传字幕，B 站可用自动字幕）
NO_SUBTITLE_TIP = "该视频没有可用的字幕，暂时无法 AI 总结。（抖音需作者上传字幕，B站 可用自动字幕）"


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
    auto: bool = False  # 解析成功后自动触发；失败时在任务内自动重试 1 次
    status: str = "queued"  # queued | running | success | failed
    stage: str = STAGE_QUEUED
    progress: float = 0.0
    error: str = ""
    transcript: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    transcript_text: str = ""
    subtitle_ready: threading.Event = field(default_factory=threading.Event, repr=False)
    # 流式模块结果缓存：生成后回填，重复点击不重复请求
    summary_text: str = ""
    key_points: list[str] = field(default_factory=list)
    chapters_text: str = ""
    mindmap_md: str = ""
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

    def submit(
        self, url: str, title: str, platform: str = "", auto: bool = False
    ) -> SummaryTask:
        task = SummaryTask(
            id=uuid.uuid4().hex,
            url=url,
            title=title or "未命名视频",
            platform=platform,
            auto=auto,
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
        if task.status != "success" or not task.transcript:
            raise RuntimeError("请先完成视频总结后再提问")

        transcript_text = task.transcript_text or subtitles.transcript_to_text(task.transcript)
        return ask_question(question, task.title, transcript_text, task.summary_text)

    def stream(self, task_id: str, module: str, question: str = ""):
        """按模块返回流式生成器，yield (event, data)。

        module ∈ {summary, subtitle, mindmap, chat}；event ∈ {phase, delta}。
        done / error 事件由路由层在遍历结束后统一发送。
        """
        task = self.get(task_id)
        if not task:
            raise RuntimeError("总结任务不存在或已过期")

        # 等待后台线程把字幕提取完
        if not task.subtitle_ready.wait(timeout=300):
            raise RuntimeError("字幕提取超时，请稍后重试")
        if task.status != "success":
            raise RuntimeError(task.error or "字幕提取失败")

        if not ai_client.is_configured():
            raise ai_client.AIClientError(
                "尚未配置 AI 服务，请在服务端设置 DEEPSEEK_API_KEY 环境变量后重试"
            )

        if module == "summary":
            yield from self._stream_summary(task)
        elif module == "subtitle":
            yield from self._stream_subtitle(task)
        elif module == "mindmap":
            yield from self._stream_mindmap(task)
        elif module == "chat":
            if not question.strip():
                raise RuntimeError("请输入要提问的内容")
            yield from self._stream_chat(task, question.strip())
        else:
            raise RuntimeError(f"未知的总结模块：{module}")

    def _stream_summary(self, task: SummaryTask):
        with task.lock:
            cached_text = task.summary_text
            cached_points = list(task.key_points)
        if cached_text:
            yield "phase", "summary"
            yield "delta", cached_text
            yield "phase", "points"
            yield "delta", "\n".join(f"- {p}" for p in cached_points)
            return

        summary_parts: list[str] = []
        points_parts: list[str] = []
        current = ""
        for event, data in summarizer.stream_summary(task.title, task.transcript_text):
            if event == "phase":
                current = data
                yield "phase", data
            else:
                if current == "summary":
                    summary_parts.append(data)
                elif current == "points":
                    points_parts.append(data)
                yield "delta", data

        with task.lock:
            task.summary_text = "".join(summary_parts).strip()
            points_text = "".join(points_parts).strip()
            task.key_points = [
                p.lstrip("- ").strip()
                for p in points_text.splitlines()
                if p.lstrip("- ").strip()
            ]

    def _stream_subtitle(self, task: SummaryTask):
        # 原始字幕是现成数据，分块推送，保证长文本也有渐进渲染
        yield "phase", "transcript"
        text = task.transcript_text
        step = 240
        for i in range(0, len(text), step):
            yield "delta", text[i : i + step]

        with task.lock:
            cached = task.chapters_text
        if cached:
            yield "phase", "chapters"
            yield "delta", cached
            return

        parts: list[str] = []
        for event, data in summarizer.stream_chapters(task.title, task.transcript_text):
            if event == "delta":
                parts.append(data)
            yield event, data
        with task.lock:
            task.chapters_text = "".join(parts).strip()

    def _stream_mindmap(self, task: SummaryTask):
        with task.lock:
            cached = task.mindmap_md
            summary_text = task.summary_text
        if cached:
            yield "phase", "mindmap"
            yield "delta", cached
            return

        parts: list[str] = []
        for event, data in summarizer.stream_mindmap(task.title, task.transcript_text, summary_text):
            if event == "delta":
                parts.append(data)
            yield event, data
        with task.lock:
            task.mindmap_md = "".join(parts).strip()

    def _stream_chat(self, task: SummaryTask, question: str):
        with task.lock:
            summary_text = task.summary_text
        for event, data in summarizer.stream_chat(
            question, task.title, task.transcript_text, summary_text
        ):
            yield event, data

    # ------------------------------------------------------------------ 内部

    def _run(self, task: SummaryTask) -> None:
        # 自动任务（解析成功后触发）失败时在任务内重试 1 次；手动任务失败即止，交给用户重试
        max_attempts = 2 if task.auto else 1

        for attempt in range(1, max_attempts + 1):
            with task.lock:
                task.status = "running"
                task.stage = STAGE_SUBTITLES
                task.progress = 10.0

            try:
                cues = subtitles.extract_subtitles(task.url)
                if not cues:
                    raise RuntimeError(
                        "该视频没有可用的字幕，暂时无法 AI 总结。"
                        "（抖音需 UP 主上传字幕，B 站可用自动字幕）"
                    )
                    raise RuntimeError(NO_SUBTITLE_TIP)
                task.transcript = cues
                task.transcript_text = subtitles.transcript_to_text(cues)

                with task.lock:
                    task.status = "success"
                    task.stage = STAGE_DONE
                    task.progress = 100.0
                self._record(task.id, task.url, task.title, task.platform, "success")
                task.subtitle_ready.set()
                return
            except Exception as exc:  # noqa: BLE001 - 兜底，避免线程静默退出
                message = str(exc) or "字幕提取失败，请稍后重试"
                if attempt < max_attempts:
                    # 自动任务首次失败：原地重试一次，taskId 不变，前端无需感知
                    with task.lock:
                        task.error = message
                    continue

                with task.lock:
                    task.status = "failed"
                    task.stage = STAGE_FAILED
                    task.error = message
                self._record(
                    task.id, task.url, task.title, task.platform, "failed", error=message
                )
                task.subtitle_ready.set()
                return

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
