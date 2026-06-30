"""
文献匹配智能体
多关键词扩展搜索，优先覆盖全部论文库
"""

from .base import BaseAgent, PLATFORM_INTROSPECTION
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

        # ── 判断意图：搜索推荐 vs 普通对话 ──
        is_search = self._is_search_intent(user_query, history)

        if is_search:
            # ── 多关键词扩展搜索 ──
            keyword_sets = self._expand_keywords(user_query, history)
            all_candidates = self._multi_search(keyword_sets, per_query_top_k=300)

            # 构建论文上下文（最多送 80 篇给 LLM，避免超长上下文）
            MAX_CANDIDATES = 80
            papers_context = ""
            top_candidates = all_candidates[:MAX_CANDIDATES]
            for i, (paper, score) in enumerate(top_candidates, 1):
                abstract_part = f"\n摘要: {paper.abstract[:500]}..." if paper.abstract else ""
                papers_context += f"\n[{i}] {paper.conference} {paper.year} - {paper.title}{abstract_part}\n"

            total = len(top_candidates)
            kw_display = " | ".join(keyword_sets[:3])
            search_info = f"\n\n搜索关键词（多组扩展）: {kw_display}\n候选论文数量: {total}\n\n以下是论文库中筛选出的候选论文:\n{papers_context}"
        else:
            search_info = ""
            total = 0
            kw_display = ""
            papers_context = ""

        # ── 选择 system prompt ──
        if is_search and not history:
            system_prompt = f"""你是一个学术文献匹配助手，专门服务于网络安全领域的研究者。
你的知识库包含四大顶会（NDSS、CCS、S&P、USENIX Security）2018-2026年的论文。

当用户描述自己的研究课题时，你需要：
1. 从候选论文中选出最相关的 5-10 篇
2. 按相关性从高到低排序
3. 对每篇论文，简要说明它与用户课题的关联（1-2句话）
4. 在最后给出一个简短的总结，归纳这些论文的共同主题

输出格式要求：
- 使用 Markdown 格式
- 每篇论文用编号列表，格式：**[序号] 会议 年份 - 标题**
- 关联说明紧跟其后，缩进显示
- 最后用 "---" 分隔，加上"总结"部分

【自我认知 - 当用户询问你怎么工作时引用】
我的工作流程：
1. 多关键词扩展: 调用 LLM 从用户问题提取 3 组不同关键词/同义词，提高召回
2. TF-IDF 检索: 每组关键词转为 TF-IDF 向量，与 5586 篇论文的摘要向量做余弦相似度
3. 合并排序: 3 组结果合并去重，按分数降序排列，取前 80 篇
4. LLM 精排: 阅读候选论文的标题和摘要，选出最相关的 5-10 篇
{PLATFORM_INTROSPECTION}"""
        else:
            system_prompt = f"""你是一个网络安全领域的 AI 研究助手，知识库包含四大顶会（NDSS、CCS、S&P、USENIX Security）2018-2026年的论文。

你可以做以下事情：
1. **搜索论文**：用户要求推荐/查找相关论文时，我会从论文库中检索匹配
2. **回答论文相关问题**：用户询问某篇论文的细节时，根据你的知识回答
3. **一般讨论**：用户讨论网络安全研究话题时，给出专业的见解

当前模式：{"完整搜索模式 - 已检索论文库并附上候选论文" if is_search else "对话模式 - 根据已有知识和上下文回答"}
{PLATFORM_INTROSPECTION}"""

        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for msg in history[-6:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")[:500],
                })

        # PDF 上下文
        if pdf_context:
            pdf_block = f"\n\n=== 用户上传的 PDF 文档（{pdf_filename}）===\n{pdf_context[:60000]}\n=== PDF 内容结束 ===\n"
            if is_search:
                user_prompt = f"""当前请求:
{user_query}
{pdf_block}

以下是论文库中的相关候选论文（共 {total} 篇，使用关键词: {kw_display}）:
{papers_context}

请重点分析用户上传的 PDF 文档内容，回答用户的问题。论文库结果仅作为补充参考。用中文回答。"""
            else:
                user_prompt = f"""当前请求:
{user_query}
{pdf_block}

请根据 PDF 内容和你的知识回答用户的问题。用中文回答。"""
        else:
            if is_search:
                user_prompt = f"""当前请求:
{user_query}

搜索关键词（多组扩展）: {kw_display}
候选论文数量: {total}

以下是从论文库中筛选出的候选论文:
{papers_context}

请从中选出最相关的论文，并解释它们与我课题的关联。如果是"更多论文"的请求，请推荐之前未提及的论文。用中文回答。"""
            else:
                user_prompt = f"""当前请求:
{user_query}

（此问题无需搜索论文库，根据已有知识回答即可）用中文回答。"""

        messages.append({"role": "user", "content": user_prompt})
        return messages

    @staticmethod
    def _is_search_intent(query: str, history: list = None) -> bool:
        """用 LLM 进行语义分析，判断用户是否需要搜索论文库"""
        context_block = ""
        if history:
            recent = history[-4:]
            lines = []
            for msg in recent:
                role = "用户" if msg.get("role") == "user" else "AI"
                content = msg.get("content", "")[:200]
                lines.append(f"{role}: {content}")
            context_block = "\n".join(lines)

        system_prompt = f"""You are an intent classifier for an academic literature matching system.
Classify the user's intent into exactly ONE category.

Categories:
- search: User wants paper recommendations, searching for papers, finding related work. They explicitly ask for paper suggestions.
- meta: User is asking about how the system works, its technology, internal mechanism, or how it operates. They do NOT want paper results.
- detail: User is asking about a specific paper already mentioned, requesting explanation, comparison, or deeper analysis of previous results.
- chat: General conversation, domain questions, or anything else not requiring paper search.

Respond with ONLY the category word: search, meta, detail, or chat.

{"Recent conversation:\n" + context_block if context_block else ""}"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        result = chat_sync(messages, temperature=0.1).strip().lower()
        is_search = result == "search"
        print(f"[意图] query={query[:60]}... → {result} {'🔍 执行搜索' if is_search else '💬 对话模式'}")
        return is_search

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
