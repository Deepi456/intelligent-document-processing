from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.ocr.ocr_engine import OcrEngine


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str
    source: str
    bounding_boxes: list[dict] | None = None
    image_width: int | None = None
    image_height: int | None = None


def extract_pdf(file_path: str | Path, ocr_engine: OcrEngine | None = None) -> list[PageText]:
    document = pymupdf.open(str(file_path))
    pages: list[PageText] = []
    try:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            words = page.get_text("words")
            if text and len(words) > 5:
                boxes = [
                    {
                        "text": word[4],
                        "left": float(word[0]),
                        "top": float(word[1]),
                        "width": float(word[2] - word[0]),
                        "height": float(word[3] - word[1]),
                        "confidence": 1.0
                    }
                    for word in page.get_text("words") if word[4].strip()
                ]
                pages.append(PageText(page_number, text, "text_layer", boxes, int(page.rect.width), int(page.rect.height)))
                continue
            if ocr_engine is None:
                ocr_engine = OcrEngine()
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            result = ocr_engine.extract_pixmap(pixmap)
            pages.append(PageText(page_number, result.text, "ocr", result.bounding_boxes, pixmap.width, pixmap.height))
    finally:
        document.close()
    return pages