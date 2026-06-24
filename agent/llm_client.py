"""
LLM API 调用封装
配置从 config.json 读取
"""

import os
import json
import requests
from pathlib import Path
from typing import Generator

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# 初始加载
_config = _load_config()
API_BASE = _config.get("api_base", os.environ.get("LLM_API_BASE", "https://api.openai.com/v1"))
API_KEY = _config.get("api_key", os.environ.get("LLM_API_KEY", ""))
MODEL = _config.get("model", os.environ.get("LLM_MODEL", "gpt-4o-mini"))


def reload_config():
    """热重载配置（由 config API 调用）"""
    global API_BASE, API_KEY, MODEL, _config
    _config = _load_config()
    API_BASE = _config.get("api_base", API_BASE)
    API_KEY = _config.get("api_key", API_KEY)
    MODEL = _config.get("model", MODEL)
    print(f"[配置] 已重载: model={MODEL}, base={API_BASE}")


if not API_KEY:
    print("[警告] 未配置 API Key，请在 agent/config.json 中设置或通过环境变量 LLM_API_KEY 指定")


def chat_stream(messages: list, temperature: float = 0.7, max_tokens: int = None) -> Generator[str, None, None]:
    """流式调用 LLM Chat API"""
    url = f"{API_BASE}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    try:
        resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
            except (json.JSONDecodeError, IndexError, KeyError):
                continue
    except requests.exceptions.RequestException as e:
        yield f"\n\n[错误] LLM API 调用失败: {e}"


def chat_sync(messages: list, temperature: float = 0.7) -> str:
    """同步调用 LLM Chat API"""
    url = f"{API_BASE}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[错误] LLM API 调用失败: {e}"
