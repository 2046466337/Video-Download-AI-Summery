"""AI 视频总结冒烟测试（直接调用任务管理器，不依赖 HTTP 客户端）。

用法：
    backend/.venv/Scripts/python.exe scripts/summary_smoke_test.py "<视频链接>"

流程：提交总结 → 轮询直到终态 → 打印结果（或错误）。
未配置 DEEPSEEK_API_KEY 时，验证链路能跑通并给出友好错误提示；
配置后则产出真实总结，并追问一句验证问答能力。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# 保证无论从哪个目录运行都能找到 app 包（backend 目录）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.summary_manager import summary_manager


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.bilibili.com/video/BV1wENtzkEAq"

    print(f"== 提交总结：{url}")
    task = summary_manager.submit(url=url, title="", platform="")
    print("task_id:", task.id)

    for _ in range(120):
        state = task.snapshot()
        print(f"  状态: {state['status']} / {state['stage']} / {state['progress']}%")
        if state["status"] in ("success", "failed"):
            if state["status"] == "success":
                result = state["result"] or {}
                print("\n== 摘要 ==")
                print(result.get("summary"))
                print("\n== 核心要点 ==")
                for p in result.get("key_points") or []:
                    print(" -", p)
                print(f"\n== 章节数: {len(result.get('chapters') or [])} ==")
                print("\n== 追问 ==")
                try:
                    answer = summary_manager.ask(task.id, "这个视频的核心结论是什么？")
                    print(answer)
                except Exception as exc:  # noqa: BLE001
                    print("追问失败:", exc)
            else:
                print("\n== 失败原因 ==")
                print(state["error"])
            return
        time.sleep(2)

    print("超时：任务未在预期时间内完成")


if __name__ == "__main__":
    main()
