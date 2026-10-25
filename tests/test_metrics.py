import pytest

from evaluation.metrics import (
    abstention_scores,
    citation_accuracy,
    first_hit_rank,
    keyword_coverage,
    mrr,
    percentile,
    recall_at_k,
)

A1, A2, A3, B1 = ("a.pdf", 1), ("a.pdf", 2), ("a.pdf", 3), ("b.md", None)


def test_first_hit_rank_finds_first_expected_page():
    assert first_hit_rank({A2}, [A1, A2, A3]) == 2
    assert first_hit_rank({A2, A3}, [A3, A2]) == 1
    assert first_hit_rank({A2}, [A1, A3]) is None
    assert first_hit_rank({B1}, [B1]) == 1  # text files have page None


def test_recall_at_k_counts_any_expected_page_in_top_k():
    cases = [
        ({A1}, [A1, A2]),  # hit at rank 1
        ({A2}, [A1, A2]),  # hit at rank 2
        ({A3}, [A1, A2]),  # miss
        ({A2, A3}, [A3, A1]),  # multi-page: any one counts
    ]
    assert recall_at_k(cases, k=1) == 2 / 4
    assert recall_at_k(cases, k=2) == 3 / 4


def test_recall_at_k_ignores_hits_beyond_k():
    assert recall_at_k([({A3}, [A1, A2, A3])], k=2) == 0.0


def test_mrr_averages_reciprocal_ranks_with_zero_for_misses():
    cases = [({A1}, [A1, A2]), ({A2}, [A1, A2]), ({A3}, [A1, A2])]
    assert mrr(cases) == pytest.approx((1 + 0.5 + 0) / 3)


def test_mrr_uses_first_correct_page_only():
    assert mrr([({A2}, [A1, A2, A2])]) == 0.5


def test_empty_inputs_do_not_divide_by_zero():
    assert recall_at_k([], k=4) == 0.0
    assert mrr([]) == 0.0
    assert percentile([], 50) is None


def test_keyword_coverage_is_case_insensitive_fraction():
    answer = "Declare it with a type annotation: item_id: INT [a.pdf, p. 1]"
    assert keyword_coverage(answer, ["int", "type annotation"]) == 1.0
    assert keyword_coverage(answer, ["int", "pydantic"]) == 0.5
    assert keyword_coverage("", ["int"]) == 0.0
    assert keyword_coverage("anything", []) == 1.0


def test_citation_accuracy_sums_over_answers():
    assert citation_accuracy([1, 0, 2], [1, 1, 2]) == 3 / 4
    assert citation_accuracy([0, 0], [0, 0]) is None  # no citations at all


def test_abstention_precision_and_recall():
    predicted = [True, True, False, False, True]
    truth = [True, False, True, False, True]
    scores = abstention_scores(predicted, truth)
    assert scores["true_positives"] == 2
    assert scores["false_positives"] == 1
    assert scores["false_negatives"] == 1
    assert scores["precision"] == pytest.approx(2 / 3)
    assert scores["recall"] == pytest.approx(2 / 3)


def test_abstention_undefined_cases_return_none():
    never = abstention_scores([False, False], [True, False])
    assert never["precision"] is None  # never abstained
    assert never["recall"] == 0.0
    nothing_to_find = abstention_scores([False], [False])
    assert nothing_to_find["recall"] is None


def test_abstention_rejects_length_mismatch():
    with pytest.raises(ValueError):
        abstention_scores([True], [True, False])


def test_percentile_interpolates():
    values = [100.0, 200.0, 300.0, 400.0]
    assert percentile(values, 50) == 250.0
    assert percentile(values, 100) == 400.0
    assert percentile([7.0], 95) == 7.0
