#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NDSS论文爬虫 - 获取NDSS Symposium历年论文信息
"""

import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional


# 随机User-Agent列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
]


def get_random_headers() -> Dict[str, str]:
    """生成随机请求头"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def fetch_page(url: str, retries: int = 3) -> Optional[BeautifulSoup]:
    """
    获取页面内容并解析为BeautifulSoup对象

    Args:
        url: 目标URL
        retries: 重试次数

    Returns:
        BeautifulSoup对象或None（失败时）
    """
    for attempt in range(retries):
        try:
            # 随机延迟，避免请求过快
            time.sleep(random.uniform(1.0, 3.0))

            response = requests.get(
                url,
                headers=get_random_headers(),
                timeout=30
            )
            response.raise_for_status()

            return BeautifulSoup(response.text, "html.parser")

        except requests.RequestException as e:
            print(f"  [警告] 请求失败 (尝试 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(random.uniform(2.0, 5.0))

    return None


def get_paper_list(year: int) -> List[Dict[str, str]]:
    """
    获取指定年份的论文列表

    Args:
        year: 年份

    Returns:
        论文列表，每个元素包含title和url
    """
    list_url = f"https://www.ndss-symposium.org/ndss{year}/accepted-papers/"
    print(f"获取 {year} 年论文列表: {list_url}")

    soup = fetch_page(list_url)
    if not soup:
        print(f"  [错误] 无法获取 {year} 年论文列表页")
        return []

    papers = []
    # 查找所有论文链接
    paper_items = soup.select("div.pt-cv-content-item h2.pt-cv-title a")

    for item in paper_items:
        title = item.get_text(strip=True)
        url = item.get("href", "")
        if title and url:
            papers.append({"title": title, "url": url})

    print(f"  找到 {len(papers)} 篇论文")
    return papers


def get_paper_detail(url: str) -> Dict[str, str]:
    """
    获取单篇论文的详细信息

    Args:
        url: 论文详情页URL

    Returns:
        包含title, abstract, pdf_url, slides_url的字典
    """
    detail = {
        "title": "",
        "abstract": "",
        "pdf_url": "",
        "slides_url": "",
    }

    soup = fetch_page(url)
    if not soup:
        return detail

    # 提取标题
    title_elem = soup.select_one("h1.entry-title")
    if title_elem:
        detail["title"] = title_elem.get_text(strip=True)

    # 提取摘要（paper-data区域的第二个p标签，第一个是作者）
    paper_data = soup.select_one("div.paper-data")
    if paper_data:
        paragraphs = paper_data.find_all("p", recursive=False)
        # 跳过作者段落（包含strong标签），找摘要
        for p in paragraphs:
            text = p.get_text(strip=True)
            # 摘要通常是较长的段落，且不包含strong标签
            if len(text) > 100 and not p.find("strong"):
                detail["abstract"] = text
                break

        # 如果上面方法没找到，尝试获取所有非作者段落
        if not detail["abstract"]:
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 50:
                    detail["abstract"] = text
                    break

    # 提取PDF链接
    pdf_elem = soup.select_one("a.pdf-button")
    if pdf_elem:
        detail["pdf_url"] = pdf_elem.get("href", "")

    # 提取Slides链接
    slides_elem = soup.select_one("a.button-slides")
    if slides_elem:
        detail["slides_url"] = slides_elem.get("href", "")

    return detail


def generate_markdown_files(year: int, papers_detail: List[Dict[str, str]], output_dir: str):
    """
    生成三个Markdown文件

    Args:
        year: 年份
        papers_detail: 论文详情列表
        output_dir: 输出目录
    """
    # 创建输出目录
    year_dir = os.path.join(output_dir, str(year))
    os.makedirs(year_dir, exist_ok=True)

    # 1. 生成摘要文件
    abstracts_file = os.path.join(year_dir, f"ndss{year}_abstracts.md")
    with open(abstracts_file, "w", encoding="utf-8") as f:
        f.write(f"# NDSS {year} 论文摘要\n\n")
        for paper in papers_detail:
            f.write(f"## {paper['title']}\n\n")
            if paper["abstract"]:
                f.write(f"{paper['abstract']}\n\n")
            else:
                f.write("暂无摘要\n\n")

    # 2. 生成PDF链接文件
    papers_file = os.path.join(year_dir, f"ndss{year}_papers.md")
    with open(papers_file, "w", encoding="utf-8") as f:
        f.write(f"# NDSS {year} 论文PDF链接\n\n")
        for i, paper in enumerate(papers_detail, 1):
            if paper["pdf_url"]:
                f.write(f"{i}. {paper['title']}- {paper['pdf_url']}\n")
            else:
                f.write(f"{i}. {paper['title']}- 暂无链接\n")

    # 3. 生成Slides链接文件
    slides_file = os.path.join(year_dir, f"ndss{year}_slides.md")
    with open(slides_file, "w", encoding="utf-8") as f:
        f.write(f"# NDSS {year} Slides链接\n\n")
        for i, paper in enumerate(papers_detail, 1):
            if paper["slides_url"]:
                f.write(f"{i}. {paper['title']}- {paper['slides_url']}\n")
            else:
                f.write(f"{i}. {paper['title']}- 暂无链接\n")

    print(f"  已生成文件:")
    print(f"    - {abstracts_file}")
    print(f"    - {papers_file}")
    print(f"    - {slides_file}")


def crawl_ndss_year(year: int, output_dir: str = "NDSS"):
    """
    爬取指定年份的NDSS论文信息

    Args:
        year: 年份
        output_dir: 输出目录
    """
    print(f"\n{'='*60}")
    print(f"开始爬取 NDSS {year} 年论文")
    print(f"{'='*60}")

    # 1. 获取论文列表
    papers = get_paper_list(year)
    if not papers:
        print(f"  [跳过] 未找到 {year} 年论文")
        return

    # 2. 获取每篇论文详情
    papers_detail = []
    for i, paper in enumerate(papers, 1):
        print(f"  处理论文 {i}/{len(papers)}: {paper['title'][:50]}...")
        detail = get_paper_detail(paper["url"])
        detail["title"] = paper["title"]  # 使用列表页的标题
        papers_detail.append(detail)

    # 3. 生成Markdown文件
    generate_markdown_files(year, papers_detail, output_dir)

    print(f"\nNDSS {year} 年论文爬取完成！")


def main():
    """主函数"""
    # 设置输出目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "NDSS")

    # 爬取年份范围：2010-2025
    start_year = 2010
    end_year = 2025

    print(f"NDSS论文爬虫启动")
    print(f"爬取范围: {start_year}-{end_year}")
    print(f"输出目录: {output_dir}")

    for year in range(start_year, end_year + 1):
        try:
            crawl_ndss_year(year, output_dir)
        except Exception as e:
            print(f"  [错误] 爬取 {year} 年论文时出错: {e}")

        # 年份间较长延迟
        if year < end_year:
            delay = random.uniform(3.0, 6.0)
            print(f"  等待 {delay:.1f} 秒后继续...")
            time.sleep(delay)

    print(f"\n{'='*60}")
    print("所有年份爬取完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
