# 4TH-CyberSecurityConference

## 项目概述

网络安全四大顶会（NDSS、CCS、S&P、USENIX）论文爬虫 + 学术智能体平台。

## 技术栈

- Python 3.x, Flask, scikit-learn, PyMuPDF
- 前端: 原生 HTML/CSS/JS
- LLM: OpenAI 兼容接口

## 目录结构

```
├── crawlers/           # 四个会议的爬虫脚本
├── agent/              # 智能体平台
│   ├── agents/         # 可插拔智能体模块
│   │   ├── base.py     # BaseAgent 基类
│   │   ├── literature.py
│   │   └── debate.py
│   ├── app.py          # Flask 入口
│   ├── llm_client.py   # LLM API
│   ├── paper_store.py  # TF-IDF 论文检索
│   ├── pdf_utils.py    # PDF 解析
│   └── config.json     # LLM 配置
├── NDSS/ USENIX/ S&P/ CCS/  # 论文数据
└── crawl_all.sh
```

## 常用命令

```bash
bash crawl_all.sh       # 爬取论文
cd agent && python app.py  # 启动平台
```

## 开发规范

- 新智能体: 继承 `BaseAgent`，放 `agents/` 下，自动注册
- 配置: `config.json` 管理 LLM 参数，`/api/config` 热更新
- 会话: JSON 文件持久化在 `agent/data/`
- 敏感信息: API Key 存 `config.json`，已 gitignore
