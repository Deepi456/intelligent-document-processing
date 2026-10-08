from pathlib import Path
from PIL import Image

from app.extraction.pdf_extractor import PageText
from app.ocr.ocr_engine import OcrEngine


def extract_image(file_path: str | Path, ocr_engine: OcrEngine | None = None) -> list[PageText]:
    engine = ocr_engine or OcrEngine()
    comparison = engine.compare_file(file_path)
    fused = comparison.fused
    with Image.open(file_path) as image:
        width, height = image.size
    return [PageText(1, fused.text, "ocr", fused.bounding_boxes, width, height)]