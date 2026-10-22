from dataclasses import dataclass, field

from app.ingestion.loader import Document


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


def split_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    pieces = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space

        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)

        if end >= len(text):
            break
        start = max(end - overlap, start + 1)

    return pieces


def chunk_documents(documents: list[Document], chunk_size: int = 500, overlap: int = 100) -> list[Chunk]:
    chunks = []
    for doc in documents:
        for index, piece in enumerate(split_text(doc.text, chunk_size, overlap)):
            metadata = {**doc.metadata, "chunk_index": index, "char_count": len(piece)}
            chunks.append(Chunk(text=piece, metadata=metadata))
    return chunks