import numpy as np
import pytest

from app.retrieval.projection import fit_projection


def random_vectors(n=40, d=384, seed=0):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, d)).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def test_projects_to_three_coordinates_inside_unit_range():
    vectors = random_vectors()
    projection = fit_projection(vectors)
    coords = projection.project(vectors)
    assert coords.shape == (40, 3)
    assert np.abs(coords).max() == pytest.approx(1.0)


def test_same_input_gives_same_map_every_time():
    vectors = random_vectors()
    a = fit_projection(vectors).project(vectors)
    b = fit_projection(vectors.copy()).project(vectors)
    assert np.allclose(a, b)


def test_sign_is_fixed_so_the_map_never_mirrors():
    projection = fit_projection(random_vectors())
    for component in projection.components:
        assert component[np.argmax(np.abs(component))] > 0


def test_explained_variance_is_a_decreasing_share():
    explained = fit_projection(random_vectors()).explained
    assert len(explained) == 3
    assert all(0 <= share <= 1 for share in explained)
    assert explained[0] >= explained[1] >= explained[2]
    assert sum(explained) <= 1.0 + 1e-6


def test_similar_vectors_land_closer_than_different_ones():
    rng = np.random.default_rng(1)
    base_a, base_b = rng.normal(size=384), rng.normal(size=384)
    group_a = base_a + 0.05 * rng.normal(size=(10, 384))
    group_b = base_b + 0.05 * rng.normal(size=(10, 384))
    vectors = np.vstack([group_a, group_b]).astype(np.float32)
    coords = fit_projection(vectors).project(vectors)

    within = np.linalg.norm(coords[0] - coords[1])
    across = np.linalg.norm(coords[0] - coords[10])
    assert within < across


def test_single_new_vector_can_be_projected():
    vectors = random_vectors()
    projection = fit_projection(vectors)
    assert projection.project(vectors[0]).shape == (1, 3)


def test_tiny_index_with_fewer_points_than_dimensions_still_works():
    vectors = random_vectors(n=2)
    projection = fit_projection(vectors)
    assert projection.project(vectors).shape == (2, 3)
    assert projection.explained[2] == 0.0


def test_rejects_empty_input():
    with pytest.raises(ValueError):
        fit_projection(np.zeros((0, 384)))
