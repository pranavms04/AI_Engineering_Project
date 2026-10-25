"""Evaluation metrics as small pure functions. No I/O, no models — easy to unit test.

A "page" is a (source, page) pair, e.g. ("fastapi-path-params.pdf", 2). Text files have page None.
"""

import numpy as np

Page = tuple[str, int | None]


def first_hit_rank(expected: set[Page], retrieved: list[Page]) -> int | None:
    """1-based rank of the first retrieved page that is expected, or None if none is."""
    for rank, page in enumerate(retrieved, start=1):
        if page in expected:
            return rank
    return None


def recall_at_k(cases: list[tuple[set[Page], list[Page]]], k: int) -> float:
    """Fraction of questions where ANY expected page appears in the top-k retrieved."""
    if not cases:
        return 0.0
    hits = 0
    for expected, retrieved in cases:
        rank = first_hit_rank(expected, retrieved[:k])
        if rank is not None:
            hits += 1
    return hits / len(cases)


def mrr(cases: list[tuple[set[Page], list[Page]]]) -> float:
    """Mean reciprocal rank: average of 1/rank of the first correct page (0 if not retrieved)."""
    if not cases:
        return 0.0
    total = 0.0
    for expected, retrieved in cases:
        rank = first_hit_rank(expected, retrieved)
        if rank is not None:
            total += 1 / rank
    return total / len(cases)


def keyword_coverage(answer: str, keywords: list[str]) -> float:
    """Fraction of expected keywords found in the answer (case-insensitive substring match).

    Weak proxy: a keyword can appear in a wrong answer, and a right answer can use other words.
    """
    if not keywords:
        return 1.0
    text = answer.lower()
    found = sum(1 for keyword in keywords if keyword.lower() in text)
    return found / len(keywords)


def citation_accuracy(valid_counts: list[int], total_counts: list[int]) -> float | None:
    """Valid citations / all citations, summed over answers. None if there were no citations at all."""
    total = sum(total_counts)
    if total == 0:
        return None
    return sum(valid_counts) / total


def abstention_scores(predicted: list[bool], truth: list[bool]) -> dict[str, float | None]:
    """Precision and recall of abstaining.

    precision: when the app abstained, how often it should have.
    recall:    of the questions it should abstain on, how many it did.
    None when the metric is undefined (nothing to divide by).
    """
    if len(predicted) != len(truth):
        raise ValueError(f"Got {len(predicted)} predictions but {len(truth)} labels")
    true_pos = sum(1 for p, t in zip(predicted, truth) if p and t)
    false_pos = sum(1 for p, t in zip(predicted, truth) if p and not t)
    false_neg = sum(1 for p, t in zip(predicted, truth) if not p and t)
    precision = true_pos / (true_pos + false_pos) if true_pos + false_pos else None
    recall = true_pos / (true_pos + false_neg) if true_pos + false_neg else None
    return {
        "precision": precision,
        "recall": recall,
        "true_positives": true_pos,
        "false_positives": false_pos,
        "false_negatives": false_neg,
    }


def percentile(values: list[float], p: float) -> float | None:
    """p-th percentile (0-100) with linear interpolation. None for an empty list."""
    if not values:
        return None
    return float(np.percentile(values, p))
