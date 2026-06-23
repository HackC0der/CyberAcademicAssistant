#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IEEE S&P论文爬虫 - 获取IEEE Symposium on Security and Privacy历年论文信息
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


def find_papers_page(year: int) -> Optional[str]:
    """
    查找论文页面URL

    Args:
        year: 年份

    Returns:
        论文页面URL或None
    """
    base_url = f"https://sp{year}.ieee-security.org"

    # 尝试不同的URL格式
    possible_urls = [
        f"{base_url}/accepted-papers.html",
        f"{base_url}/program-papers.html",
    ]

    for url in possible_urls:
        print(f"  尝试: {url}")
        try:
            response = requests.head(
                url,
                headers=get_random_headers(),
                timeout=10,
                allow_redirects=True
            )
            if response.status_code == 200:
                print(f"  找到论文页: {url}")
                return url
        except requests.RequestException:
            pass

    return None


def extract_papers_from_page(url: str) -> List[Dict[str, str]]:
    """
    从论文页面提取论文信息

    Args:
        url: 论文页面URL

    Returns:
        论文信息列表
    """
    print(f"  解析论文页面: {url}")
    soup = fetch_page(url)
    if not soup:
        return []

    papers = []

    # 查找所有论文项
    paper_items = soup.select("div.list-group-item")

    for item in paper_items:
        paper = {"title": "", "authors": ""}

        # 提取标题（在b标签中）
        title_tag = item.find("b")
        if title_tag:
            # 获取标题文本，清理多余空格
            title_text = title_tag.get_text(strip=True)
            paper["title"] = " ".join(title_text.split())

        # 提取作者（在br标签后）
        br_tag = item.find("br")
        if br_tag:
            # 获取br标签后的所有文本
            authors_text = ""
            for sibling in br_tag.next_siblings:
                if isinstance(sibling, str):
                    authors_text += sibling
                elif sibling.name == "br":
                    break
                else:
                    authors_text += sibling.get_text()

            paper["authors"] = " ".join(authors_text.split())

        if paper["title"]:
            papers.append(paper)

    print(f"    找到 {len(papers)} 篇论文")
    return papers


def crawl_sp_year(year: int, output_dir: str = "S&P"):
    """
    爬取指定年份的S&P论文信息

    Args:
        year: 年份
        output_dir: 输出目录
    """
    print(f"\n{'='*60}")
    print(f"开始爬取 IEEE S&P {year} 年论文")
    print(f"{'='*60}")

    # 1. 查找论文页面
    papers_url = find_papers_page(year)
    if not papers_url:
        print(f"  [跳过] 未找到 {year} 年论文页面")
        return

    # 2. 提取论文
    papers = extract_papers_from_page(papers_url)
    if not papers:
        print(f"  [跳过] 未找到 {year} 年论文")
        return

    # 3. 生成Markdown文件
    generate_markdown_files(year, papers, output_dir)

    print(f"\nIEEE S&P {year} 年论文爬取完成！")


def generate_markdown_files(year: int, papers: List[Dict[str, str]], output_dir: str):
    """
    生成Markdown文件

    Args:
        year: 年份
        papers: 论文列表
        output_dir: 输出目录
    """
    # 创建输出目录
    year_dir = os.path.join(output_dir, str(year))
    os.makedirs(year_dir, exist_ok=True)

    # S&P网站通常不提供摘要和PDF链接，只生成论文列表文件
    papers_file = os.path.join(year_dir, f"sp{year}_papers.md")
    with open(papers_file, "w", encoding="utf-8") as f:
        f.write(f"# IEEE S&P {year} 论文列表\n\n")
        f.write(f"共 {len(papers)} 篇论文\n\n")
        for i, paper in enumerate(papers, 1):
            f.write(f"{i}. {paper['title']}\n")
            if paper["authors"]:
                f.write(f"   - 作者: {paper['authors']}\n")

    print(f"\n  已生成文件:")
    print(f"    - {papers_file}")


def main():
    """主函数"""
    # 设置输出目录
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(script_dir, "S&P")

    # 爬取年份范围：2018-2026
    start_year = 2018
    end_year = 2026

    print(f"IEEE S&P论文爬虫启动")
    print(f"爬取范围: {start_year}-{end_year}")
    print(f"输出目录: {output_dir}")

    for year in range(start_year, end_year + 1):
        try:
            crawl_sp_year(year, output_dir)
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
