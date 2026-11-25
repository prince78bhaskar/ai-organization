"""PDF, scanned PDF, image, handwritten notes, txt/md ko text mein badalna.

Text wale PDF  -> PyMuPDF se seedha text
Scanned/image  -> vision model (qwen3-vl) se OCR + samajh
"""
import os
import tempfile

from config import VISION_MODEL
from llm import chat

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
TEXT_EXT = {".txt", ".md", ".py", ".csv", ".json"}

OCR_PROMPT = (
    "Is image mein jo bhi likha hai (printed ya handwritten), use ek-ek karke "
    "bilkul waisa hi text mein likho. Kuch add mat karo. Agar diagram/table hai "
    "to uska chhota sa description do."
)


def _ocr_image(path: str) -> str:
    return chat(VISION_MODEL, "You are an accurate OCR assistant.", OCR_PROMPT, images=[path])


def read_document(path: str):
    """Returns list of (page_label, text)."""
    ext = os.path.splitext(path)[1].lower()

    if ext in TEXT_EXT:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return [("text", f.read())]

    if ext in IMAGE_EXT:
        return [("image", _ocr_image(path))]

    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise RuntimeError("PDF ke liye install karo: pip install pymupdf")
        pages = []
        doc = fitz.open(path)
        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if len(text) < 30:  # lagta hai scanned page hai -> vision model
                with tempfile.TemporaryDirectory() as tmp:
                    img_path = os.path.join(tmp, f"p{i}.png")
                    page.get_pixmap(dpi=150).save(img_path)
                    text = _ocr_image(img_path)
            pages.append((f"page {i}", text))
        return pages

    raise ValueError(f"Ye file type supported nahi hai: {ext}")
