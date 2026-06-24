"""
学术智能体平台 - Flask 入口
负责：会话管理、PDF上传、智能体路由注册
"""

import json
import os
import time
import random
import threading
from pathlib import Path

from flask import Flask, render_template, request, jsonify

from paper_store import PaperStore
from pdf_utils import parse_pdf
from agents import discover_agents

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_FILE = Path(__file__).resolve().parent / "data" / "sessions.json"

app = Flask(__name__)

# ========== 会话持久化 ==========

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


# ========== 初始化论文库 ==========

print("正在加载论文数据...")
store = PaperStore(str(PROJECT_ROOT))
paper_count = store.load()
print(f"论文库加载完成: 共 {paper_count} 篇论文")


# ========== 配置管理 ==========

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=4), encoding="utf-8")


@app.route("/api/config", methods=["GET"])
def api_get_config():
    cfg = load_config()
    # 脱敏：不返回完整 key
    safe = {**cfg}
    if safe.get("api_key"):
        safe["api_key"] = safe["api_key"][:8] + "..." if len(safe["api_key"]) > 8 else safe["api_key"]
    return jsonify(safe)


@app.route("/api/config", methods=["POST"])
def api_set_config():
    data = request.get_json()
    cfg = load_config()
    for key in ("api_base", "api_key", "model", "temperature", "max_tokens"):
        if key in data:
            cfg[key] = data[key]
    save_config(cfg)
    # 重新加载 llm_client 配置
    import llm_client
    llm_client.reload_config()
    return jsonify({"ok": True})


# ========== 页面路由 ==========

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def stats():
    return jsonify(store.get_stats())


# ========== 会话 API ==========

@app.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    return jsonify(load_sessions())


@app.route("/api/sessions", methods=["POST"])
def api_create_session():
    data = request.get_json()
    session = {
        "id": f"sess_{int(time.time() * 1000)}_{random.choice('abcdefghijklmnopqrstuvwxyz0123456789') * 4}",
        "title": data.get("title", "新对话"),
        "messages": [],
        "createdAt": int(time.time() * 1000),
    }
    save_session(session)
    return jsonify(session)


@app.route("/api/sessions/<sid>", methods=["PUT"])
def api_update_session(sid):
    data = request.get_json()
    sessions = load_sessions()
    session = next((s for s in sessions if s["id"] == sid), None)
    if not session:
        return jsonify({"error": "会话不存在"}), 404
    for key in ("title", "messages", "createdAt"):
        if key in data:
            session[key] = data[key]
    save_session(session)
    return jsonify(session)


@app.route("/api/sessions/<sid>", methods=["DELETE"])
def api_delete_session(sid):
    delete_session(sid)
    return jsonify({"ok": True})


# ========== PDF 上传 ==========

@app.route("/api/upload-pdf", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "未上传文件"}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "仅支持 PDF 文件"}), 400

    try:
        result = parse_pdf(file.read())
        result["filename"] = file.filename
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"PDF 解析失败: {str(e)}"}), 500


# ========== 论文搜索 ==========

@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json()
    query = data.get("query", "").strip()
    top_k = data.get("top_k", 10)

    if not query:
        return jsonify({"error": "查询不能为空"}), 400

    results = store.search(query, top_k=top_k)
    return jsonify({
        "results": [
            {"paper": paper.to_dict(), "score": round(score, 4)}
            for paper, score in results
        ]
    })


# ========== 智能体注册 ==========

def register_agents():
    """自动发现并注册所有智能体路由"""
    agent_classes = discover_agents()
    for cls in agent_classes:
        try:
            agent = cls(store=store)
            app.add_url_rule(
                agent.route,
                endpoint=agent.name,
                view_func=lambda a=agent: a.handle(request.get_json()),
                methods=["POST"],
            )
            print(f"  已注册智能体: {agent.name} -> {agent.route}")
        except Exception as e:
            print(f"  [警告] 注册智能体 {cls.__name__} 失败: {e}")


register_agents()


# ========== 启动 ==========

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n启动服务: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
