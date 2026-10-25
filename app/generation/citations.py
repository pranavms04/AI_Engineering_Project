import re

from app.ingestion.chunking import Chunk
from app.ingestion.loader import SUPPORTED_SUFFIXES

# Only extensions the app can index can be cited, so code like `[user.value]` is not a citation.
_EXTENSIONS = "|".join(sorted(suffix.lstrip(".") for suffix in SUPPORTED_SUFFIXES))

# Matches [file.pdf] or [file.pdf, p. 3], but not list indexing like items[0].
CITATION_PATTERN = re.compile(
    rf"(?<![\w\]])\[([^\[\],]+\.(?:{_EXTENSIONS}))(?:,\s*p\.\s*(\d+))?\]", re.IGNORECASE
)


def citation_tag(metadata: dict) -> str:
    if "page" in metadata:
        return f"[{metadata['source']}, p. {metadata['page']}]"
    return f"[{metadata['source']}]"


def extract_citations(answer: str) -> list[str]:
    tags = []
    for source, page in CITATION_PATTERN.findall(answer):
        tag = f"[{source.strip()}, p. {page}]" if page else f"[{source.strip()}]"
        if tag not in tags:
            tags.append(tag)
    return tags


def validate_citations(answer: str, retrieved: list[tuple[Chunk, float]]) -> tuple[list[str], list[str]]:
    allowed = {citation_tag(chunk.metadata) for chunk, _ in retrieved}
    valid, invalid = [], []
    for tag in extract_citations(answer):
        (valid if tag in allowed else invalid).append(tag)
    return valid, invalid
