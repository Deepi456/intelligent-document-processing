from pathlib import Path

from app.ocr.ocr_engine import OcrEngine, OcrResult, _fuse_results


def test_tesseract_ocr_returns_text_boxes_and_confidence():
    image_path = Path("data/raw/sroie/SROIE2019/train/img/X00016469612.jpg")
    result = OcrEngine().extract_file(image_path)
    assert result.text.strip()
    assert result.bounding_boxes
    assert any(box["text"] for box in result.bounding_boxes)
    assert result.confidence is not None


def test_fuses_fuller_readable_candidate_for_overlapping_region():
    fragment = OcrResult("ITHA", 91.0, [{"text": "ITHA", "confidence": 91, "left": 10, "top": 10, "width": 20, "height": 50}])
    fuller = OcrResult("ASMITHA", 0.0, [{"text": "ASMITHA", "confidence": 0, "left": 8, "top": 8, "width": 60, "height": 100}])
    result = _fuse_results([(fragment, 100.0), (fuller, 50.0)])
    assert "ASMITHA" in result.text