"""
PDF 解析工具
使用 PyMuPDF 提取文本，带内存缓存
"""

import base64
import hashlib

import fitz  # PyMuPDF

# 缓存：key=文件MD5, value=解析结果
_cache: dict[str, dict] = {}
CACHE_MAX = 50  # 最多缓存 50 个 PDF


def parse_pdf(pdf_bytes: bytes, extract_images: bool = False) -> dict:
    """
    解析 PDF 文件，提取文本

    参数:
        pdf_bytes: PDF 文件字节
        extract_images: 是否提取图片（默认 False，避免响应过大）

    返回:
        {
            "pages": int,
            "text": str,
            "text_length": int,
            "images": [{"page": int, "index": int, "ext": str, "data": str}, ...]
        }
    """
    # 缓存查找
    cache_key = hashlib.md5(pdf_bytes).hexdigest()
    if cache_key in _cache:
        return _cache[cache_key]

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    pages_text = []
    images_b64 = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # 提取文本
        text = page.get_text("text").strip()
        if text:
            pages_text.append(f"--- 第 {page_num + 1} 页 ---\n{text}")

        # 提取图片（仅在显式请求时）
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
    }

    # 写入缓存（超过上限时清理最早的）
    if len(_cache) >= CACHE_MAX:
        oldest = next(iter(_cache))
        del _cache[oldest]
    _cache[cache_key] = result

    return result
