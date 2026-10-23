import numpy as np
from app.retrieval.embedder import embed_texts, embed_query


def test_vectors_have_expected_shape():
    vectors = embed_texts(["hello", "world"])
    assert vectors.shape == (2, 384)
    assert vectors.dtype == np.float32


def test_vectors_are_normalized():
    vector = embed_query("normalization check")
    assert np.isclose(np.linalg.norm(vector), 1.0, atol=1e-5)


def test_similar_meaning_scores_higher_than_unrelated():
    q, related, unrelated = embed_texts([
        "How do I install Python packages?",
        "Using pip to add libraries to a project",
        "My favourite food is biryani",
    ])
    assert q @ related > q @ unrelated


def test_empty_input_returns_empty_array():
    assert embed_texts([]).shape == (0, 384)
