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

> S&P 2018-2022、CCS 2018/2026 的官方页面已下线或未发布，无法获取。

### 🤖 学术智能体平台

基于爬取的论文数据构建的 Web 智能体平台，包含三个核心功能：

| 智能体 | 功能 |
|--------|------|
| **📚 文献匹配** | 自然语言描述课题，AI 语义匹配返回最相关论文 |
| **⚔️ Idea 辩论 - 审稿人** | 扮演顶级会议审稿人，严厉质疑研究假设与贡献 |
| **🎓 Idea 辩论 - 导师** | 扮演资深教授，引导凝练科学问题与创新点 |
| **📄 PDF 解读** | 上传 PDF 文档，AI 解析内容并进行对话 |

## 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/your-username/4TH-CyberSecurityConference.git
cd 4TH-CyberSecurityConference

# 安装爬虫依赖
pip install requests beautifulsoup4 lxml

# 安装智能体依赖
cd agent
pip install -r requirements.txt
```

`agent/requirements.txt` 包含：
```
flask>=3.0
requests>=2.31
scikit-learn>=1.3
numpy>=1.24
python-dotenv>=1.0
pymupdf>=1.24
```

### 2. 配置 LLM API

```bash
cd agent
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 配置：

```env
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=your-api-key-here
LLM_MODEL=gpt-4o-mini
```

支持任何 OpenAI 兼容接口（OpenAI、DeepSeek、本地 Ollama 等）。

### 3. 爬取论文数据（可选）

```bash
# 一键爬取所有会议
bash crawl_all.sh

# 仅爬取指定会议
bash crawl_all.sh ndss usenix
```

爬取的数据存储在 `NDSS/`、`USENIX/`、`S&P/`、`CCS/` 目录下，每年份生成三个文件：

| 文件 | 内容 |
|------|------|
| `{conf}{year}_abstracts.md` | 论文标题 + 摘要 |
| `{conf}{year}_papers.md` | 论文 PDF 链接列表 |
| `{conf}{year}_slides.md` | Slides 链接列表 |

> 爬虫内置反爬措施（随机 User-Agent、请求延迟），请合理使用。

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
│   ├── app.py                  # Flask 后端
│   ├── llm_client.py           # LLM API 封装
│   ├── paper_store.py          # 论文索引与检索
│   ├── requirements.txt
│   ├── .env.example            # API 配置模板
│   ├── static/                 # 前端资源
│   │   ├── style.css
│   │   └── app.js
│   └── templates/
│       └── index.html
├── crawl_all.sh                # 一键爬取脚本
├── NDSS/                       # 论文数据（git 忽略）
├── USENIX/
├── S&P/
└── CCS/
```

## 技术架构

### 论文爬虫

- **Python 3.x** + requests + BeautifulSoup4
- 针对每个会议的不同网站结构定制解析逻辑
- 反爬：随机 User-Agent、1-3s 请求延迟、3-6s 年份间延迟

### 智能体平台

```
用户输入 → LLM 提取关键词 → TF-IDF 初筛(top-30) → LLM 语义排序 → 流式输出
```

- **后端**：Flask + SSE 流式响应
- **前端**：原生 HTML/CSS/JS，ChatGPT 风格对话界面
- **检索**：scikit-learn TF-IDF 索引（5500+ 论文）
- **LLM**：OpenAI 兼容接口，支持温度/长度/思考模式调节
- **会话**：服务端 JSON 持久化，支持多会话管理

## 使用指南

### 文献匹配

1. 选择 📚 文献匹配 模式
2. 用自然语言描述研究课题，例如：
   - "我对联邦学习中的隐私攻击感兴趣"
   - "我想找关于大语言模型安全性的论文"
3. AI 返回最相关的论文列表及关联分析
4. 可上传 PDF 文档，结合论文库进行分析

### Idea 辩论

1. 选择 ⚔️ Idea 辩论 模式
2. 切换审稿人 🔍 或导师 🎓 人格（共享上下文，随时切换）
3. 描述研究想法，例如：
   - "我想研究漏洞利用代码移植"
   - "我的课题是基于 LLM 的自动化漏洞挖掘"
4. 审稿人模式：给出 3-5 个严厉质疑，找出逻辑裂缝
5. 导师模式：引导凝练科学问题，给出创新点建议

### PDF 解读

1. 点击输入框左侧 📎 按钮上传 PDF
2. 输入问题，AI 解析 PDF 内容并回答
3. 支持文本提取，适用于论文、报告等文档

### 模型设置

点击侧边栏 ⚙️ 按钮调节：

| 参数 | 说明 |
|------|------|
| Temperature | 0-2，低值更精确，高值更发散 |
| Max Tokens | 最大输出长度，0 = 不限制 |
| Think Mode | 扩展思考模式（需模型支持） |

## 许可证

MIT License
