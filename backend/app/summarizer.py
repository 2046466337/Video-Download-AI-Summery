"""视频内容总结核心逻辑。

把「带时间戳的字幕文本」送给大模型，产出结构化结果：
摘要、核心要点、带时间戳章节、思维导图，以及基于上下文的 AI 追问。

超长字幕按阈值分块做 map-reduce，避免单次上下文过长导致质量下降或超时。
"""

from __future__ import annotations

import re
from typing import Any

from . import ai_client

# 单次送入模型的最大字符数（中文约等于 1.2 万 token），超过则分块
MAX_CHARS_PER_CALL = 24000

_SUMMARY_SYSTEM = (
    "你是专业的视频内容分析师，擅长从视频字幕中提炼结构化、可复用的知识。"
    "你的回答必须准确、具体，不编造字幕中不存在的内容。"
)


def summarize(title: str, transcript_text: str) -> dict[str, Any]:
    """生成视频结构化总结。"""
    if not transcript_text.strip():
        raise ai_client.AIClientError("字幕为空，无法总结")

    if len(transcript_text) <= MAX_CHARS_PER_CALL:
        return _summarize_chunk(title, transcript_text, is_whole=True)

    # 分块 map-reduce：先逐块提炼，再汇总
    chunks = _split_text(transcript_text, MAX_CHARS_PER_CALL)
    partials = [_summarize_chunk(title, chunk, is_whole=False) for chunk in chunks]
    return _reduce(title, partials)


def ask_question(
    question: str,
    title: str,
    transcript_text: str,
    summary_text: str,
) -> str:
    """基于字幕与摘要回答用户追问。"""
    # 控制上下文体量：超长字幕截断到上限附近，保留开头（通常含总览）
    context = transcript_text
    if len(context) > MAX_CHARS_PER_CALL * 2:
        context = context[: MAX_CHARS_PER_CALL * 2]

    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {
            "role": "user",
            "content": (
                f"以下是视频《{title}》的内容摘要：\n{summary_text}\n\n"
                f"以下是视频字幕（含时间戳 [MM:SS]）：\n{context}\n\n"
                f"请根据以上内容回答用户问题，简洁、准确。"
                f"若答案涉及具体时间点，请给出 [MM:SS] 时间戳。\n\n用户问题：{question}"
            ),
        },
    ]
    return ai_client.chat_text(messages, max_tokens=2048, temperature=0.3)


# ------------------------------------------------------------------ 内部

def _split_text(text: str, limit: int) -> list[str]:
    """按行切块，尽量在句子边界断开，保证每块不超过 limit。"""
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.split("\n"):
        if size + len(line) + 1 > limit and current:
            chunks.append("\n".join(current))
            current = []
            size = 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def _summary_prompt(title: str, transcript_text: str, is_whole: bool) -> str:
    scope = "整个视频" if is_whole else "视频的这一片段"
    return (
        f"以下是视频《{title}》{scope}的字幕（含时间戳，格式 [MM:SS] 文本）。\n\n"
        f"请分析并输出一个 JSON 对象，字段如下：\n"
        f'{{"summary": "用 200 字以内概括核心内容", '
        f'"key_points": ["3-8 条核心要点，每条一句，具体而非空泛"], '
        f'"chapters": [{{"start": 秒, "end": 秒, "title": "章节标题", "summary": "该段要点"}}], '
        f'"mindmap": {{"topic": "主题", "children": [{{"topic": "要点", "children": []}}]}}}}\n\n'
        f"硬性要求：\n"
        f"1. chapters 的 start/end 必须引用字幕中真实出现的时间戳（转换为秒），"
        f"按时间顺序排列并尽量覆盖全片；\n"
        f"2. mindmap 最多 3 层，children 可为空数组；\n"
        f"3. 只输出 JSON 本身，不要任何解释、不要代码块标记。\n\n"
        f"字幕：\n{transcript_text}"
    )


def _summarize_chunk(title: str, transcript_text: str, is_whole: bool) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {"role": "user", "content": _summary_prompt(title, transcript_text, is_whole)},
    ]
    result = ai_client.chat_json(messages, max_tokens=8192, temperature=0.3)
    return _normalize(result)


def _reduce(title: str, partials: list[dict[str, Any]]) -> dict[str, Any]:
    """把分块结果汇总成一份最终结构。"""
    summaries = [p.get("summary", "") for p in partials if p.get("summary")]
    key_points: list[str] = []
    chapters: list[dict[str, Any]] = []
    branch_topics: list[str] = []
    for p in partials:
        key_points.extend(p.get("key_points") or [])
        chapters.extend(p.get("chapters") or [])
        mm = p.get("mindmap") or {}
        if mm.get("topic"):
            branch_topics.append(str(mm["topic"]))

    prompt = (
        f"以下是视频《{title}》分段总结的合并素材，请综合成一份最终 JSON，字段与之前一致：\n\n"
        f"分段摘要：\n" + "\n".join(f"- {s}" for s in summaries) + "\n\n"
        f"全部要点：\n" + "\n".join(f"- {k}" for k in key_points) + "\n\n"
        f"全部章节：\n"
        + json_dumps(chapters)
        + "\n\n"
        f"各段主题：{branch_topics}\n\n"
        f"要求：key_points 去重合并为 5-10 条；chapters 按时间排序并去重；"
        f"mindmap 汇总成一个 3 层以内的整体结构；只输出 JSON。"
    )
    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    result = ai_client.chat_json(messages, max_tokens=8192, temperature=0.3)
    return _normalize(result)


def json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


def _normalize(result: dict[str, Any]) -> dict[str, Any]:
    """兜底清洗模型输出，保证前端拿到的结构字段齐全。"""
    summary = str(result.get("summary") or "").strip()
    key_points = [str(k).strip() for k in (result.get("key_points") or []) if str(k).strip()]

    chapters: list[dict[str, Any]] = []
    for ch in result.get("chapters") or []:
        if not isinstance(ch, dict):
            continue
        start = _to_number(ch.get("start"))
        end = _to_number(ch.get("end"))
        title = str(ch.get("title") or "").strip()
        csummary = str(ch.get("summary") or "").strip()
        if not title and not csummary:
            continue
        chapters.append({"start": start, "end": end, "title": title, "summary": csummary})
    chapters.sort(key=lambda c: c["start"])

    mindmap = _normalize_mindmap(result.get("mindmap"))
    return {
        "summary": summary,
        "key_points": key_points[:10],
        "chapters": chapters,
        "mindmap": mindmap,
    }


def _normalize_mindmap(node: Any) -> dict[str, Any]:
    if not isinstance(node, dict):
        node = {}
    topic = str(node.get("topic") or node.get("title") or "").strip()
    children = [
        _normalize_mindmap(child) for child in (node.get("children") or []) if isinstance(child, dict)
    ]
    return {"topic": topic, "children": children}


def _to_number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return float(match.group(0))
    return 0.0
