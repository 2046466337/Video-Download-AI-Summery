"""后端接口冒烟测试。

用法：backend/.venv/Scripts/python.exe scripts/api_smoke_test.py [视频链接]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
DEFAULT_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def call(path: str, payload: dict | None = None) -> tuple[int, dict]:
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"} if data else {}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def main() -> int:
    video_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
        if not ok:
            failures.append(name)

    status, body = call("/api/health")
    check("健康检查", status == 200 and body.get("status") == "ok")

    status, body = call("/api/parse", {"url": "http://127.0.0.1:8000/api/health"})
    check("SSRF 拦截内网地址", status == 400, body.get("detail", ""))

    status, body = call("/api/parse", {"url": "ftp://example.com/a.mp4"})
    check("拦截非 http 协议", status == 400, body.get("detail", ""))

    status, body = call("/api/parse", {"url": "https://example.com/not-a-video"})
    check("无效链接给出友好提示", status == 422, body.get("detail", ""))

    status, info = call("/api/parse", {"url": video_url})
    ok = status == 200 and bool(info.get("options"))
    check("解析视频", ok, f"{info.get('platform', '')} | {info.get('title', '')[:28]}")
    if not ok:
        print("解析失败，后续用例跳过")
        return 1

    option = next(
        (o for o in info["options"] if o["id"] == "video-360"),
        next((o for o in info["options"] if o["kind"] == "video"), info["options"][0]),
    )
    check("清晰度归档", all("-" in o["id"] for o in info["options"]), f"{len(info['options'])} 个档位")

    status, task = call(
        "/api/downloads",
        {
            "url": info["url"],
            "option_id": option["id"],
            "title": info["title"],
            "quality": option["label"],
            "platform": info.get("platform", ""),
            "expected_size": option.get("filesize") or 0,
        },
    )
    check("创建下载任务", status == 200 and bool(task.get("id")))
    if not task.get("id"):
        return 1

    task_id = task["id"]
    progresses: list[float] = []
    state: dict = {}
    for _ in range(120):
        _, state = call(f"/api/downloads/{task_id}")
        progresses.append(state.get("progress", 0))
        if state.get("status") in ("success", "failed"):
            break
        time.sleep(1)

    check("任务完成", state.get("status") == "success", state.get("error", ""))
    check(
        "进度单调递增",
        all(b >= a for a, b in zip(progresses, progresses[1:])),
        f"轨迹 {[round(p) for p in progresses]}",
    )

    if state.get("status") == "success":
        req = urllib.request.Request(BASE + state["download_url"])
        with urllib.request.urlopen(req, timeout=120) as resp:
            disposition = resp.headers.get("content-disposition", "")
            size = len(resp.read())
        check("文件可下载", size > 0, f"{size / 1048576:.1f} MB")
        check("附件头正确（移动端可保存）", "attachment" in disposition)

    status, body = call("/api/downloads/not-exist-id")
    check("不存在的任务返回 404", status == 404)

    print()
    print(f"共 {len(failures)} 项失败" if failures else "全部用例通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
