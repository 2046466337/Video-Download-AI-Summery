"""测试加密字幕 URL 能否直接请求（服务端解密返回字幕 JSON）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from app.bilibili_adapter import API_HEADERS, extract_ids, fetch_view

WEB_SUBTITLE_API = "https://api.bilibili.com/x/v2/subtitle/web/view"


def read_varint(buf: bytes, pos: int):
    value = 0
    shift = 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            return value, pos
        shift += 7
    return value, pos


def decode_message(buf: bytes):
    fields = []
    pos = 0
    while pos < len(buf):
        key, pos = read_varint(buf, pos)
        field_num = key >> 3
        wire_type = key & 7
        if wire_type == 0:
            val, pos = read_varint(buf, pos)
            fields.append((field_num, wire_type, val))
        elif wire_type == 2:
            length, pos = read_varint(buf, pos)
            fields.append((field_num, wire_type, buf[pos:pos + length]))
            pos += length
        elif wire_type == 1:
            fields.append((field_num, wire_type, buf[pos:pos + 8]))
            pos += 8
        elif wire_type == 5:
            fields.append((field_num, wire_type, buf[pos:pos + 4]))
            pos += 4
        else:
            break
    return fields


def parse_tracks(payload: bytes):
    top = decode_message(payload)
    data = next((f[2] for f in top if f[0] == 1 and f[1] == 2), None)
    if not data:
        return []
    tracks = []
    for field in decode_message(data):
        if field[0] != 3 or field[1] != 2:
            continue
        inner = decode_message(field[2])
        def ft(n):
            return next((f[2].decode("utf-8", "ignore") for f in inner if f[0] == n and f[1] == 2), "")
        tracks.append({"lan": ft(3), "lan_doc": ft(4), "url": ft(5)})
    return [t for t in tracks if t["lan"] and t["url"]]


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "https://bilibili.com/video/BV1mAAmzqEfP"
    bvid, aid, page = extract_ids(url)
    view = fetch_view(bvid, aid)
    pages = view.get("pages") or []
    page_info = pages[page - 1] if 0 < page <= len(pages) else (pages[0] if pages else {})
    cid = int(page_info.get("cid") or view.get("cid"))
    aid_val = view.get("aid") or aid

    cookies: dict[str, str] = {}
    p = Path("_bili_cookies.txt")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies[parts[5]] = parts[6]

    params = {
        "oid": str(cid), "pid": str(aid_val),
        "context_ext": json.dumps({"video_type": 1}), "type": "1",
        "cur_production_type": "0", "preferred_language": "ai-zh", "playlist_switch": "0",
    }
    headers = dict(API_HEADERS)
    headers["Accept"] = "application/octet-stream"
    resp = requests.get(WEB_SUBTITLE_API, headers=headers, params=params, cookies=cookies, timeout=(10, 30))
    tracks = parse_tracks(resp.content)
    print(f"字幕轨道 {len(tracks)} 条")
    for i, t in enumerate(tracks):
        print(f"\n--- 轨道 {i}: lan={t['lan']} ({t['lan_doc']}) ---")
        sub_url = t["url"]
        print("原始 URL (前120):", sub_url[:120])
        # 补全协议
        full = "https:" + sub_url if sub_url.startswith("//") else sub_url
        print("尝试直接请求...")
        try:
            r = requests.get(full, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0", "Referer": "https://www.bilibili.com/"}, timeout=(10, 30))
            ct = (r.headers.get("content-type") or "").lower()
            print("  HTTP:", r.status_code, "| content-type:", ct, "| 字节数:", len(r.content))
            body_preview = r.content[:200]
            if "json" in ct or body_preview.lstrip().startswith(b"{"):
                print("  JSON 响应(前200):", r.text[:200])
            else:
                print("  响应前120字节:", body_preview[:120])
        except Exception as exc:  # noqa: BLE001
            print("  请求失败:", repr(exc))


if __name__ == "__main__":
    main()
