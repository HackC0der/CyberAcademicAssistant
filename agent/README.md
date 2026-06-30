# 文献匹配智能体

基于四大顶会（NDSS、CCS、S&P、USENIX Security）论文库的智能文献匹配系统。

## 功能

- **自然语言检索**：用中文或英文描述研究课题，AI 自动匹配相关论文
- **语义理解**：TF-IDF 初筛 + LLM 语义排序，精准返回最相关论文
- **ChatGPT 风格界面**：流式输出，实时显示匹配结果
- **会话导出**：Markdown / PDF 导出，支持选择特定消息导出

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务（默认端口 5000）
python app.py

# 或指定端口
PORT=8080 python app.py
```

浏览器访问 http://localhost:5000

## 配置

通过环境变量配置 LLM API：

```bash
export LLM_API_BASE="https://api.openai.com/v1"  # API 地址
export LLM_API_KEY="your-api-key"                  # API 密钥
export LLM_MODEL="gpt-4o-mini"                     # 模型名称
```

默认使用小米 MiMo API（mimo-v2.5-pro）。

## 技术架构

```
用户输入 → LLM提取关键词 → TF-IDF初筛(top-30) → LLM语义排序+生成回答 → 流式输出
```

## 文件结构

```
agent/
├── app.py              # Flask 主应用
├── paper_store.py      # 论文数据加载与索引
├── llm_client.py       # LLM API 调用封装
├── pdf_export.py       # 会话导出 PDF/Markdown（MD→HTML→WeasyPrint）
├── requirements.txt    # Python 依赖
├── static/
│   ├── style.css       # ChatGPT 风格 UI
│   └── app.js          # 前端交互逻辑
└── templates/
    └── index.html      # 主页面模板
```

## 致谢

- PDF 导出受 [md2pdf](https://github.com/jmaupetit/md2pdf) 项目启发，采用 Markdown → HTML → WeasyPrint 管线。
