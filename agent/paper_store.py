"""
论文数据加载与索引模块
解析四大顶会的 abstracts.md 文件，构建可检索的论文索引
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


@dataclass
class Paper:
    """单篇论文"""
    conference: str  # NDSS, CCS, S&P, USENIX
    year: int
    title: str
    abstract: str
    pdf_url: str = ""

    def to_dict(self) -> dict:
        return {
            "conference": self.conference,
            "year": self.year,
            "title": self.title,
            "abstract": self.abstract,
            "pdf_url": self.pdf_url,
        }


class PaperStore:
    """论文存储与检索"""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.papers: List[Paper] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._tfidf_matrix = None

    def load(self) -> int:
        """加载所有论文数据，返回论文总数"""
        self.papers = []

        # 优先加载统一 JSON（含完整摘要和 PDF 链接）
        json_path = self.data_dir / "security-top4-papers.json"
        if json_path.exists():
            self._load_from_json(json_path)
        else:
            # 降级：解析旧的 abstracts.md 文件
            self._load_conference("NDSS", "NDSS")
            self._load_conference("USENIX", "USENIX")
            self._load_conference("S&P", "S&P")
            self._load_conference("CCS", "CCS")

        self._build_index()
        return len(self.papers)

    def _load_from_json(self, json_path: Path) -> None:
        """从 security-top4-papers.json 加载论文数据"""
        import json
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [警告] 无法读取 {json_path}: {e}")
            return

        count = 0
        for item in data.get("papers", []):
            self.papers.append(Paper(
                conference=item.get("venue", ""),
                year=item.get("year", 0),
                title=item.get("title", ""),
                abstract=item.get("abstract", ""),
                pdf_url=item.get("pdf_url", ""),
            ))
            count += 1

        meta = data.get("meta", {})
        print(f"  从统一 JSON 加载 {count} 篇论文 (版本 {meta.get('version', '?')}, "
              f"生成日期 {meta.get('generated', '?')})")

    def _load_conference(self, conf_name: str, dir_name: str) -> None:
        """加载单个会议的论文"""
        conf_dir = self.data_dir / dir_name
        if not conf_dir.exists():
            return

        for year_dir in sorted(conf_dir.iterdir()):
            if not year_dir.is_dir():
                continue
            try:
                year = int(year_dir.name)
            except ValueError:
                continue

            # 优先加载 abstracts 文件（含摘要）
            abstract_files = list(year_dir.glob("*abstracts*.md"))
            if abstract_files:
                for f in abstract_files:
                    self._parse_abstracts_file(f, conf_name, year)
            else:
                # 降级加载 papers 文件（仅标题+作者，无摘要）
                paper_files = list(year_dir.glob("*papers*.md"))
                for f in paper_files:
                    self._parse_papers_file(f, conf_name, year)

    def _parse_abstracts_file(self, filepath: Path, conference: str, year: int) -> None:
        """解析 abstracts.md 文件"""
        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  [警告] 无法读取 {filepath}: {e}")
            return

        # 按 ## 分割，每段是一个论文
        sections = re.split(r'\n## ', text)
        count = 0
        for section in sections[1:]:  # 跳过第一个（标题部分）
            lines = section.strip().split('\n', 1)
            if len(lines) < 2:
                continue
            title = lines[0].strip()
            abstract = lines[1].strip()
            if title and abstract:
                self.papers.append(Paper(
                    conference=conference,
                    year=year,
                    title=title,
                    abstract=abstract,
                ))
                count += 1

        print(f"  {conference} {year}: {count} 篇论文 (含摘要)")

    def _parse_papers_file(self, filepath: Path, conference: str, year: int) -> None:
        """解析 papers.md 文件（仅标题+作者，无摘要）"""
        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  [警告] 无法读取 {filepath}: {e}")
            return

        # 匹配 "序号. 标题" 格式
        pattern = re.compile(r'^\d+\.\s+(.+)$', re.MULTILINE)
        count = 0
        for match in pattern.finditer(text):
            title = match.group(1).strip()
            if title and not title.startswith("共") and not title.startswith("#"):
                self.papers.append(Paper(
                    conference=conference,
                    year=year,
                    title=title,
                    abstract="",  # 无摘要
                ))
                count += 1

        print(f"  {conference} {year}: {count} 篇论文 (仅标题)")

    def _build_index(self) -> None:
        """构建 TF-IDF 索引"""
        if not self.papers:
            return

        # 将 title + abstract 拼接作为文档
        documents = [f"{p.title} {p.abstract}" for p in self.papers]

        self._vectorizer = TfidfVectorizer(
            max_features=50000,
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(documents)
        print(f"  TF-IDF 索引构建完成: {self._tfidf_matrix.shape}")

    def search(self, query: str, top_k: int = 30) -> List[Tuple[Paper, float]]:
        """TF-IDF 初筛，返回 top-K 相关论文及相似度分数"""
        if self._vectorizer is None or self._tfidf_matrix is None:
            return []

        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._tfidf_matrix).flatten()

        # 取 top-K
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self.papers[idx], float(scores[idx])))

        return results

    def get_stats(self) -> Dict:
        """获取论文库统计信息"""
        stats = {
            "total": len(self.papers),
            "by_conference": {},
            "by_year": {},
        }
        for p in self.papers:
            stats["by_conference"][p.conference] = stats["by_conference"].get(p.conference, 0) + 1
            stats["by_year"][p.year] = stats["by_year"].get(p.year, 0) + 1
        return stats
