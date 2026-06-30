"""
会话导出：PDF (MD→HTML→WeasyPrint) + Markdown
"""

import re
from io import BytesIO

import markdown
from weasyprint import HTML, CSS

FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"

ROLE_CFG = {
    "user": {"label": "用户", "color": "#E87E24"},
    "assistant": {"label": "AI", "color": "#7C6FE0"},
}

RE_FIELD = re.compile(r"^([一-鿿]{2,8}[：:])\s*")

# ── Markdown 导出 ──

def export_session_markdown(session: dict, selected_indices: list[int] | None = None) -> str:
    title = session.get("title", "对话导出")
    messages = session.get("messages", [])

    if selected_indices is not None:
        messages = [messages[i] for i in selected_indices if i < len(messages)]

    lines = [f"# {title}\n", f"> 共 {len(messages)} 条消息\n", "---\n"]
    for i, msg in enumerate(messages):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        label = ROLE_CFG.get(role, ROLE_CFG["user"])["label"]
        lines.append(f"## {label} #{i + 1}\n")
        lines.append(content + "\n")
        lines.append("---\n")

    return "\n".join(lines)


# ── PDF 导出 (MD → HTML → WeasyPrint) ──

CSS_STYLES = """
@page {
  size: A4;
  margin: 25mm 20mm 25mm 20mm;
  @top-center {
    content: "";
  }
  @bottom-center {
    content: "";
  }
}

@page:first {
  @top-center { content: "" }
  @bottom-center { content: "" }
  margin-top: 30mm;
}

@font-face {
  font-family: "WQY";
  src: url("FONT_PLACEHOLDER");
  font-weight: normal;
  font-style: normal;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: "WQY", "SimSun", "Noto Sans CJK SC", serif;
  font-size: 10.5pt;
  line-height: 1.8;
  color: #373737;
}

/* ── 会话标题 ── */
h1.session-title {
  font-size: 22pt;
  color: #282828;
  text-align: center;
  margin-bottom: 6pt;
  font-weight: bold;
}
h1.session-title + hr {
  border: none;
  border-top: 0.6pt solid #7C6FE0;
  width: 60%;
  margin: 8pt auto 16pt auto;
}

/* ── 角色标签 ── */
.role-badge {
  display: inline-block;
  font-size: 11.5pt;
  font-weight: bold;
  color: #fff;
  padding: 1pt 10pt;
  border-radius: 0;
  margin-bottom: 6pt;
}

/* ── 消息容器 ── */
.message {
  margin-bottom: 14pt;
}

/* ── Markdown 元素 ── */

/* 段落：首行缩进两字 */
.message p {
  text-indent: 2em;
  margin-bottom: 4pt;
  text-align: justify;
}

/* 标题（消息内 h2-h4） */
.message h2 { font-size: 14pt; color: #7C6FE0; margin: 8pt 0 4pt 0; }
.message h3 { font-size: 13pt; color: #7C6FE0; margin: 6pt 0 3pt 0; }
.message h4 { font-size: 11pt; color: #7C6FE0; margin: 5pt 0 2pt 0; }

.message h2,
.message h3,
.message h4 {
  page-break-after: avoid;
}

/* 列表 */
.message ul, .message ol {
  margin: 2pt 0 4pt 0;
  padding-left: 2.5em;
}
.message li {
  margin-bottom: 1pt;
  text-align: justify;
}
.message li > ul,
.message li > ol {
  margin: 0;
  padding-left: 1.5em;
}

/* 代码块 */
.message pre {
  background: #f6f6f8;
  border-top: 2.5pt solid #7C6FE0;
  padding: 8pt 6pt;
  font-family: "Courier New", monospace;
  font-size: 8pt;
  line-height: 1.4;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 4pt 0 6pt 0;
}
.message code {
  font-family: "Courier New", monospace;
  font-size: 9pt;
  background: #f0f0f0;
  padding: 0 3pt;
  border-radius: 2pt;
}
.message pre code {
  background: none;
  padding: 0;
  border-radius: 0;
}

/* 引用 */
.message blockquote {
  color: #828282;
  font-size: 9.5pt;
  border-left: 2pt solid #c8c8c8;
  padding: 2pt 0 2pt 8pt;
  margin: 4pt 0 6pt 0;
}
.message blockquote p {
  text-indent: 0;
}

/* 水平线（消息分割） */
hr.message-sep {
  border: none;
  border-top: 0.3pt solid #ebebeb;
  margin: 10pt 0 12pt 0;
}

/* 表格（markdown extra 扩展） */
.message table {
  border-collapse: collapse;
  margin: 6pt 0;
  font-size: 9.5pt;
}
.message th, .message td {
  border: 0.5pt solid #ccc;
  padding: 3pt 6pt;
  text-align: left;
}
.message th {
  background: #eeeefc;
  font-weight: bold;
}
"""


def _build_html(title: str, messages: list[dict]) -> str:
    parts = ['<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"></head><body>']

    # 会话标题
    parts.append(f'<h1 class="session-title">{_escape_html(title)}</h1>')
    parts.append('<hr>')

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        cfg = ROLE_CFG.get(role, ROLE_CFG["user"])
        label = cfg["label"]
        color = cfg["color"]

        parts.append(f'<div class="message {role}">')
        parts.append(f'<span class="role-badge" style="background:{color};">{label}</span>')

        # 将消息内容转为 HTML
        html_body = markdown.markdown(
            content,
            extensions=["extra", "codehilite", "sane_lists"],
        )
        parts.append(html_body)
        parts.append('<hr class="message-sep">')
        parts.append("</div>")

    parts.append("</body></html>")
    return "\n".join(parts)


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _make_css() -> str:
    css = CSS_STYLES.replace("FONT_PLACEHOLDER", FONT_PATH)
    return css


def export_session_pdf(session: dict, selected_indices: list[int] | None = None) -> BytesIO:
    title = session.get("title", "对话导出")
    messages = session.get("messages", [])

    if selected_indices is not None:
        messages = [messages[i] for i in selected_indices if i < len(messages)]

    html_str = _build_html(title, messages)
    css_str = _make_css()

    buf = BytesIO()
    HTML(string=html_str).write_pdf(
        target=buf,
        stylesheets=[CSS(string=css_str)],
    )
    buf.seek(0)
    return buf
