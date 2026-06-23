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


def extract_keywords(query: str) -> str:
    """用 LLM 从用户查询中提取英文搜索关键词"""
    messages = [
        {"role": "system", "content": "You are a keyword extractor. Given a research topic description (possibly in Chinese), extract 5-10 English search keywords/phrases suitable for searching academic papers. Output ONLY the keywords, separated by spaces, no explanations. Example input: '我对联邦学习中的隐私攻击感兴趣' Output: federated learning privacy attack gradient leakage membership inference"},
        {"role": "user", "content": query},
    ]
    keywords = chat_sync(messages, temperature=0.1)
    return keywords.strip()


@app.route("/api/chat", methods=["POST"])
def chat():
    """对话接口 - SSE 流式响应"""
    data = request.get_json()
    user_query = data.get("message", "").strip()
    if not user_query:
        return jsonify({"error": "消息不能为空"}), 400

    # 1. 用 LLM 提取英文关键词（支持中文输入）
    def generate():
        # 先发送状态提示
        yield f"data: {json.dumps({'token': '🔍 正在分析您的课题并检索相关论文...\n\n'})}\n\n"

        keywords = extract_keywords(user_query)

        # 2. TF-IDF 初筛（用英文关键词搜索）
        candidates = store.search(keywords, top_k=30)

        if not candidates:
            yield f"data: {json.dumps({'token': '未找到相关论文，请尝试换个角度描述您的课题。'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

        # 3. 构建候选论文上下文
        papers_context = ""
        for i, (paper, score) in enumerate(candidates, 1):
            papers_context += f"\n[{i}] {paper.conference} {paper.year} - {paper.title}\n摘要: {paper.abstract[:500]}...\n"

        # 4. 构建 LLM prompt
        system_prompt = """你是一个学术文献匹配助手，专门服务于网络安全领域的研究者。
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
- 最后用 "---" 分隔，加上"总结"部分"""

        user_prompt = f"""我的研究课题/兴趣:
{user_query}

提取的搜索关键词: {keywords}

以下是从论文库中初步筛选出的候选论文（按相关度排序）:
{papers_context}

请从中选出最相关的论文，并解释它们与我课题的关联。用中文回答。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 5. 流式返回 LLM 响应
        for token in chat_stream(messages):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield f"data: {json.dumps({'done': True, 'candidate_count': len(candidates)})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
