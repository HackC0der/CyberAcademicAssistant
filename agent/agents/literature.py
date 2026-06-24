"""
文献匹配智能体
多关键词扩展搜索，优先覆盖全部论文库
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

        # ── 多关键词扩展搜索 ──
        keyword_sets = self._expand_keywords(user_query, history)
        all_candidates = self._multi_search(keyword_sets, per_query_top_k=25)

        # 构建论文上下文
        papers_context = ""
        for i, (paper, score) in enumerate(all_candidates, 1):
            abstract_part = f"\n摘要: {paper.abstract[:500]}..." if paper.abstract else ""
            papers_context += f"\n[{i}] {paper.conference} {paper.year} - {paper.title}{abstract_part}\n"

        total = len(all_candidates)
        kw_display = " | ".join(keyword_sets[:3])

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

        if history:
            for msg in history[-6:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")[:500],
                })

        # PDF 上下文
        if pdf_context:
            pdf_block = f"\n\n=== 用户上传的 PDF 文档（{pdf_filename}）===\n{pdf_context[:8000]}\n=== PDF 内容结束 ===\n"
            user_prompt = f"""当前请求:
{user_query}
{pdf_block}

以下是论文库中的相关候选论文（共 {total} 篇，使用关键词: {kw_display}）:
{papers_context}

请重点分析用户上传的 PDF 文档内容，回答用户的问题。论文库结果仅作为补充参考。用中文回答。"""
        else:
            user_prompt = f"""当前请求:
{user_query}

搜索关键词（多组扩展）: {kw_display}
候选论文数量: {total}

以下是从论文库中筛选出的候选论文:
{papers_context}

请从中选出最相关的论文，并解释它们与我课题的关联。如果是"更多论文"的请求，请推荐之前未提及的论文。用中文回答。"""

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _expand_keywords(self, query: str, history: list = None) -> list:
        """
        用 LLM 提取多组关键词（主关键词 + 同义词/相关词扩展）
        返回: ["keyword_set_1", "keyword_set_2", ...]
        """
        context_block = ""
        if history:
            recent = history[-6:]
            context_block = "\n\nRecent conversation context:\n"
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:300]
                context_block += f"{role}: {content}\n"

        messages = [
            {"role": "system", "content": f"""You are a keyword extractor for academic paper search.{context_block}

Given the user's research topic, generate 3 DIFFERENT sets of English search keywords.
Each set should use different terminology, synonyms, or related concepts to maximize coverage.

Rules:
- Set 1: Direct keywords from the query
- Set 2: Synonyms and related technical terms
- Set 3: Broader/adjacent concepts

Output format (one set per line, keywords separated by spaces):
set1_keyword1 set1_keyword2 set1_keyword3
set2_keyword1 set2_keyword2 set2_keyword3
set3_keyword1 set3_keyword2 set3_keyword3

Output ONLY the keyword lines, nothing else."""},
            {"role": "user", "content": query},
        ]

        result = chat_sync(messages, temperature=0.2)
        lines = [l.strip() for l in result.strip().split('\n') if l.strip()]
        # 至少返回一组
        if not lines:
            lines = [query]
        return lines[:3]  # 最多 3 组

    def _multi_search(self, keyword_sets: list, per_query_top_k: int = 25) -> list:
        """
        用多组关键词搜索，合并去重，按最高分数排序
        """
        seen_ids = set()
        merged = []

        for kw_set in keyword_sets:
            results = self.store.search(kw_set, top_k=per_query_top_k)
            for paper, score in results:
                pid = (paper.conference, paper.year, paper.title)
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    merged.append((paper, score))

        # 按分数降序排序
        merged.sort(key=lambda x: x[1], reverse=True)
        return merged
