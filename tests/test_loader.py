import pytest
from app.ingestion.cleaning import clean_text
from app.ingestion.loader import load_file, load_directory


def test_clean_text_fixes_hyphenation_and_spaces():
    raw = "you build appli-\ncation routes     that\nPage 7\n"
    assert clean_text(raw) == "you build application routes that"


def test_loads_markdown_with_metadata(tmp_path):
    file = tmp_path / "guide.md"
    file.write_text("# Hello", encoding="utf-8")

    [doc] = load_file(file)

    assert doc.metadata == {"source": "guide.md", "type": ".md", "char_count": 7}


def test_rejects_unsupported_type(tmp_path):
    file = tmp_path / "image.png"
    file.write_bytes(b"\x89PNG")
    with pytest.raises(ValueError):
        load_file(file)


def test_directory_skips_empty_and_bad_encoding(tmp_path):
    (tmp_path / "good.txt").write_text("real content", encoding="utf-8")
    (tmp_path / "empty.md").write_text("   \n", encoding="utf-8")
    (tmp_path / "broken.txt").write_bytes(b"\xff\xfe\xfa")

    docs = load_directory(tmp_path)

    assert [d.metadata["source"] for d in docs] == ["good.txt"]


def test_directory_skips_duplicate_content(tmp_path):
    (tmp_path / "a.txt").write_text("same content", encoding="utf-8")
    (tmp_path / "b.md").write_text("same   content\n", encoding="utf-8")
    (tmp_path / "c.txt").write_text("different content", encoding="utf-8")

    docs = load_directory(tmp_path)

    assert [d.metadata["source"] for d in docs] == ["a.txt", "c.txt"]

