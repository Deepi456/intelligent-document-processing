"""Inspect a locally downloaded SROIE2019 dataset without modifying it."""

import argparse
import json
from collections import Counter
from pathlib import Path


def find_dataset(raw_root: Path) -> Path:
    candidates = []
    for directory in [raw_root, *raw_root.rglob("*")]:
        if not directory.is_dir():
            continue
        if all((directory / split / name).is_dir() for split in ("train", "test") for name in ("img", "box", "entities")):
            candidates.append(directory)
    if not candidates:
        raise FileNotFoundError("Could not find a SROIE directory containing train/test img, box, and entities folders")
    return min(candidates, key=lambda path: len(path.parts))


def files(directory: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in suffixes)


def print_split(dataset: Path, split: str, sample_count: int) -> None:
    split_root = dataset / split
    images = files(split_root / "img", (".jpg", ".jpeg", ".png"))
    boxes = files(split_root / "box", (".txt",))
    entities = files(split_root / "entities", (".txt",))
    image_stems = {path.stem for path in images}
    box_stems = {path.stem for path in boxes}
    entity_stems = {path.stem for path in entities}
    print(f"{split}: images={len(images)}, box={len(boxes)}, entities={len(entities)}")
    print(f"  matching basenames: images+box={len(image_stems & box_stems)}, images+entities={len(image_stems & entity_stems)}")
    for image in images[:sample_count]:
        box_path = split_root / "box" / f"{image.stem}.txt"
        entity_path = split_root / "entities" / f"{image.stem}.txt"
        print(f"  sample image: {image.relative_to(dataset)}")
        if box_path.exists():
            box_lines = box_path.read_text(encoding="utf-8-sig").splitlines()
            print(f"    box lines: {len(box_lines)}; first: {box_lines[0] if box_lines else '<empty>'}")
        if entity_path.exists():
            print(f"    entities: {entity_path.read_text(encoding='utf-8-sig').strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a local SROIE2019 dataset")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    dataset = find_dataset(args.raw_root.resolve())
    print(f"dataset: {dataset}")
    print("structure: <split>/{img,box,entities}")
    print_split(dataset, "train", args.samples)
    print_split(dataset, "test", args.samples)

    entity_files = [path for split in ("train", "test") for path in files(dataset / split / "entities", (".txt",))]
    fields = Counter()
    for path in entity_files:
        fields.update(json.loads(path.read_text(encoding="utf-8-sig")).keys())
    print(f"entity fields across {len(entity_files)} files: {', '.join(sorted(fields))}")
    print("maps to current schema: company -> Organization; date -> Date; total -> Amount; address -> Location")
    print("not available as explicit ground truth: person, product, quantity, invoice number, PO number, relationships")
    print("box annotation: quadrilateral coordinates and OCR transcription per text line")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())