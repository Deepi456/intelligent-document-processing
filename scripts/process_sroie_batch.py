import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dataset.sroie_loader import SROIEExample, SROIELoader
from app.extraction.image_extractor import extract_image
from app.nlp.entity_extractor import extract_entities


FIELDS = {
    "company": "Organization",
    "date": "Date",
    "total": "Amount",
    "address": "Location",
}


def predicted_value(entities: list[dict], entity_type: str) -> str | None:
    values = [entity["name"] for entity in entities if entity["entity_type"] == entity_type]
    return values[0] if values else None


def comparable(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def field_metrics(results: list[dict], field: str) -> dict[str, float | int]:
    successful = [result for result in results if result["status"] == "success"]
    true_positives = sum(result["matches"][field] for result in successful)
    false_positives = sum(
        bool(result["predicted"][field]) and not result["matches"][field]
        for result in successful
    )
    false_negatives = sum(
        not result["matches"][field]
        for result in successful
    )
    precision = true_positives / (true_positives + false_positives) if true_positives + false_positives else 0.0
    recall = true_positives / (true_positives + false_negatives) if true_positives + false_negatives else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "exact_match_count": true_positives,
        "accuracy": true_positives / len(successful) if successful else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_example(example: SROIEExample) -> tuple[dict, str | None]:
    try:
        pages = extract_image(example.image_path)
    except Exception as error:
        return {"document_id": example.document_id, "status": "ocr_failed"}, str(error)
    if not any(page.text.strip() for page in pages):
        return {"document_id": example.document_id, "status": "ocr_failed"}, "OCR returned no text"
    try:
        entities = extract_entities(pages)
    except Exception as error:
        return {"document_id": example.document_id, "status": "extraction_failed"}, str(error)
    predictions = {field: predicted_value(entities, entity_type) for field, entity_type in FIELDS.items()}
    matches = {field: comparable(predictions[field]) == comparable(getattr(example, field)) for field in FIELDS}
    return {
        "document_id": example.document_id,
        "status": "success",
        "ground_truth": {field: getattr(example, field) for field in FIELDS},
        "predicted": predictions,
        "matches": matches,
    }, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a limited, no-Neo4j SROIE smoke evaluation")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--split", choices=("train", "test"), default="train")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.offset < 0:
        parser.error("--offset must be zero or greater")
    loader = SROIELoader()
    examples = list(loader.iter_examples(args.split, args.offset + args.limit))[args.offset:]
    results = []
    errors = []
    for example in examples:
        result, error = evaluate_example(example)
        results.append(result)
        if error:
            errors.append({"document_id": example.document_id, "error": error, "status": result["status"]})
        print(f"{example.document_id}: {result['status']}")
    successful = [result for result in results if result["status"] == "success"]
    summary = {
        "split": args.split,
        "limit": args.limit,
        "offset": args.offset,
        "samples_selected": len(examples),
        "successful": len(successful),
        "ocr_failures": sum(result["status"] == "ocr_failed" for result in results),
        "extraction_failures": sum(result["status"] == "extraction_failed" for result in results),
        "field_metrics": {},
        "results": results,
        "errors": errors,
        "note": "Smoke test only; these metrics do not represent full-dataset performance.",
    }
    for field in FIELDS:
        summary["field_metrics"][field] = field_metrics(results, field)
    summary["overall_metrics"] = {
        metric_name: sum(summary["field_metrics"][field][metric_name] for field in FIELDS) / len(FIELDS)
        for metric_name in ("precision", "recall", "f1")
    }
    output_path = Path("data/processed/sroie_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nSROIE EVALUATION")
    print("================")
    print(f"Samples: {len(examples)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(examples) - len(successful)}")
    print(f"OCR failures: {summary['ocr_failures']}; extraction failures: {summary['extraction_failures']}")
    for field, metric in summary["field_metrics"].items():
        print(f"\n{field.title()}:")
        print(f"Accuracy: {metric['accuracy']:.2%}")
        print(f"Precision: {metric['precision']:.4f}")
        print(f"Recall: {metric['recall']:.4f}")
        print(f"F1: {metric['f1']:.4f}")
    print("\nOverall (macro average):")
    print(f"Precision: {summary['overall_metrics']['precision']:.4f}")
    print(f"Recall: {summary['overall_metrics']['recall']:.4f}")
    print(f"F1: {summary['overall_metrics']['f1']:.4f}")
    print("\nExamples:")
    for result in successful[:3]:
        print(f"{result['document_id']}: {json.dumps({'ground_truth': result['ground_truth'], 'predicted': result['predicted']}, ensure_ascii=False)}")
    print(f"Results saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())