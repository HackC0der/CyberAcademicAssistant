#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CCS论文爬虫 - 获取ACM CCS历年论文信息
支持2019-2025年，网站结构随年份变化较大
"""

import os
import re
import time
import random
import json
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from xml.etree import ElementTree as ET


# 随机User-Agent列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
]

# CCS网站基础URL
CCS_BASE_URL = "https://www.sigsac.org/ccs"


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

            # 确保正确处理编码
            response.encoding = response.apparent_encoding or 'utf-8'

            return BeautifulSoup(response.text, "html.parser")

        except requests.RequestException as e:
            print(f"  [警告] 请求失败 (尝试 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(random.uniform(2.0, 5.0))

    return None


def fetch_json(url: str, retries: int = 3) -> Optional[Dict]:
    """
    获取JSON数据

    Args:
        url: 目标URL
        retries: 重试次数

    Returns:
        解析后的JSON字典或None（失败时）
    """
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(1.0, 3.0))

            response = requests.get(
                url,
                headers=get_random_headers(),
                timeout=30
            )
            response.raise_for_status()

            return response.json()

        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"  [警告] JSON请求失败 (尝试 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(random.uniform(2.0, 5.0))

    return None


def fetch_text(url: str, retries: int = 3) -> Optional[str]:
    """
    获取原始文本内容

    Args:
        url: 目标URL
        retries: 重试次数

    Returns:
        文本内容或None（失败时）
    """
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(1.0, 3.0))

            response = requests.get(
                url,
                headers=get_random_headers(),
                timeout=30
            )
            response.raise_for_status()

            return response.text

        except requests.RequestException as e:
            print(f"  [警告] 请求失败 (尝试 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(random.uniform(2.0, 5.0))

    return None


def get_paper_list_2025(year: int) -> List[Dict[str, str]]:
    """
    获取2025年CCS论文列表（JSON格式）

    Args:
        year: 年份

    Returns:
        论文列表
    """
    json_url = f"{CCS_BASE_URL}/CCS{year}/assets/accepted-papers.json"
    print(f"获取 {year} 年论文列表 (JSON): {json_url}")

    data = fetch_json(json_url)
    if not data:
        print(f"  [错误] 无法获取 {year} 年论文JSON数据")
        return []

    papers = []

    # 处理First Cycle
    first_cycle = data.get("firstCycle", [])
    for paper in first_cycle:
        title = paper.get("title", "").strip()
        # 移除标题中的编号前缀，如 "(#18) "
        title = re.sub(r'^\(#\d+\)\s*', '', title)
        authors = paper.get("full", "")
        url = paper.get("url", "")
        papers.append({
            "title": title,
            "authors": authors,
            "url": url,
            "cycle": "First Cycle"
        })

    # 处理Second Cycle
    second_cycle = data.get("secondCycle", [])
    for paper in second_cycle:
        title = paper.get("title", "").strip()
        title = re.sub(r'^\(#\d+\)\s*', '', title)
        authors = paper.get("full", "")
        url = paper.get("url", "")
        papers.append({
            "title": title,
            "authors": authors,
            "url": url,
            "cycle": "Second Cycle"
        })

    print(f"  找到 {len(papers)} 篇论文 (First Cycle: {len(first_cycle)}, Second Cycle: {len(second_cycle)})")
    return papers


def get_paper_list_2024(year: int) -> List[Dict[str, str]]:
    """
    获取2024/2022年CCS论文列表（HTML表格格式）

    Args:
        year: 年份

    Returns:
        论文列表
    """
    list_url = f"{CCS_BASE_URL}/CCS{year}/program/accepted-papers.html"
    print(f"获取 {year} 年论文列表 (HTML表格): {list_url}")

    soup = fetch_page(list_url)
    if not soup:
        print(f"  [错误] 无法获取 {year} 年论文列表页")
        return []

    papers = []

    # 查找表格中的行
    table = soup.find("table")
    if table:
        rows = table.find_all("tr")
        for row in rows[1:]:  # 跳过表头
            cells = row.find_all("td")
            if len(cells) >= 2:
                title = cells[0].get_text(strip=True)
                # 将<br/>替换为分号，再提取文本
                authors_cell = cells[1]
                for br in authors_cell.find_all("br"):
                    br.replace_with("; ")
                authors = authors_cell.get_text(strip=True)
                if title:
                    papers.append({
                        "title": title,
                        "authors": authors,
                        "url": ""
                    })

    print(f"  找到 {len(papers)} 篇论文")
    return papers


def get_paper_list_2023(year: int) -> List[Dict[str, str]]:
    """
    获取2023年CCS论文列表（XML格式）

    Args:
        year: 年份

    Returns:
        论文列表
    """
    xml_url = f"{CCS_BASE_URL}/CCS{year}/assets/data/accepted_papers.xml"
    print(f"获取 {year} 年论文列表 (XML): {xml_url}")

    xml_text = fetch_text(xml_url)
    if not xml_text:
        print(f"  [错误] 无法获取 {year} 年论文XML数据")
        return []

    papers = []

    try:
        root = ET.fromstring(xml_text)
        for paper_elem in root.findall("paper"):
            title = paper_elem.findtext("title", "").strip()
            if title and title != "Not Available":
                papers.append({
                    "title": title,
                    "authors": "",  # XML中作者是ID，需要额外解析
                    "url": ""
                })
    except ET.ParseError as e:
        print(f"  [错误] XML解析失败: {e}")

    print(f"  找到 {len(papers)} 篇论文")
    return papers


def get_paper_list_2021(year: int) -> List[Dict[str, str]]:
    """
    获取2021/2020年CCS论文列表（HTML div格式）

    Args:
        year: 年份

    Returns:
        论文列表
    """
    list_url = f"{CCS_BASE_URL}/CCS{year}/accepted-papers.html"
    print(f"获取 {year} 年论文列表 (HTML div): {list_url}")

    soup = fetch_page(list_url)
    if not soup:
        print(f"  [错误] 无法获取 {year} 年论文列表页")
        return []

    papers = []

    # 查找所有 papers-item div
    paper_items = soup.find_all("div", class_="papers-item")
    for item in paper_items:
        title_elem = item.find("b")
        if title_elem:
            title = title_elem.get_text(strip=True)
            # 作者在相邻的div中，将<br/>替换为分号
            author_elem = item.find("p")
            if author_elem:
                for br in author_elem.find_all("br"):
                    br.replace_with("; ")
                authors = author_elem.get_text(strip=True)
            else:
                authors = ""
            papers.append({
                "title": title,
                "authors": authors,
                "url": ""
            })

    print(f"  找到 {len(papers)} 篇论文")
    return papers


def get_paper_list_2019(year: int) -> List[Dict[str, str]]:
    """
    获取2019年CCS论文列表（WordPress格式）

    Args:
        year: 年份

    Returns:
        论文列表
    """
    list_url = f"{CCS_BASE_URL}/CCS{year}/index.php/program/accepted-papers/"
    print(f"获取 {year} 年论文列表 (WordPress): {list_url}")

    soup = fetch_page(list_url)
    if not soup:
        print(f"  [错误] 无法获取 {year} 年论文列表页")
        return []

    papers = []

    # 查找表格
    table = soup.find("table")
    if table:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                title_elem = cells[0].find("strong") or cells[0]
                title = title_elem.get_text(strip=True)
                authors = cells[1].get_text(strip=True)
                if title:
                    papers.append({
                        "title": title,
                        "authors": authors,
                        "url": ""
                    })

    print(f"  找到 {len(papers)} 篇论文")
    return papers


def get_paper_list(year: int) -> List[Dict[str, str]]:
    """
    根据年份选择合适的解析方法获取论文列表

    Args:
        year: 年份

    Returns:
        论文列表
    """
    if year == 2025:
        return get_paper_list_2025(year)
    elif year in (2024, 2022):
        return get_paper_list_2024(year)
    elif year == 2023:
        return get_paper_list_2023(year)
    elif year in (2021, 2020):
        return get_paper_list_2021(year)
    elif year == 2019:
        return get_paper_list_2019(year)
    else:
        print(f"  [警告] CCS {year} 年暂不支持自动爬取")
        return []


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

    # 1. 生成摘要文件（CCS网站通常不提供摘要，只生成标题列表）
    abstracts_file = os.path.join(year_dir, f"ccs{year}_abstracts.md")
    with open(abstracts_file, "w", encoding="utf-8") as f:
        f.write(f"# CCS {year} 论文列表\n\n")
        for paper in papers:
            f.write(f"## {paper['title']}\n\n")
            if paper.get("authors"):
                f.write(f"**作者:** {paper['authors']}\n\n")
            if paper.get("cycle"):
                f.write(f"**审稿周期:** {paper['cycle']}\n\n")

    # 2. 生成PDF链接文件（如果有URL）
    papers_file = os.path.join(year_dir, f"ccs{year}_papers.md")
    with open(papers_file, "w", encoding="utf-8") as f:
        f.write(f"# CCS {year} 论文链接\n\n")
        for i, paper in enumerate(papers, 1):
            if paper.get("url"):
                f.write(f"{i}. {paper['title']}- {paper['url']}\n")
            else:
                f.write(f"{i}. {paper['title']}\n")

    print(f"  已生成文件:")
    print(f"    - {abstracts_file}")
    print(f"    - {papers_file}")


def crawl_ccs_year(year: int, output_dir: str = "CCS"):
    """
    爬取指定年份的CCS论文信息

    Args:
        year: 年份
        output_dir: 输出目录
    """
    print(f"\n{'='*60}")
    print(f"开始爬取 CCS {year} 年论文")
    print(f"{'='*60}")

    # 1. 获取论文列表
    papers = get_paper_list(year)
    if not papers:
        print(f"  [跳过] 未找到 {year} 年论文")
        return

    # 2. 生成Markdown文件
    generate_markdown_files(year, papers, output_dir)

    print(f"\nCCS {year} 年论文爬取完成！")


def main():
    """主函数"""
    # 设置输出目录
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(script_dir, "CCS")

    # 爬取年份范围：2018-2026
    start_year = 2018
    end_year = 2026

    print(f"CCS论文爬虫启动")
    print(f"爬取范围: {start_year}-{end_year}")
    print(f"输出目录: {output_dir}")

    for year in range(start_year, end_year + 1):
        try:
            crawl_ccs_year(year, output_dir)
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
