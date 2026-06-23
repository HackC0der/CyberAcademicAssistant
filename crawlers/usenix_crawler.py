#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
USENIX Security论文爬虫 - 获取USENIX Security历年论文信息
"""

import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin


# 随机User-Agent列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
]

BASE_URL = "https://www.usenix.org"


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


def find_accepted_papers_pages(year: int) -> List[str]:
    """
    从会议主页找到所有论文列表页链接

    Args:
        year: 年份

    Returns:
        论文列表页URL列表
    """
    # 构建会议主页URL
    year_short = str(year)[-2:]  # 取年份后两位
    main_url = f"{BASE_URL}/conference/usenixsecurity{year_short}"
    print(f"访问会议主页: {main_url}")

    soup = fetch_page(main_url)
    if not soup:
        print(f"  [错误] 无法访问会议主页")
        return []

    paper_pages = []
    # 查找包含 "accepted-papers" 或 "technical-sessions" 的链接
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if "accepted-papers" in href or "technical-sessions" in href:
            full_url = urljoin(BASE_URL, href)
            if full_url not in paper_pages:
                paper_pages.append(full_url)
                print(f"  找到论文页: {full_url}")

    # 如果没有找到论文页，尝试直接访问technical-sessions
    if not paper_pages:
        technical_sessions_url = f"{main_url}/technical-sessions"
        response = requests.get(technical_sessions_url, headers=get_random_headers(), timeout=30)
        if response.status_code == 200:
            paper_pages.append(technical_sessions_url)
            print(f"  找到论文页: {technical_sessions_url}")

    return paper_pages


def extract_papers_from_list_page(url: str) -> List[Dict[str, str]]:
    """
    从论文列表页提取论文信息

    Args:
        url: 论文列表页URL

    Returns:
        论文信息列表
    """
    print(f"  解析论文列表页: {url}")
    soup = fetch_page(url)
    if not soup:
        return []

    papers = []
    # 查找所有论文article
    articles = soup.select("article.node.node-paper")

    for article in articles:
        paper = {"title": "", "url": "", "abstract": "", "pdf_url": "", "slides_url": ""}

        # 提取标题和链接
        title_link = article.select_one("h2 a")
        if title_link:
            paper["title"] = title_link.get_text(strip=True)
            href = title_link.get("href", "")
            if href:
                paper["url"] = urljoin(BASE_URL, href)

        # 提取摘要（列表页就有）
        abstract_div = article.select_one("div.field-name-field-paper-description-long")
        if not abstract_div:
            abstract_div = article.select_one("div.field-name-field-paper-description")
        if abstract_div:
            p_tag = abstract_div.find("p")
            if p_tag:
                paper["abstract"] = p_tag.get_text(strip=True)

        # 提取PDF链接（从media icons）
        pdf_spans = article.select("span.usenix-schedule-media.pdf a")
        for pdf_a in pdf_spans:
            href = pdf_a.get("href", "")
            if href and "presentation" in href:
                # 这是详情页链接，不是直接PDF
                pass

        if paper["title"]:
            papers.append(paper)

    print(f"    找到 {len(papers)} 篇论文")
    return papers


def get_paper_detail(url: str) -> Dict[str, str]:
    """
    获取单篇论文的详细信息（PDF、Slides等）

    Args:
        url: 论文详情页URL

    Returns:
        包含pdf_url, slides_url的字典
    """
    detail = {"pdf_url": "", "slides_url": ""}

    soup = fetch_page(url)
    if not soup:
        return detail

    # 方法1: 从meta标签提取PDF
    pdf_meta = soup.select_one('meta[name="citation_pdf_url"]')
    if pdf_meta:
        detail["pdf_url"] = pdf_meta.get("content", "")

    # 方法2: 从field-final-paper-pdf提取
    if not detail["pdf_url"]:
        pdf_div = soup.select_one("div.field-name-field-final-paper-pdf a")
        if pdf_div:
            href = pdf_div.get("href", "")
            if href:
                detail["pdf_url"] = urljoin(BASE_URL, href)

    # 方法3: 从field-presentation-pdf提取prepublication版本
    if not detail["pdf_url"]:
        pdf_div = soup.select_one("div.field-name-field-presentation-pdf a")
        if pdf_div:
            href = pdf_div.get("href", "")
            if href:
                detail["pdf_url"] = urljoin(BASE_URL, href)

    # Slides通常在video embed区域，这里暂时留空
    # USENIX的slides通常通过video页面访问

    return detail


def crawl_usenix_year(year: int, output_dir: str = "USENIX"):
    """
    爬取指定年份的USENIX Security论文信息

    Args:
        year: 年份
        output_dir: 输出目录
    """
    print(f"\n{'='*60}")
    print(f"开始爬取 USENIX Security {year} 年论文")
    print(f"{'='*60}")

    # 1. 找到所有论文列表页
    paper_pages = find_accepted_papers_pages(year)
    if not paper_pages:
        print(f"  [跳过] 未找到 {year} 年论文列表页")
        return

    # 2. 从所有列表页提取论文
    all_papers = []
    for page_url in paper_pages:
        papers = extract_papers_from_list_page(page_url)
        all_papers.extend(papers)

    # 去重（根据标题）
    seen_titles: Set[str] = set()
    unique_papers = []
    for paper in all_papers:
        if paper["title"] not in seen_titles:
            seen_titles.add(paper["title"])
            unique_papers.append(paper)

    print(f"\n  共找到 {len(unique_papers)} 篇唯一论文")

    if not unique_papers:
        return

    # 3. 获取每篇论文的详情（PDF链接等）
    for i, paper in enumerate(unique_papers, 1):
        if paper["url"]:
            print(f"  获取详情 {i}/{len(unique_papers)}: {paper['title'][:50]}...")
            detail = get_paper_detail(paper["url"])
            paper["pdf_url"] = detail["pdf_url"]
            paper["slides_url"] = detail["slides_url"]

    # 4. 生成Markdown文件
    generate_markdown_files(year, unique_papers, output_dir)

    print(f"\nUSENIX Security {year} 年论文爬取完成！")


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
    abstracts_file = os.path.join(year_dir, f"usenix{year}_abstracts.md")
    with open(abstracts_file, "w", encoding="utf-8") as f:
        f.write(f"# USENIX Security {year} 论文摘要\n\n")
        for paper in papers_detail:
            f.write(f"## {paper['title']}\n\n")
            if paper["abstract"]:
                f.write(f"{paper['abstract']}\n\n")
            else:
                f.write("暂无摘要\n\n")

    # 2. 生成PDF链接文件
    papers_file = os.path.join(year_dir, f"usenix{year}_papers.md")
    with open(papers_file, "w", encoding="utf-8") as f:
        f.write(f"# USENIX Security {year} 论文PDF链接\n\n")
        for i, paper in enumerate(papers_detail, 1):
            if paper["pdf_url"]:
                f.write(f"{i}. {paper['title']}- {paper['pdf_url']}\n")
            else:
                f.write(f"{i}. {paper['title']}- 暂无链接\n")

    # 3. 生成Slides链接文件
    slides_file = os.path.join(year_dir, f"usenix{year}_slides.md")
    with open(slides_file, "w", encoding="utf-8") as f:
        f.write(f"# USENIX Security {year} Slides链接\n\n")
        for i, paper in enumerate(papers_detail, 1):
            if paper["slides_url"]:
                f.write(f"{i}. {paper['title']}- {paper['slides_url']}\n")
            else:
                f.write(f"{i}. {paper['title']}- 暂无链接\n")

    print(f"\n  已生成文件:")
    print(f"    - {abstracts_file}")
    print(f"    - {papers_file}")
    print(f"    - {slides_file}")


def main():
    """主函数"""
    # 设置输出目录
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(script_dir, "USENIX")

    # 爬取年份范围：2018-2026
    start_year = 2018
    end_year = 2026

    print(f"USENIX Security论文爬虫启动")
    print(f"爬取范围: {start_year}-{end_year}")
    print(f"输出目录: {output_dir}")

    for year in range(start_year, end_year + 1):
        try:
            crawl_usenix_year(year, output_dir)
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
