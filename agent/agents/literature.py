"""
文献匹配智能体
基于四大顶会论文库，语义匹配返回最相关论文
"""

from .base import BaseAgent
from llm_client import chat_sync


class LiteratureAgent(BaseAgent):
    name = "literature"
    route = "/api/chat"
    default_temp = 0.7

    def __init__(self, store):
        self.store = store

    def get_progress_info(self, data: dict) -> tuple:
        pdf_context = data.get("pdf_context", "")
        pdf_filename = data.get("pdf_filename", "")
        if pdf_context:
            return (5, f"正在分析 PDF: {pdf_filename}...")
        return (5, "正在分析您的课题...")

    def build_messages(self, data: dict) -> list:
        user_query = data.get("message", "").strip()
        history = data.get("history", [])
        pdf_context = data.get("pdf_context", "")
        pdf_filename = data.get("pdf_filename", "")

        if pdf_context:
            print(f"[PDF] 收到 PDF 上下文: {pdf_filename} ({len(pdf_context)} 字符)")

        # 提取关键词
        keywords = self._extract_keywords(user_query, history)

        # 检索论文库
        candidates = self.store.search(keywords, top_k=30)

        # 构建论文上下文
        papers_context = ""
        for i, (paper, score) in enumerate(candidates, 1):
            abstract_part = f"\n摘要: {paper.abstract[:500]}..." if paper.abstract else ""
            papers_context += f"\n[{i}] {paper.conference} {paper.year} - {paper.title}{abstract_part}\n"

        system_prompt = """你是一个学术文献匹配助手，专门服务于网络安全领域的研究者。
你的知识库包含四大顶会（NDSS、CCS、S&P、USENIX Security）2018-2026年的论文。

当用户描述自己的研究课题时，你需要：
1. 从候选论文中选出最相关的 5-10 篇
2. 按相关性从高到低排序
3. 对每篇论文，简要说明它与用户课题的关联（1-2句话）
4. 在最后给出一个简短的总结，归纳这些论文的共同主题

当用户要求"更多论文"或"再推荐一些"时，继续推荐之前未提及的论文，保持同一研究主题。

输出格式要求：
- 使用 Markdown 格式
- 每篇论文用编号列表，格式：**[序号] 会议 年份 - 标题**
- 关联说明紧跟其后，缩进显示
- 最后用 "---" 分隔，加上"总结"部分"""

        messages = [{"role": "system", "content": system_prompt}]

        # 历史对话
        if history:
            for msg in history[-6:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")[:500],
                })

        # 用户消息（含 PDF 或论文检索结果）
        if pdf_context:
            pdf_block = f"\n\n=== 用户上传的 PDF 文档（{pdf_filename}）===\n{pdf_context[:8000]}\n=== PDF 内容结束 ===\n"
            user_prompt = f"""当前请求:
{user_query}
{pdf_block}

以下是论文库中的相关候选论文（可作为补充参考）:
{papers_context}

请重点分析用户上传的 PDF 文档内容，回答用户的问题。论文库结果仅作为补充参考。用中文回答。"""
        else:
            user_prompt = f"""当前请求:
{user_query}

提取的搜索关键词: {keywords}

以下是从论文库中初步筛选出的候选论文（按相关度排序）:
{papers_context}

请从中选出最相关的论文，并解释它们与我课题的关联。如果是"更多论文"的请求，请推荐之前未提及的论文。用中文回答。"""

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _extract_keywords(self, query: str, history: list = None) -> str:
        """用 LLM 提取英文搜索关键词"""
        context_block = ""
        if history:
            recent = history[-6:]
            context_block = "\n\nRecent conversation context:\n"
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:300]
                context_block += f"{role}: {content}\n"

        messages = [
            {"role": "system", "content": f"You are a keyword extractor for academic paper search.{context_block}\nGiven the latest user message and the conversation context above, extract 5-10 English search keywords/phrases suitable for searching academic papers. If the user's message refers to a previous topic (e.g. 'more papers', 'show me 20 more'), infer the topic from context. Output ONLY the keywords, separated by spaces, no explanations."},
            {"role": "user", "content": query},
        ]
        return chat_sync(messages, temperature=0.1).strip()
