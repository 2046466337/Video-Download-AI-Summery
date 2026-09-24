"""Dump 新字幕接口 protobuf 的完整字段结构，寻找明文 URL 或解密线索。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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


def decode_message(buf: bytes, depth: int = 0):
    fields = []
    pos = 0
    while pos < len(buf):
        key, pos = read_varint(buf, pos)
        field_num = key >> 3
        wire_type = key & 7
        ind = "  " * depth
        if wire_type == 0:
            val, pos = read_varint(buf, pos)
            fields.append((field_num, wire_type, val))
        elif wire_type == 1:
            fields.append((field_num, wire_type, buf[pos:pos + 8]))
            pos += 8
        elif wire_type == 2:
            length, pos = read_varint(buf, pos)
            raw = buf[pos:pos + length]
            pos += length
            fields.append((field_num, wire_type, raw))
        elif wire_type == 5:
            fields.append((field_num, wire_type, buf[pos:pos + 4]))
            pos += 4
        else:
            break
    return fields


def dump(buf: bytes, depth: int = 0, max_depth: int = 4):
    ind = "  " * depth
    try:
        fields = decode_message(buf, depth)
    except Exception as exc:  # noqa: BLE001
        print(f"{ind}<无法解析: {exc}> bytes={buf[:60]!r}")
        return
    for field_num, wire_type, val in fields:
        if wire_type == 0:
            print(f"{ind}field {field_num} (varint) = {val}")
        elif wire_type == 1:
            print(f"{ind}field {field_num} (fixed64) = {val.hex()}")
        elif wire_type == 5:
            print(f"{ind}field {field_num} (fixed32) = {val.hex()}")
        elif wire_type == 2:
            # 尝试作为字符串/子 message 打印
            if field_num in (2, 3, 4, 5):  # 已知字符串字段
                try:
                    s = val.decode("utf-8")
                    print(f"{ind}field {field_num} (bytes, str) = {s[:100]!r}")
                except UnicodeDecodeError:
                    print(f"{ind}field {field_num} (bytes) = {val.hex()[:100]}")
            else:
                print(f"{ind}field {field_num} (bytes) len={len(val)}:")
                if depth < max_depth:
                    dump(val, depth + 1, max_depth)


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "https://bilibili.com/video/BV1mAAmzqEfP"
    bvid, aid, page = extract_ids(url)
    view = fetch_view(bvid, aid)
    pages = view.get("pages") or []
    page_info = pages[page - 1] if 0 < page <= len(pages) else (pages[0] if pages else {})
    cid = int(page_info.get("cid") or view.get("cid"))
    aid_val = view.get("aid") or aid
    print(f"bvid={bvid} aid={aid_val} cid={cid} title={view.get('title')}")

    params = {
        "oid": str(cid),
        "pid": str(aid_val),
        "context_ext": json.dumps({"video_type": 1}),
        "type": "1",
        "cur_production_type": "0",
        "preferred_language": "ai-zh",
        "playlist_switch": "0",
    }
    headers = dict(API_HEADERS)
    headers["Accept"] = "application/octet-stream"
    # 带 buvid cookie
    cookies: dict[str, str] = {}
    p = Path("_bili_cookies.txt")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies[parts[5]] = parts[6]

    resp = requests.get(WEB_SUBTITLE_API, headers=headers, params=params, cookies=cookies, timeout=(10, 30))
    print("HTTP:", resp.status_code, "content-type:", resp.headers.get("content-type"))
    body = resp.content
    print("返回字节数:", len(body))
    print("=== 完整 protobuf 结构 ===")
    dump(body)


if __name__ == "__main__":
    main()
