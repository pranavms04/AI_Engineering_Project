
import pytest
from app.ingestion.loader import load_document, load_directory


def test_loads_markdown_with_metadata(tmp_path):
    file = tmp_path / "guide.md"
    file.write_text("# Hello", encoding="utf-8")

    doc = load_document(file)

    assert doc.text == "# Hello"
    assert doc.metadata == {"source": "guide.md", "type": ".md"}


def test_rejects_unsupported_type(tmp_path):
    file = tmp_path / "image.png"
    file.write_bytes(b"\x89PNG")

    with pytest.raises(ValueError):
        load_document(file)