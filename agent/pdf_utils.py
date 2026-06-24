"""
PDF 解析工具
使用 PyMuPDF 提取文本，带磁盘缓存（MD5 去重）
"""

import json
import base64
import hashlib
from pathlib import Path

import fitz  # PyMuPDF

CACHE_DIR = Path(__file__).resolve().parent / "data" / "pdf_cache"

# 内存缓存（热数据）
_mem_cache: dict[str, dict] = {}
MEM_CACHE_MAX = 20


def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(cache_key: str) -> Path:
    return CACHE_DIR / f"{cache_key}.json"


def _load_from_disk(cache_key: str) -> dict | None:
    """从磁盘加载缓存"""
    path = _cache_path(cache_key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_to_disk(cache_key: str, result: dict):
    """写入磁盘缓存"""
    _ensure_cache_dir()
    _cache_path(cache_key).write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )


def parse_pdf(pdf_bytes: bytes, extract_images: bool = False) -> dict:
    """
    解析 PDF 文件，提取文本

    缓存策略：内存 → 磁盘 → 解析

    返回:
        {
            "pages": int,
            "text": str,
            "text_length": int,
            "images": list,
            "cache_key": str  # MD5 哈希
        }
    """
    cache_key = hashlib.md5(pdf_bytes).hexdigest()

    # 1. 内存缓存命中
    if cache_key in _mem_cache:
        return _mem_cache[cache_key]

    # 2. 磁盘缓存命中
    disk_result = _load_from_disk(cache_key)
    if disk_result is not None:
        # 加入内存缓存
        _mem_cache[cache_key] = disk_result
        return disk_result

    # 3. 解析 PDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    pages_text = []
    images_b64 = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        text = page.get_text("text").strip()
        if text:
            pages_text.append(f"--- 第 {page_num + 1} 页 ---\n{text}")

        if extract_images:
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image and base_image.get("image"):
                        img_bytes = base_image["image"]
                        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                        ext = base_image.get("ext", "png")
                        images_b64.append({
                            "page": page_num + 1,
                            "index": img_index,
                            "ext": ext,
                            "data": img_b64,
                        })
                except Exception:
                    continue

    doc.close()

    full_text = "\n\n".join(pages_text)

    result = {
        "pages": len(pages_text),
        "text": full_text,
        "text_length": len(full_text),
        "images": images_b64,
        "cache_key": cache_key,
    }

    # 写入磁盘 + 内存
    _save_to_disk(cache_key, result)

    if len(_mem_cache) >= MEM_CACHE_MAX:
        oldest = next(iter(_mem_cache))
        del _mem_cache[oldest]
    _mem_cache[cache_key] = result

    return result
