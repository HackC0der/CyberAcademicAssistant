"""
通用对话智能体
无特定任务，正常对话
"""

from .base import BaseAgent


CHAT_SYSTEM_PROMPT = """你是一个 helpful 的 AI 助手。

- 用中文回答（除非用户用其他语言提问）
- 回答简洁、准确、有条理
- 不确定时坦诚说明"""


class ChatAgent(BaseAgent):
    name = "chat"
    route = "/api/chat-general"
    default_temp = 0.7

    def build_messages(self, data: dict) -> list:
        user_query = data.get("message", "").strip()
        history = data.get("history", [])
        pdf_context = data.get("pdf_context", "")
        pdf_filename = data.get("pdf_filename", "")

        messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

        if history:
            for msg in history[-10:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")[:2000],
                })

        user_content = self._inject_pdf(user_query, pdf_context, pdf_filename)
        messages.append({"role": "user", "content": user_content})
        return messages
