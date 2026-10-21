from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_SUFFIXES = {".txt", ".md"}


@dataclass
class Document:
    text: str
    metadata: dict = field(default_factory=dict)


def load_document(path: Path) -> Document:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported file type: {suffix}")

    text = path.read_text(encoding="utf-8")
    return Document(text=text, metadata={"source": path.name, "type": suffix})


def load_directory(folder: Path) -> list[Document]:
    documents = []
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            documents.append(load_document(path))
    return documents