import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ingestion.cleaning import clean_text

logger = logging.getLogger(__name__)

TEXT_SUFFIXES = {".txt", ".md"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | {".pdf"}


@dataclass
class Document:
    text: str
    metadata: dict = field(default_factory=dict)


def _make_document(text: str, source: str, file_type: str, page: int | None = None) -> Document:
    metadata = {"source": source, "type": file_type, "char_count": len(text)}
    if page is not None:
        metadata["page"] = page
    return Document(text=text, metadata=metadata)


def load_text_file(path: Path) -> list[Document]:
    text = clean_text(path.read_text(encoding="utf-8"))
    if not text:
        logger.warning("Skipping empty file: %s", path.name)
        return []
    return [_make_document(text, path.name, path.suffix.lower())]


def load_pdf(path: Path) -> list[Document]:
    reader = PdfReader(path)
    documents = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")
        if not text:
            logger.warning("No text on page %d of %s (scanned image?)", page_number, path.name)
            continue
        documents.append(_make_document(text, path.name, ".pdf", page=page_number))
    return documents


def load_file(path: Path) -> list[Document]:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return load_text_file(path)
    if suffix == ".pdf":
        return load_pdf(path)
    raise ValueError(f"Unsupported file type: {suffix}")


def load_directory(folder: Path) -> list[Document]:
    documents = []
    seen_hashes: dict[str, str] = {}
    for path in sorted(folder.iterdir()):
        if not (path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES):
            continue
        try:
            loaded = load_file(path)
        except UnicodeDecodeError:
            logger.warning("Skipping %s: not valid UTF-8", path.name)
            continue
        except PdfReadError:
            logger.warning("Skipping %s: unreadable or corrupt PDF", path.name)
            continue
        for doc in loaded:
            digest = hashlib.sha256(doc.text.encode("utf-8")).hexdigest()
            if digest in seen_hashes:
                logger.warning("Skipping %s: duplicate of %s", path.name, seen_hashes[digest])
                continue
            seen_hashes[digest] = path.name
            documents.append(doc)
    return documents
