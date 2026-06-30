"""
智能体基类
所有智能体继承此类，实现 build_messages() 即可
"""

import json
from abc import ABC, abstractmethod
from flask import Response, stream_with_context

from llm_client import chat_stream

# ── 全局自我认知（所有智能体共享，用于回答"你怎么工作的"）──
PLATFORM_INTROSPECTION = """
【平台机制说明 - 当你被问及自身工作原理时引用】
- 论文存储: 5586 篇论文，来自 NDSS/CCS/S&P/USENIX 四大顶会 (2018-2026)
- 搜索算法: TF-IDF 向量化 + 余弦相似度排序。先将所有论文摘要转为 TF-IDF 特征矩阵（50000 维），用户查询同样向量化后计算余弦相似度，返回最匹配的论文
- 多关键词扩展: 调用 LLM 从用户问题提取 3 组不同关键词/同义词，分别搜索后合并去重，提高召回率
- PDF 解析: 使用 PyMuPDF (fitz) 提取文本，按 MD5 缓存到 data/pdf_cache/，上传时返回全文（约 60K 字符/14 页论文）
- LLM 配置: 通过 config.json 配置 api_base / api_key / model / temperature / max_tokens，支持 OpenAI 兼容接口
- 会话持久化: 会话数据存储为 JSON 文件 (data/sessions.json)，包含消息历史、PDF 引用、平台归属
- 智能体架构: 每个智能体独立为一个 .py 文件，继承 BaseAgent，实现 build_messages()，自动注册到 Flask 路由
"""


class BaseAgent(ABC):
    """智能体基类"""

    name: str = ""       # 智能体名称，如 "literature"
    route: str = ""      # API 路由，如 "/api/chat"
    default_temp: float = 0.7  # 默认温度

    def __init__(self, store=None):
        pass

    @abstractmethod
    def build_messages(self, data: dict) -> list:
        """构建 LLM 消息列表（含 system prompt 和用户输入）"""
        ...

    def get_progress_info(self, data: dict) -> tuple:
        """返回初始进度 (percent, stage_text)"""
        return (5, "正在分析...")

    def handle(self, data: dict) -> Response:
        """处理请求，返回 SSE 流式响应"""
        user_query = data.get("message", "").strip()
        if not user_query:
            return {"error": "消息不能为空"}, 400

        temperature = data.get("temperature", self.default_temp)
        max_tokens = data.get("max_tokens", None)

        messages = self.build_messages(data)
        init_pct, init_stage = self.get_progress_info(data)

        def generate():
            yield self._progress(init_pct, init_stage)
            token_count = 0
            for token in chat_stream(messages, temperature=temperature, max_tokens=max_tokens):
                token_count += 1
                if token_count % 20 == 0:
                    pct = min(init_pct + token_count, 95)
                    yield self._progress(pct, "AI 正在生成回答...")
                yield f"data: {json.dumps({'token': token})}\n\n"

            yield self._progress(100, "完成")
            yield f"data: {json.dumps({'done': True})}\n\n"

        return Response(
            stream_with_context(generate()),
            content_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @staticmethod
    def _progress(percent: int, stage: str) -> str:
        """构造 SSE 进度事件"""
        return f"data: {json.dumps({'progress': percent, 'stage': stage})}\n\n"

    @staticmethod
    def _inject_pdf(user_content: str, pdf_context: str, pdf_filename: str) -> str:
        """将 PDF 上下文注入到用户消息中"""
        if not pdf_context:
            return user_content
        truncated = pdf_context[:60000]
        return (
            f"{user_content}\n\n"
            f"=== 用户上传的 PDF 文档（{pdf_filename}）===\n"
            f"{truncated}\n"
            f"=== PDF 内容结束 ==="
        )
