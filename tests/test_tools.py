"""Tests for the 7 agent tools — all run against real data, no LLM/API key needed."""
import math
from pathlib import Path

from backend.agent.tools.tools import (
    pandas_query, sql_query, trend_analyser, correlation_finder,
    insight_writer, chart_generator,
)


# ── pandas_query ──────────────────────────────────────────────────────────────
def test_pandas_query_basic_filter():
    r = pandas_query("result = df[df['state']=='Kerala'][['district','stunting_pct']]")
    assert r["status"] == "success"
    assert r["type"] == "dataframe"
    assert r["shape"][0] > 0


def test_pandas_query_missing_value_returns_none_not_nan():
    """Thrissur's fully_vaccinated_recall_pct is genuinely missing in the source data —
    regression test for the NaN-serialization bug fixed this session."""
    r = pandas_query(
        "result = df.loc[df['district']=='Thrissur', 'fully_vaccinated_recall_pct'].mean()"
    )
    assert r["status"] == "success"
    assert r["value"] is None  # not float('nan') — NaN isn't valid JSON


def test_pandas_query_no_result_variable_errors():
    r = pandas_query("x = 1 + 1")
    assert r["status"] == "error"


def test_pandas_query_blocks_forbidden_operations():
    for bad in ["import os", "open('x')", "__import__('os')"]:
        r = pandas_query(f"result = {bad!r}")
        assert r["status"] == "error"
        assert "Forbidden" in r["error"]


def test_pandas_query_scalar_result():
    r = pandas_query("result = df['stunting_pct'].mean()")
    assert r["status"] == "success"
    assert r["type"] == "scalar"
    assert isinstance(r["value"], float)


# ── sql_query ─────────────────────────────────────────────────────────────────
def test_sql_query_basic_select():
    r = sql_query("SELECT district, state FROM nfhs5 WHERE state = 'Kerala' LIMIT 5")
    assert r["status"] == "success"
    assert len(r["data"]) <= 5


def test_sql_query_rejects_non_select():
    r = sql_query("DROP TABLE nfhs5")
    assert r["status"] == "error"


# ── trend_analyser ────────────────────────────────────────────────────────────
def test_trend_analyser_known_indicator_with_trend_data():
    r = trend_analyser("stunting_pct", top_n=5)
    assert r["status"] == "success"
    assert r["trend_data_available"] is True
    assert len(r["best_5_districts"]) == 5
    assert len(r["worst_5_districts"]) == 5
    assert "most_improved_5_districts_since_nfhs4" in r


def test_trend_analyser_state_filter():
    r = trend_analyser("stunting_pct", state_filter="Bihar", top_n=3)
    assert r["status"] == "success"
    assert all(d["state"] == "Bihar" for d in r["best_3_districts"])


def test_trend_analyser_unknown_indicator_errors():
    r = trend_analyser("this is not a real indicator name at all xyz")
    assert r["status"] == "error"


# ── correlation_finder ────────────────────────────────────────────────────────
def test_correlation_finder_basic():
    r = correlation_finder("stunting_pct", "improved_sanitation_pct")
    assert r["status"] == "success"
    assert -1.0 <= r["pearson_r"] <= 1.0
    assert r["n_districts"] > 5


def test_correlation_finder_scatter_data_is_capped():
    """Regression test: scatter_data used to return all 706 rows, which alone
    pushed one LLM request to ~31,000 tokens."""
    r = correlation_finder("stunting_pct", "improved_sanitation_pct")
    assert len(r["scatter_data"]) <= 40


def test_correlation_finder_unknown_indicator_errors():
    r = correlation_finder("not a real column", "stunting_pct")
    assert r["status"] == "error"


# ── insight_writer ────────────────────────────────────────────────────────────
def test_insight_writer_only_uses_given_facts():
    data_result = {"status": "success", "data": [{"district": "Wayanad", "stunting_pct": 31.3}]}
    r = insight_writer(data_result, "What is stunting in Wayanad?")
    assert r["status"] == "success"
    assert "Wayanad" in r["insight"]["data_summary"]
    assert "31.3" in r["insight"]["data_summary"]


def test_insight_writer_rejects_failed_input():
    r = insight_writer({"status": "error", "error": "boom"}, "irrelevant question")
    assert r["status"] == "error"


# ── chart_generator ───────────────────────────────────────────────────────────
def test_chart_generator_creates_html_file(tmp_path, monkeypatch):
    data = [{"district": "A", "value": 1}, {"district": "B", "value": 2}]
    r = chart_generator("bar", "Test Chart", data, x_col="district", y_col="value",
                         filename="pytest_test_chart")
    assert r["status"] == "success"
    assert Path(r["chart_path"]).exists()
    Path(r["chart_path"]).unlink()  # clean up after ourselves


def test_chart_generator_empty_data_errors():
    r = chart_generator("bar", "Empty", [], x_col="a", y_col="b")
    assert r["status"] == "error"
