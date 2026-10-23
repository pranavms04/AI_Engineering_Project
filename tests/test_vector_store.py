import json

import pytest
from app.ingestion.chunking import Chunk
from app.retrieval.vector_store import CHUNKS_FILE, VectorStore

CHUNKS = [
    Chunk("Path parameters are declared with type hints like item_id: int.", {"source": "fastapi.pdf", "page": 2}),
    Chunk("Biryani is cooked with rice, spices and slow heat.", {"source": "recipes.md"}),
    Chunk("Use pip install to add Python packages to a project.", {"source": "python.txt"}),
]


@pytest.fixture(scope="module")
def store():
    return VectorStore.build(CHUNKS)


def test_search_ranks_relevant_chunk_first(store):
    results = store.search("How do I declare a typed path parameter?", k=3)
    assert results[0][0].metadata["source"] == "fastapi.pdf"
    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)


def test_k_larger_than_store_is_capped(store):
    assert len(store.search("anything", k=10)) == len(CHUNKS)


def test_empty_store_returns_nothing():
    assert VectorStore.build([]).search("anything") == []


def test_save_and_load_roundtrip(store, tmp_path):
    store.save(tmp_path)
    loaded = VectorStore.load(tmp_path)

    assert len(loaded) == len(store)
    assert loaded.chunks[0].metadata == CHUNKS[0].metadata
    original = store.search("pip install", k=1)[0]
    reloaded = loaded.search("pip install", k=1)[0]
    assert reloaded[0].text == original[0].text
    assert reloaded[1] == pytest.approx(original[1], abs=1e-5)


def test_saved_metadata_is_json_not_pickle(store, tmp_path):
    store.save(tmp_path)
    payload = json.loads((tmp_path / CHUNKS_FILE).read_text(encoding="utf-8"))
    assert payload["chunks"][1]["metadata"]["source"] == "recipes.md"


def test_load_rejects_index_from_another_model(store, tmp_path):
    store.save(tmp_path)
    path = tmp_path / CHUNKS_FILE
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["model_name"] = "some-other-model"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Rebuild"):
        VectorStore.load(tmp_path)


def test_load_missing_folder_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_index"):
        VectorStore.load(tmp_path / "nothing-here")
