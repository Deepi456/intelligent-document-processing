from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class SROIEExample:
    document_id: str
    image_path: Path
    company: str | None
    date: str | None
    total: str | None
    address: str | None
    entity_annotation_text: str
    box_annotation_text: str

    def to_dict(self) -> dict:
        result = asdict(self)
        result["image_path"] = str(self.image_path)
        return result


class SROIELoader:
    def __init__(self, raw_root: str | Path = "data/raw") -> None:
        self.raw_root = Path(raw_root).expanduser().resolve()
        self.dataset_root = self._find_dataset()

    def _find_dataset(self) -> Path:
        candidates = []
        for directory in [self.raw_root, *self.raw_root.rglob("*")]:
            if directory.is_dir() and all(
                (directory / split / name).is_dir()
                for split in ("train", "test")
                for name in ("img", "box", "entities")
            ):
                candidates.append(directory)
        if not candidates:
            raise FileNotFoundError(
                "Could not find SROIE train/test img, box, and entities directories"
            )
        return min(candidates, key=lambda path: len(path.parts))

    def _split_root(self, split: str) -> Path:
        split = split.lower()
        if split not in {"train", "test"}:
            raise ValueError("split must be 'train' or 'test'")
        return self.dataset_root / split

    def iter_examples(self, split: str = "train", limit: int | None = None) -> Iterator[SROIEExample]:
        split_root = self._split_root(split)
        image_paths = sorted(
            path for path in (split_root / "img").iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        if limit is not None:
            if limit < 0:
                raise ValueError("limit must be zero or greater")
            image_paths = image_paths[:limit]
        for image_path in image_paths:
            yield self.load_example(split, image_path.stem)

    def load_example(self, split: str, document_id: str) -> SROIEExample:
        split_root = self._split_root(split)
        image_matches = sorted((split_root / "img").glob(f"{document_id}.*"))
        image_matches = [path for path in image_matches if path.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        if not image_matches:
            raise FileNotFoundError(f"Image not found for {split}/{document_id}")
        entity_path = split_root / "entities" / f"{document_id}.txt"
        box_path = split_root / "box" / f"{document_id}.txt"
        entity_text = _read_annotation_text(entity_path)
        box_text = _read_annotation_text(box_path)
        values = json.loads(entity_text)
        return SROIEExample(
            document_id=document_id,
            image_path=image_matches[0],
            company=values.get("company"),
            date=values.get("date"),
            total=values.get("total"),
            address=values.get("address"),
            entity_annotation_text=entity_text,
            box_annotation_text=box_text,
        )

    def load_box_annotation(self, split: str, document_id: str) -> list[dict]:
        raw_text = self.load_example(split, document_id).box_annotation_text
        annotations = []
        for line_number, line in enumerate(raw_text.splitlines(), start=1):
            fields = line.split(",", 8)
            if len(fields) != 9:
                raise ValueError(f"Invalid box annotation on line {line_number}: {line}")
            annotations.append({
                "coordinates": [int(value) for value in fields[:8]],
                "text": fields[8],
                "line_number": line_number,
            })
        return annotations

    def normalized_dict(self, split: str, document_id: str) -> dict:
        example = self.load_example(split, document_id)
        return {
            "document_id": example.document_id,
            "image_path": str(example.image_path),
            "company": example.company,
            "date": example.date,
            "total": example.total,
            "address": example.address,
        }


def _read_annotation_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")