"""
PDF 解析工具
使用 PyMuPDF 提取文本和图片
"""

import base64

import fitz  # PyMuPDF


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

    return {
        "pages": len(pages_text),
        "text": full_text,
        "text_length": len(full_text),
        "images": images_b64,
    }
