"""
文献匹配智能体 - Flask 主应用
提供 ChatGPT 风格的 Web 对话界面，基于四大顶会论文库进行语义匹配
"""

import json
import sys
import os
from pathlib import Path

from flask import Flask, render_template, request, Response, jsonify, stream_with_context

from paper_store import PaperStore
from llm_client import chat_stream, chat_sync

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

app = Flask(__name__)

# 初始化论文库
print("正在加载论文数据...")
store = PaperStore(str(PROJECT_ROOT))
paper_count = store.load()
print(f"论文库加载完成: 共 {paper_count} 篇论文")


@app.route("/")
def index():
    """主页面"""
    return render_template("index.html")


@app.route("/api/stats")
def stats():
    """论文库统计"""
    return jsonify(store.get_stats())


def extract_keywords(query: str, history: list = None) -> str:
    """用 LLM 从用户查询中提取英文搜索关键词，结合历史对话上下文"""
    # 如果有历史对话，构建上下文摘要帮助理解 "再来20篇" 这类指代性请求
    context_block = ""
    if history:
        recent = history[-6:]  # 取最近 3 轮对话
        context_block = "\n\nRecent conversation context:\n"
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:300]
            context_block += f"{role}: {content}\n"

    messages = [
        {"role": "system", "content": f"You are a keyword extractor for academic paper search.{context_block}\nGiven the latest user message and the conversation context above, extract 5-10 English search keywords/phrases suitable for searching academic papers. If the user's message refers to a previous topic (e.g. 'more papers', 'show me 20 more'), infer the topic from context. Output ONLY the keywords, separated by spaces, no explanations."},
        {"role": "user", "content": query},
    ]
    keywords = chat_sync(messages, temperature=0.1)
    return keywords.strip()


@app.route("/api/chat", methods=["POST"])
def chat():
    """对话接口 - SSE 流式响应，带真实进度"""
    data = request.get_json()
    user_query = data.get("message", "").strip()
    # 历史对话（前端传入，用于上下文连贯）
    history = data.get("history", [])
    if not user_query:
        return jsonify({"error": "消息不能为空"}), 400

    def generate():
        # ── Stage 1: 提取关键词 (0% → 30%) ──
        yield _progress(5, "正在分析您的课题...")
        keywords = extract_keywords(user_query, history)
        yield _progress(25, f"已提取关键词: {keywords}")
        yield _progress(30, "关键词提取完成")

        # ── Stage 2: 检索论文库 (30% → 50%) ──
        yield _progress(35, f"正在从 {len(store.papers)} 篇论文中检索...")
        candidates = store.search(keywords, top_k=30)
        yield _progress(50, f"找到 {len(candidates)} 篇候选论文")

        if not candidates:
            yield f"data: {json.dumps({'token': '未找到相关论文，请尝试换个角度描述您的课题。'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

        # ── Stage 3: 构建上下文 & 调用 LLM 排序 (50% → 100%) ──
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

        # 构建 LLM 消息：system + 历史对话摘要 + 当前请求
        messages = [{"role": "system", "content": system_prompt}]

        # 添加历史对话（仅取最近几轮，避免 token 过长）
        if history:
            for msg in history[-6:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")[:500],
                })

        user_prompt = f"""当前请求:
{user_query}

提取的搜索关键词: {keywords}

以下是从论文库中初步筛选出的候选论文（按相关度排序）:
{papers_context}

请从中选出最相关的论文，并解释它们与我课题的关联。如果是"更多论文"的请求，请推荐之前未提及的论文。用中文回答。"""

        messages.append({"role": "user", "content": user_prompt})

        yield _progress(55, "AI 正在语义分析与排序...")
        token_count = 0
        for token in chat_stream(messages):
            token_count += 1
            # 每收到一定量 token 后更新进度（55% → 95%）
            if token_count % 20 == 0:
                pct = min(55 + token_count, 95)
                yield _progress(pct, "AI 正在生成回答...")
            yield f"data: {json.dumps({'token': token})}\n\n"

        yield _progress(100, "完成")
        yield f"data: {json.dumps({'done': True, 'candidate_count': len(candidates)})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _progress(percent: int, stage: str) -> str:
    """构造进度事件 SSE 数据"""
    return f"data: {json.dumps({'progress': percent, 'stage': stage})}\n\n"


@app.route("/api/search", methods=["POST"])
def search():
    """直接搜索接口 - 不经过 LLM，返回 TF-IDF 搜索结果"""
    data = request.get_json()
    query = data.get("query", "").strip()
    top_k = data.get("top_k", 10)

    if not query:
        return jsonify({"error": "查询不能为空"}), 400

    results = store.search(query, top_k=top_k)
    return jsonify({
        "results": [
            {
                "paper": paper.to_dict(),
                "score": round(score, 4),
            }
            for paper, score in results
        ]
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n启动服务: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
