"""自动总结任务重试逻辑的离线单测（mock 网络提取与落库）。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import summary_manager  # noqa: E402


def make_task(auto: bool) -> summary_manager.SummaryTask:
    return summary_manager.SummaryTask(
        id="test-task", url="https://example.com/v", title="测试视频", auto=auto
    )


def run_with_extract(task: summary_manager.SummaryTask, side_effect) -> None:
    with mock.patch.object(
        summary_manager.subtitles, "extract_subtitles", side_effect=side_effect
    ), mock.patch.object(summary_manager.summary_manager, "_record"):
        summary_manager.summary_manager._run(task)


def always_fail(url: str, calls: list[str]):
    calls.append(url)
    raise RuntimeError("无字幕")


# 1) 手动任务（auto=False）：失败即止，不自动重试
calls: list[str] = []
task = make_task(False)
run_with_extract(task, lambda url: always_fail(url, calls))
assert task.status == "failed", task.status
assert len(calls) == 1, f"手动任务应只尝试 1 次，实际 {len(calls)}"
print("PASS 1: 手动任务失败不重试")

# 2) 自动任务：首次失败、第二次成功，共尝试 2 次，最终 success
calls2: list[str] = []


def flaky(url: str):
    calls2.append(url)
    if len(calls2) == 1:
        raise RuntimeError("临时抖动")
    return [{"start": 0, "end": 1, "text": "你好"}]


task2 = make_task(True)
run_with_extract(task2, flaky)
assert task2.status == "success", task2.status
assert len(calls2) == 2, f"自动任务首次失败后应重试 1 次，实际 {len(calls2)}"
assert task2.transcript_text, "重试成功后应有字幕文本"
print("PASS 2: 自动任务失败重试 1 次后成功")

# 3) 自动任务：两次都失败，共尝试 2 次，最终 failed
calls3: list[str] = []
task3 = make_task(True)
run_with_extract(task3, lambda url: always_fail(url, calls3))
assert task3.status == "failed", task3.status
assert len(calls3) == 2, f"自动任务失败应尝试 2 次，实际 {len(calls3)}"
print("PASS 3: 自动任务重试 1 次后仍失败")

print("ALL_OK")
