import pytest
from app.ingestion.chunking import split_text, chunk_documents
from app.ingestion.loader import Document

LONG_TEXT = " ".join(f"word{i}" for i in range(400))


def test_short_text_gives_one_chunk():
    assert split_text("small text", chunk_size=500, overlap=100) == ["small text"]


def test_chunks_respect_size_limit():
    pieces = split_text(LONG_TEXT, chunk_size=200, overlap=50)
    assert len(pieces) > 1
    assert all(len(p) <= 200 for p in pieces)


def test_neighbouring_chunks_overlap():
    pieces = split_text(LONG_TEXT, chunk_size=200, overlap=50)
    assert pieces[1][:20] in pieces[0]


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        split_text(LONG_TEXT, chunk_size=100, overlap=100)


def test_chunks_keep_source_metadata():
    doc = Document(text=LONG_TEXT, metadata={"source": "guide.pdf", "page": 7})
    chunks = chunk_documents([doc], chunk_size=200, overlap=50)
    assert chunks[0].metadata["source"] == "guide.pdf"
    assert chunks[0].metadata["page"] == 7
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))
    assert "chunk_index" not in doc.metadata
