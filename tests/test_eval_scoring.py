"""Tests for the benchmark scoring code itself — three real scoring bugs were
found and fixed during this project by testing against actual agent output, so
these are regression tests as much as unit tests."""
import json

from backend.evaluation.eval_runner import (
    compute_ea, extract_numeric, extract_district_list,
    _score_dict_answer, check_hallucination, compute_rcq,
)


# ── extract_numeric ───────────────────────────────────────────────────────────
def test_extract_numeric_prefers_percent_suffixed_number():
    """Regression test: used to grab the first number anywhere in the text."""
    assert extract_numeric("Children aged 15-49 have a stunting rate of 23.0%") == 23.0
    assert extract_numeric("ANC 4+ visits: the rate is 53.1%") == 53.1


def test_extract_numeric_no_percent_falls_back_to_first_number():
    assert extract_numeric("The value is 42") == 42.0


def test_extract_numeric_no_number_returns_none():
    assert extract_numeric("no numbers here") is None


# ── extract_district_list ─────────────────────────────────────────────────────
def test_extract_district_list_from_prose():
    """Regression test: used to return [] for any non-JSON prose answer,
    scoring every ranking question 0% regardless of correctness."""
    text = "The top districts are South Goa, Kannur, and Wayanad in that order."
    result = extract_district_list(text)
    assert "South Goa" in result
    assert "Kannur" in result
    assert "Wayanad" in result


def test_extract_district_list_avoids_substring_false_positives():
    """'West' is itself a real Sikkim district and used to falsely match inside
    'West Khasi Hills'."""
    result = extract_district_list("The worst district is West Khasi Hills.")
    assert "West Khasi Hills" in result
    assert result.count("West Khasi Hills") == 1


def test_extract_district_list_from_json():
    text = json.dumps([{"district": "Kannur"}, {"district": "Wayanad"}])
    assert extract_district_list(text) == ["Kannur", "Wayanad"]


# ── compute_ea ────────────────────────────────────────────────────────────────
def test_compute_ea_numeric_within_tolerance():
    assert compute_ea("The stunting rate is 23.0%", "23.0%", "numeric") == 1.0


def test_compute_ea_numeric_outside_tolerance():
    assert compute_ea("The stunting rate is 10.0%", "23.0%", "numeric") == 0.0


def test_compute_ea_empty_answer_scores_zero_not_partial_credit():
    """Regression test: comparison/distribution questions used to get a free 0.5
    no matter what — including a blank answer."""
    gt = json.dumps({"Bihar": 42.6, "Kerala": 23.3})
    assert compute_ea("", gt, "comparison") == 0.0
    assert compute_ea("", gt, "distribution") == 0.0


def test_compute_ea_comparison_rewards_correct_values():
    gt = json.dumps({"Bihar": 42.6, "Kerala": 23.3})
    full = compute_ea("Bihar is 42.6%, Kerala is 23.3%", gt, "comparison")
    wrong = compute_ea("Both states are around 90%", gt, "comparison")
    assert full == 1.0
    assert wrong == 0.0


def test_compute_ea_ranking_uses_kendall_tau():
    # extract_district_list only matches real district names from the dataset,
    # so the ground truth here has to use ones that actually exist.
    gt = json.dumps(["Kannur", "Wayanad", "Idukki", "Kollam"])
    perfect = compute_ea("Kannur, Wayanad, Idukki, Kollam", gt, "ranking")
    assert perfect == 1.0


# ── _score_dict_answer ────────────────────────────────────────────────────────
def test_score_dict_answer_partial_credit():
    gt = {"Bihar": 42.6, "Kerala": 23.3, "Uttar Pradesh": 39.6}
    score = _score_dict_answer("Bihar is 42.6%", gt)
    assert 0 < score < 1


def test_score_dict_answer_handles_nested_dict():
    gt = {"top_3_states": {"Kerala": 5.0}, "bottom_3_states": {"Bihar": 45.0}}
    score = _score_dict_answer("Kerala leads at 5.0%, Bihar trails at 45.0%", gt)
    assert score == 1.0


# ── check_hallucination ───────────────────────────────────────────────────────
def test_check_hallucination_flags_fabricated_district(df):
    result = check_hallucination("Nowhereville district has a stunting rate of 20%", df)
    assert result["has_hallucination"] is True


def test_check_hallucination_flags_out_of_range_value(df):
    result = check_hallucination("The rate is 150%", df)
    assert result["has_hallucination"] is True


def test_check_hallucination_clean_answer(df):
    result = check_hallucination("Kerala has a stunting rate of 23%", df)
    assert result["has_hallucination"] is False


# ── compute_rcq ───────────────────────────────────────────────────────────────
def test_compute_rcq_perfect_match():
    assert compute_rcq(["pandas_query"], "factual_lookup") == 1.0


def test_compute_rcq_empty_sequence():
    assert compute_rcq([], "factual_lookup") == 0.0


def test_compute_rcq_partial_match():
    # correlation's gold sequence is [correlation_finder, chart_generator, insight_writer] —
    # using just one of the three is a genuine partial match, not zero overlap.
    score = compute_rcq(["correlation_finder"], "correlation")
    assert 0 < score < 1
