# 4TH-CyberSecurityConference

## 项目概述

网络安全四大顶会论文爬虫工具，用于自动获取NDSS、CCS、S&P、USENIX会议的论文信息。

## 用户背景

- 网络空间安全专业博士研究生
- 需要获取四大顶会论文用于研究

## 目录结构

```
4TH-CyberSecurityConference/
├── CLAUDE.md
├── ndss_crawler.py      # NDSS爬虫脚本
├── NDSS/                # NDSS论文数据
│   └── {year}/          # 按年份组织
├── CCS/                 # CCS论文数据
├── S&P/                 # S&P论文数据
└── USENIX/              # USENIX论文数据
```

## 输出文件格式

每年份生成三个文件：
1. `ndss{year}_abstracts.md` - 所有论文摘要（二级标题+正文）
2. `ndss{year}_papers.md` - 论文PDF链接列表
3. `ndss{year}_slides.md` - Slides链接列表

## 技术栈

- Python 3.x
- requests
- beautifulsoup4

## 开发规范

- 添加反爬措施（请求延迟、随机User-Agent）
- 错误处理和日志记录
- 代码注释使用中文
