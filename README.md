# 🎓 4TH Cyber Security Conference

网络安全四大顶会（NDSS、USENIX Security、IEEE S&P、CCS）论文爬虫与学术智能体平台。

## 功能概览

### 📚 论文爬虫

自动获取四大顶会 2018-2026 年的论文信息（标题、摘要、PDF 链接、Slides 链接）。

| 会议 | 覆盖年份 | 数据量 |
|------|---------|--------|
| NDSS | 2018-2026 | ~1100 篇 |
| USENIX Security | 2018-2026 | ~2300 篇 |
| IEEE S&P | 2023-2026 | ~960 篇 |
| CCS | 2019-2025 | ~1100 篇 |

> S&P 2018-2022、CCS 2018/2026 的官方页面已下线或未发布。

### 🤖 学术智能体平台

基于爬取的论文数据构建的 Web 智能体平台，支持多智能体切换：

| 智能体 | 功能 |
|--------|------|
| **📚 文献匹配** | 自然语言描述课题，AI 语义匹配返回最相关论文 |
| **⚔️ Idea 辩论 - 审稿人** | 扮演顶级会议审稿人，严厉质疑研究假设与贡献 |
| **🎓 Idea 辩论 - 导师** | 扮演资深教授，引导凝练科学问题与创新点 |
| **📄 PDF 解读** | 上传 PDF 文档，引用后与 AI 对话分析内容 |

## 快速开始

### 1. 环境准备

```bash
git clone https://github.com/your-username/4TH-CyberSecurityConference.git
cd 4TH-CyberSecurityConference

# 安装爬虫依赖
pip install requests beautifulsoup4 lxml

# 安装智能体依赖
cd agent
pip install -r requirements.txt
```

### 2. 配置 LLM

启动后在左侧栏「⚙️ 设置」中填写：

| 参数 | 说明 |
|------|------|
| API Base URL | LLM 接口地址（如 `https://api.openai.com/v1`） |
| API Key | 你的 API 密钥 |
| Model | 模型名称（如 `gpt-4o-mini`） |
| Temperature | 生成温度（0-2） |
| Max Tokens | 最大输出长度（0=不限制） |

配置保存在 `agent/config.json`，支持任何 OpenAI 兼容接口。

### 3. 爬取论文数据（可选）

```bash
bash crawl_all.sh           # 一键爬取所有会议
bash crawl_all.sh ndss ccs  # 仅爬取指定会议
```

### 4. 启动智能体平台

```bash
cd agent
python app.py
```

浏览器访问 http://localhost:5000

## 项目结构

```
4TH-CyberSecurityConference/
├── crawlers/                   # 论文爬虫脚本
│   ├── ndss_crawler.py
│   ├── usenix_crawler.py
│   ├── sp_crawler.py
│   └── ccs_crawler.py
├── agent/                      # 学术智能体平台
│   ├── app.py                  # Flask 入口
│   ├── agents/                 # 智能体模块（可插拔）
│   │   ├── __init__.py         # 自动发现与注册
│   │   ├── base.py             # Agent 基类
│   │   ├── literature.py       # 文献匹配智能体
│   │   └── debate.py           # Idea 辩论智能体
│   ├── llm_client.py           # LLM API 封装
│   ├── paper_store.py          # 论文索引与检索
│   ├── pdf_utils.py            # PDF 解析工具
│   ├── config.json             # LLM 配置（git 忽略）
│   ├── requirements.txt
│   ├── static/
│   │   ├── style.css
│   │   └── app.js
│   └── templates/
│       └── index.html
├── crawl_all.sh
├── NDSS/                       # 论文数据（git 忽略）
├── USENIX/
├── S&P/
└── CCS/
```

## 使用指南

### 文献匹配

1. 选择 📚 文献匹配 模式
2. 用自然语言描述研究课题
3. AI 返回最相关的论文列表及关联分析

### Idea 辩论

1. 选择 ⚔️ Idea 辩论 模式
2. 切换审稿人 🔍 或导师 🎓 人格（共享上下文，随时切换）
3. 描述研究想法，获得批判性质疑或建设性引导

### PDF 解读

1. 点击输入框左侧 📎 按钮上传 PDF（可上传多个）
2. 已上传的 PDF 显示为引用标签，高亮 = 引用，点击切换
3. 输入问题，被引用的 PDF 内容将作为上下文发送给 AI
4. 支持同时引用多个 PDF 进行对比分析

### 模型设置

点击左侧栏「⚙️ 设置」标签页调节参数，点击「💾 保存配置」生效。

## 扩展智能体

在 `agent/agents/` 下创建新文件即可添加智能体：

```python
from .base import BaseAgent

class MyAgent(BaseAgent):
    name = "my_agent"
    route = "/api/my-agent"

    def __init__(self, store=None):
        pass

    def build_messages(self, data: dict) -> list:
        return [
            {"role": "system", "content": "你是..."},
            {"role": "user", "content": data.get("message", "")},
        ]
```

重启服务自动注册。前端需在 `app.js` 的 `switchMode` 中添加新模式。

## 许可证

MIT License
