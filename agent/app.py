"""
学术智能体平台 - Flask 主应用
包含：文献匹配智能体、Idea 辩论智能体、PDF 解读
"""

import json
import sys
import os
import io
import base64
import threading
from pathlib import Path

from flask import Flask, render_template, request, Response, jsonify, stream_with_context

import fitz  # PyMuPDF

from paper_store import PaperStore
from llm_client import chat_stream, chat_sync

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_FILE = Path(__file__).resolve().parent / "data" / "sessions.json"

app = Flask(__name__)

# ========== 会话持久化（服务端 JSON 文件存储） ==========

_sessions_lock = threading.Lock()


def _ensure_data_dir():
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_sessions_raw() -> list:
    _ensure_data_dir()
    if not SESSIONS_FILE.exists():
        return []
    try:
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_sessions_raw(sessions: list):
    _ensure_data_dir()
    SESSIONS_FILE.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")


def load_sessions() -> list:
    with _sessions_lock:
        return _load_sessions_raw()


def save_session(session: dict):
    with _sessions_lock:
        sessions = _load_sessions_raw()
        idx = next((i for i, s in enumerate(sessions) if s["id"] == session["id"]), -1)
        if idx >= 0:
            sessions[idx] = session
        else:
            sessions.insert(0, session)
        _save_sessions_raw(sessions)


def delete_session(sid: str):
    with _sessions_lock:
        sessions = [s for s in _load_sessions_raw() if s["id"] != sid]
        _save_sessions_raw(sessions)

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


# ========== 会话 API ==========

@app.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    """获取所有会话列表"""
    return jsonify(load_sessions())


@app.route("/api/sessions", methods=["POST"])
def api_create_session():
    """创建新会话"""
    data = request.get_json()
    session = {
        "id": "sess_" + str(int(__import__("time").time() * 1000)) + "_" + __import__("random").choice("abcdefghijklmnopqrstuvwxyz0123456789") * 4,
        "title": data.get("title", "新对话"),
        "messages": [],
        "createdAt": int(__import__("time").time() * 1000),
    }
    save_session(session)
    return jsonify(session)


@app.route("/api/sessions/<sid>", methods=["PUT"])
def api_update_session(sid):
    """更新会话（消息、标题等）"""
    data = request.get_json()
    sessions = load_sessions()
    session = next((s for s in sessions if s["id"] == sid), None)
    if not session:
        return jsonify({"error": "会话不存在"}), 404
    # 合并更新字段
    for key in ("title", "messages", "createdAt"):
        if key in data:
            session[key] = data[key]
    save_session(session)
    return jsonify(session)


@app.route("/api/sessions/<sid>", methods=["DELETE"])
def api_delete_session(sid):
    """删除会话"""
    delete_session(sid)
    return jsonify({"ok": True})


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
    history = data.get("history", [])
    # PDF 上下文（可选）
    pdf_context = data.get("pdf_context", "")
    pdf_filename = data.get("pdf_filename", "")
    # LLM 设置
    temperature = data.get("temperature", 0.7)
    max_tokens = data.get("max_tokens", None)
    if not user_query:
        return jsonify({"error": "消息不能为空"}), 400

    if pdf_context:
        print(f"[PDF] 收到 PDF 上下文: {pdf_filename} ({len(pdf_context)} 字符)")

    def generate():
        if pdf_context:
            yield _progress(5, f"正在分析 PDF: {pdf_filename}...")
        else:
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

        # PDF 上下文（如果有）
        pdf_block = ""
        if pdf_context:
            truncated = pdf_context[:8000]
            pdf_block = f"\n\n=== 用户上传的 PDF 文档（{pdf_filename}）===\n{truncated}\n=== PDF 内容结束 ===\n"

        if pdf_context:
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

        yield _progress(55, "AI 正在语义分析与排序...")
        token_count = 0
        for token in chat_stream(messages, temperature=temperature, max_tokens=max_tokens):
            token_count += 1
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


# ========== Idea 辩论智能体 ==========

REVIEWER_SYSTEM_PROMPT = """你是一位网络安全领域的顶级会议（IEEE S&P、USENIX Security、CCS、NDSS）资深审稿人。你的任务是与研究者就其研究课题进行深度、严厉但建设性的批判性对话。

## 你的行为准则

1. **毫不留情地质疑**：你的目标是找出研究想法中所有逻辑脆弱、假设过强、贡献不足的地方。你要像最严厉的审稿人一样，用最锋利的手术刀解剖每一个假设。

2. **质疑的层次**：
   - **定义层面**：研究问题的边界是否清晰？"你究竟在做什么？"是你要反复追问的。
   - **假设层面**：你依赖了哪些隐式假设？这些假设在真实世界中成立吗？
   - **贡献层面**：这是工程贡献还是科学贡献？有没有不可约减的创新内核？
   - **增量层面**：与现有工作（尤其是最新的LLM工具）相比，你的增量在哪里？
   - **验证层面**：你如何证明你的方法有效？实验设计是否有cherry-picking？

3. **质疑的结构**：每次给出 3-5 个具体、尖锐的质疑，每个质疑都要：
   - 明确指出问题所在
   - 解释为什么这是一个致命问题
   - 要求研究者给出具体回应

4. **不允许模糊回答**：如果研究者的回应含糊其辞，你要追问到底，直到得到精确的定义或承认不确定性。

5. **发现闪光点**：虽然你以质疑为主，但当你发现一个真正坚不可摧的想法时，要明确指出"这一点经得起推敲"。

## 输出格式
- 使用 Markdown
- 每个质疑用编号
- 关键术语用 **加粗**
- 用 `---` 分隔不同的质疑主题"""

