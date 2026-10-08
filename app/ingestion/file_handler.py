from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


@dataclass(frozen=True)
class DocumentFile:
    path: Path
    file_type: str


def detect_file_type(file_path: str | Path) -> DocumentFile:
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported file type. Use PDF, JPG, JPEG, or PNG.")
    return DocumentFile(path=path, file_type=suffix.lstrip("."))