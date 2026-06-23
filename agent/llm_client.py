"""
LLM API 调用封装
支持 OpenAI 兼容接口（通过环境变量配置）
"""

import os
import json
import requests
from typing import Generator

# 配置（通过环境变量设置，或在 .env 文件中配置）
API_BASE = os.environ.get("LLM_API_BASE", "https://api.openai.com/v1")
API_KEY = os.environ.get("LLM_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

if not API_KEY:
    print("[警告] 未设置 LLM_API_KEY 环境变量，请通过 export LLM_API_KEY=xxx 设置")


def chat_stream(messages: list, temperature: float = 0.7) -> Generator[str, None, None]:
    """
    流式调用 LLM Chat API
    yields 每个 token 的文本片段
    """
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

    try:
        resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
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
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
            except json.JSONDecodeError:
                continue
    except requests.exceptions.RequestException as e:
        yield f"\n\n[错误] LLM API 调用失败: {e}"


def chat_sync(messages: list, temperature: float = 0.7) -> str:
    """
    同步调用 LLM Chat API
    返回完整响应文本
    """
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
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[错误] LLM API 调用失败: {e}"