MENTOR_SYSTEM_PROMPT = """你是一位网络安全领域的资深教授和博士生导师。你的任务是帮助研究者将其研究想法打磨成顶会论文级别的科学贡献。

## 你的行为准则

1. **建设性引导**：你不是来打击学生的，而是帮助他们找到"坚不可摧的核心创新点"。当学生的想法有潜力但不成熟时，你要指出方向而不是直接否定。

2. **问题降级**：当学生的想法过于宏大时，帮助他们将问题分解为可管理的子问题。"不做万能神药，做精确的补丁"。

3. **科学问题导向**：
   - 先明确"要解决的科学问题是什么"
   - 再思考"用什么设计来解决"
   - 最后考虑"如何验证"
   - 绝不允许"有了设计却说不清解决什么问题"

4. **创新点凝练**：帮助学生提炼 2-3 个清晰、互补、不可替代的创新点。每个创新点必须：
   - 回答一个明确的科学问题
   - 有独特的算法/方法论内核
   - 有可操作的验证标准

5. **务实落地**：
   - 不要"为了学术而学术"的包装
   - 关注"水涨船高"的设计（LLM越强，系统越强）
   - 建议最小可行的行动步骤

6. **切换模式的能力**：当需要严厉审视时，你可以临时切换为审稿人视角进行批判，然后切回导师模式给出改进建议。

## 输出格式
- 使用 Markdown
- 层次清晰，用标题组织
- 关键洞察用 **加粗** 或 > 引用
- 给出具体的、可执行的下一步建议"""



def _progress(percent: int, stage: str) -> str:
    """构造进度事件 SSE 数据"""
    return f"data: {json.dumps({'progress': percent, 'stage': stage})}\n\n"


@app.route("/api/debate", methods=["POST"])
def debate():
    """Idea 辩论智能体 - SSE 流式响应"""
    data = request.get_json()
    user_query = data.get("message", "").strip()
    history = data.get("history", [])
    mode = data.get("mode", "reviewer")
    pdf_context = data.get("pdf_context", "")
    pdf_filename = data.get("pdf_filename", "")
    # LLM 设置
    temperature = data.get("temperature", 0.8)
    max_tokens = data.get("max_tokens", None)

    if not user_query:
        return jsonify({"error": "消息不能为空"}), 400

    if mode == "mentor":
        system_prompt = MENTOR_SYSTEM_PROMPT
    else:
        system_prompt = REVIEWER_SYSTEM_PROMPT

    messages = [{"role": "system", "content": system_prompt}]

    if history:
        for msg in history[-10:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")[:2000],
            })

    # 附带 PDF 上下文
    user_content = user_query
    if pdf_context:
        truncated = pdf_context[:8000]
        user_content = f"{user_query}\n\n=== 用户上传的 PDF 文档（{pdf_filename}）===\n{truncated}\n=== PDF 内容结束 ==="

    messages.append({"role": "user", "content": user_content})

    def generate():
        if pdf_context:
            yield _progress(10, f"正在分析 PDF: {pdf_filename}...")
        else:
            yield _progress(10, "正在深度分析您的研究想法...")
        token_count = 0
        for token in chat_stream(messages, temperature=temperature, max_tokens=max_tokens):
            token_count += 1
            if token_count % 30 == 0:
                yield _progress(min(10 + token_count // 3, 95), "正在生成分析...")
            yield f"data: {json.dumps({'token': token})}\n\n"

        yield _progress(100, "完成")
        yield f"data: {json.dumps({'done': True, 'mode': mode})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ========== PDF 解读 ==========

@app.route("/api/upload-pdf", methods=["POST"])
def upload_pdf():
    """上传并解析 PDF，返回提取的文本和图片"""
    if "file" not in request.files:
        return jsonify({"error": "未上传文件"}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "仅支持 PDF 文件"}), 400

    try:
        pdf_bytes = file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        pages_text = []
        images_b64 = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # 提取文本
            text = page.get_text("text").strip()
            if text:
                pages_text.append(f"--- 第 {page_num + 1} 页 ---\n{text}")

            # 提取图片
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image and base_image.get("image"):
                        img_bytes = base_image["image"]
                        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                        ext = base_image.get("ext", "png")
                        images_b64.append({
                            "page": page_num + 1,
                            "index": img_index,
                            "ext": ext,
                            "data": img_b64,
                        })
                except Exception:
                    continue

        doc.close()

        full_text = "\n\n".join(pages_text)

        return jsonify({
            "filename": file.filename,
            "pages": len(pages_text),
            "text": full_text,
            "text_length": len(full_text),
            "images": images_b64,
        })

    except Exception as e:
        return jsonify({"error": f"PDF 解析失败: {str(e)}"}), 500


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
