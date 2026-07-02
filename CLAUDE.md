# 4TH-CyberSecurityConference

## 项目概述

网络安全四大顶会（NDSS、CCS、S&P、USENIX）论文爬虫 + 学术智能体平台。

## 技术栈

- Python 3.x, Flask, scikit-learn, PyMuPDF
- 前端: 原生 HTML/CSS/JS
- LLM: OpenAI 兼容接口

## 目录结构

```
├── crawlers/               # 四个会议的爬虫脚本
├── agent/                  # 智能体平台
│   ├── agents/             # 可插拔智能体模块
│   │   ├── base.py         # BaseAgent 基类
│   │   ├── literature.py
│   │   └── debate.py
│   ├── app.py              # Flask 入口
│   ├── llm_client.py       # LLM API
│   ├── paper_store.py      # TF-IDF 论文检索（从 security-top4-papers.json 加载）
│   ├── pdf_utils.py        # PDF 解析
│   └── config.json         # LLM 配置
├── NDSS/ USENIX/ S&P/ CCS/ # 论文数据（旧格式，仅向后兼容）
├── security-top4-papers.json  # 统一数据集（3347 篇，96% 含摘要）
├── export_all.py              # 导出统一 JSON
├── enrich_abstracts.py        # 摘要补全脚本
├── verify_links.py            # PDF 链接验证
└── crawl_all.sh
```

## 数据源

`agent/paper_store.py` 优先加载 `security-top4-papers.json`（来自 [security-top4-papers](https://github.com/HackC0der/security-top4-papers) 数据集）。若文件不存在则降级解析 `NDSS/` `CCS/` `S&P/` `USENIX/` 目录下的旧格式 `abstracts.md`。

如需更新数据：
```bash
# 从 security-top4-papers 仓库同步后
cp /path/to/security-top4-papers/security-top4-papers.json .
uv run python export_all.py  # 重新生成
```

## 常用命令

```bash
uv sync --extra agent   # 安装依赖
uv run bash crawl_all.sh  # 爬取论文
cd agent && uv run python app.py  # 启动平台
```

## 开发规范

- 新智能体: 继承 `BaseAgent`，放 `agents/` 下，自动注册
- 配置: `config.json` 管理 LLM 参数，`/api/config` 热更新
- 会话: JSON 文件持久化在 `agent/data/`
- 敏感信息: API Key 存 `config.json`，已 gitignore
