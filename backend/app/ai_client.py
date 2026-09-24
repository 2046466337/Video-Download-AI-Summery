"""DeepSeek 大模型客户端薄封装。

刻意保持极简：直接用 requests 调 OpenAI 兼容的 chat/completions 接口，
零额外依赖，与项目「薄封装、不污染主链路」的原则一致。

模型名通过环境变量 DEEPSEEK_MODEL 配置，默认 deepseek-chat（官方长期稳定别名，
始终指向最新对话模型）；如需更快更省可改 deepseek-flash，更强可改 deepseek-v4-pro。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


def _load_env_file() -> None:
    """加载项目根目录的 .env 文件（只补全缺失的环境变量，不覆盖已存在的值）。

    用标准库手写解析，避免为一行配置引入 python-dotenv 依赖。
    .env 中的真实系统环境变量优先级更高。
    """
    # backend/app/ai_client.py -> 项目根目录（上溯三级）
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_file.exists():
        return
    try:
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_env_file()

API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
TIMEOUT = (15, 180)  # 长视频总结生成耗时较长，读超时给足


class AIClientError(RuntimeError):
    """LLM 调用失败，message 可直接展示给用户。"""


def is_configured() -> bool:
    return bool(API_KEY)


def _request(messages: list[dict[str, Any]], max_tokens: int, temperature: float) -> dict[str, Any]:
    if not API_KEY:
        raise AIClientError(
            "尚未配置 AI 服务，请在服务端设置 DEEPSEEK_API_KEY 环境变量后重试"
        )

    body: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    for attempt in range(2):
        try:
            response = requests.post(
                f"{BASE_URL}/chat/completions", headers=headers, json=body, timeout=TIMEOUT
            )
        except requests.RequestException as exc:
            if attempt:
                raise AIClientError(f"AI 服务连接失败，请稍后重试（{exc}）") from exc
            continue

        if response.status_code == 200:
            payload = response.json()
            content = (payload.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            return {"content": content, "usage": payload.get("usage") or {}}

        # 非 200：尝试读出服务端错误信息
        detail = _extract_error(response)
        raise AIClientError(detail)

    raise AIClientError("AI 服务请求失败，请稍后重试")


def _extract_error(response: requests.Response) -> str:
    try:
        payload = response.json()
        message = (payload.get("error") or {}).get("message") or payload.get("message") or ""
        if message:
            return f"AI 服务返回错误：{message}"
    except (json.JSONDecodeError, AttributeError):
        pass
    code = response.status_code
    if code == 401:
        return "AI 服务鉴权失败，请检查 DEEPSEEK_API_KEY 是否正确"
    if code == 402:
        return "AI 服务余额不足，请充值后重试"
    if code == 429:
        return "AI 服务限流，请稍后重试"
    return f"AI 服务返回错误（HTTP {code}）"


def chat_json(
    messages: list[dict[str, Any]],
    max_tokens: int = 8192,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """要求模型返回 JSON，解析为 dict。messages 需在 prompt 中明确要求 JSON。"""
    body = list(messages)
    body.append(
        {
            "role": "system",
            "content": "你只输出一个合法的 JSON 对象，不要输出任何多余文字、代码块标记或注释。",
        }
    )
    result = _request(body, max_tokens, temperature)
    content = result["content"].strip()
    # 模型偶尔会包一层 ```json ... ```，剥掉
    content = _strip_code_fence(content)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIClientError(f"AI 返回的内容不是合法 JSON：{content[:200]}") from exc
    if not isinstance(parsed, dict):
        raise AIClientError("AI 返回结构异常，请重试")
    return parsed


def chat_text(
    messages: list[dict[str, Any]],
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    result = _request(list(messages), max_tokens, temperature)
    return result["content"].strip()


def _strip_code_fence(text: str) -> str:
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    return text.strip()
