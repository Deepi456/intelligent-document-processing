from app.nlp.layout_analyzer import LayoutBox, analyze_layout, group_lines, normalize_boxes, sort_reading_order


def boxes(*items):
    return [{"text": text, "confidence": 90, "left": left, "top": top, "width": width, "height": height} for text, left, top, width, height in items]


def test_normalizes_coordinates():
    result = normalize_boxes(boxes(("text", 100, 50, 200, 25)), 1000, 500)[0]
    assert result.normalized_bbox == [0.1, 0.1, 0.2, 0.05]


def test_sorts_boxes_reading_order():
    result = sort_reading_order(normalize_boxes(boxes(("b", 100, 20, 20, 10), ("a", 10, 20, 20, 10), ("c", 10, 50, 20, 10)), 200, 100))
    assert [item.text for item in result] == ["a", "b", "c"]


def test_groups_multiline_address():
    lines = group_lines(normalize_boxes(boxes(("SHOP", 10, 10, 50, 10), ("NO 1", 10, 30, 40, 10), ("JALAN BESAR", 10, 45, 70, 10)), 200, 100))
    assert [[item.text for item in line] for line in lines] == [["SHOP"], ["NO 1"], ["JALAN BESAR"]]


def test_selects_total_from_summary_region():
    result = analyze_layout(boxes(("SHOP", 10, 10, 50, 10), ("TOTAL", 10, 80, 40, 10), ("15.90", 100, 80, 40, 10)), 200, 100)
    assert any(item["entity_type"] == "TOTAL" and item["name"] == "15.90" for item in result)

def test_extracts_generic_attributes():
    result = analyze_layout(boxes(
        ("Student Name:", 10, 10, 60, 10), ("Deepika", 80, 10, 40, 10),
        ("Department", 10, 30, 50, 10), ("AI & Data Science", 100, 30, 80, 10),
        ("CGPA", 10, 50, 20, 10), ("-", 35, 50, 5, 10), ("8.6", 50, 50, 15, 10),
        ("Author:", 10, 70, 30, 10), ("Ada Lovelace", 50, 70, 60, 10),
        ("Topic:", 10, 90, 35, 10), ("Computing", 80, 90, 50, 10)
    ), 200, 100)
    
    entities = {item["entity_type"]: item["name"] for item in result}
    assert entities.get("Student Name") == "Deepika"
    assert entities.get("Department") == "AI & Data Science"
    assert entities.get("CGPA") == "8.6"
    assert entities.get("Author") == "Ada Lovelace"
    assert entities.get("Topic") == "Computing"


def test_rejects_unseparated_ocr_words_as_key_value():
    # "Name FDHPA3470H Account" must NOT be accepted as a key/value pair:
    # the key has no separator and the words are unrelated OCR fragments.
    result = analyze_layout(boxes(
        ("Name", 10, 30, 20, 10),
        ("FDHPA3470H", 40, 30, 30, 10),
        ("Account", 75, 30, 25, 10),
    ), 200, 100)
    assert [item for item in result if item.get("entity_type", "") in ("Name", "Name FDHPA3470H Account")] == []
    assert not any("FDHPA3470H" in (item.get("name") or "") and "Account" in (item.get("name") or "") for item in result)

