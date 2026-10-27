"""Squeeze 384-d embeddings into 3-d points for the knowledge map (PCA with numpy).

Only for display. Search still uses the full 384 numbers; a 3-d picture keeps
part of the information, and `explained` says how much.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Projection:
    mean: np.ndarray        # (384,) centre of the chunk vectors
    components: np.ndarray  # (3, 384) the three directions with the most variation
    scale: float            # divides coordinates so chunk points fit in [-1, 1]
    explained: tuple[float, ...]  # share of total variance each direction keeps

    def project(self, vectors: np.ndarray) -> np.ndarray:
        """(n, 384) -> (n, 3). Works for chunks and for a new question."""
        vectors = np.atleast_2d(vectors).astype(np.float32)
        return (vectors - self.mean) @ self.components.T / self.scale


def fit_projection(vectors: np.ndarray, dims: int = 3) -> Projection:
    """PCA via SVD. Deterministic: each direction's sign is fixed so the map never flips between runs."""
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2 or len(vectors) == 0:
        raise ValueError("Need a non-empty (n, d) array of vectors")

    mean = vectors.mean(axis=0)
    centred = vectors - mean
    _u, singular, vt = np.linalg.svd(centred, full_matrices=False)

    components = np.zeros((dims, vectors.shape[1]), dtype=np.float32)
    available = min(dims, vt.shape[0])
    components[:available] = vt[:available]
    for i in range(available):
        # SVD may return a direction or its mirror image; pick the one whose largest loading is positive.
        if components[i, np.argmax(np.abs(components[i]))] < 0:
            components[i] *= -1

    total = float((singular**2).sum())
    explained = tuple(float(s**2 / total) if total else 0.0 for s in singular[:dims])
    explained += (0.0,) * (dims - len(explained))

    coords = centred @ components.T
    scale = float(np.abs(coords).max()) or 1.0
    return Projection(mean=mean, components=components, scale=scale, explained=explained)
