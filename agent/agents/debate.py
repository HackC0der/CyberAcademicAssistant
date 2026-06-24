"""
Idea 辩论智能体
审稿人模式：严厉质疑研究假设与贡献
导师模式：引导凝练科学问题与创新点
"""

import json
from flask import Response, stream_with_context

from .base import BaseAgent
from llm_client import chat_stream


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


class DebateAgent(BaseAgent):
    name = "debate"
    route = "/api/debate"
    default_temp = 0.8

    def __init__(self, store=None):
        pass  # 不需要论文库

    def get_progress_info(self, data: dict) -> tuple:
        pdf_context = data.get("pdf_context", "")
        pdf_filename = data.get("pdf_filename", "")
        if pdf_context:
            return (10, f"正在分析 PDF: {pdf_filename}...")
        return (10, "正在深度分析您的研究想法...")

    def build_messages(self, data: dict) -> list:
        user_query = data.get("message", "").strip()
        history = data.get("history", [])
        mode = data.get("mode", "reviewer")
        pdf_context = data.get("pdf_context", "")
        pdf_filename = data.get("pdf_filename", "")

        # 选择系统提示词
        if mode == "mentor":
            system_prompt = MENTOR_SYSTEM_PROMPT
        else:
            system_prompt = REVIEWER_SYSTEM_PROMPT

        messages = [{"role": "system", "content": system_prompt}]

        # 历史对话
        if history:
            for msg in history[-10:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")[:2000],
                })

        # 用户消息（含 PDF）
        user_content = self._inject_pdf(user_query, pdf_context, pdf_filename)
        messages.append({"role": "user", "content": user_content})

        return messages

    def handle(self, data: dict) -> Response:
        """重写 handle 以支持 done 事件中的 mode 字段"""
        user_query = data.get("message", "").strip()
        if not user_query:
            return {"error": "消息不能为空"}, 400

        mode = data.get("mode", "reviewer")
        temperature = data.get("temperature", self.default_temp)
        max_tokens = data.get("max_tokens", None)

        messages = self.build_messages(data)
        init_pct, init_stage = self.get_progress_info(data)

        def generate():
            yield self._progress(init_pct, init_stage)
            token_count = 0
            for token in chat_stream(messages, temperature=temperature, max_tokens=max_tokens):
                token_count += 1
                if token_count % 30 == 0:
                    pct = min(init_pct + token_count // 3, 95)
                    yield self._progress(pct, "正在生成分析...")
                yield f"data: {json.dumps({'token': token})}\n\n"

            yield self._progress(100, "完成")
            yield f"data: {json.dumps({'done': True, 'mode': mode})}\n\n"

        return Response(
            stream_with_context(generate()),
            content_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
