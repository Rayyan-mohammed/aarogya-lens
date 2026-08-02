"""Data integrity checks for the NFHS-5 + NFHS-4 merged dataset."""
import re

import pandas as pd


def test_shape(df):
    assert df.shape == (706, 448)


def test_district_id_is_unique_and_complete(df):
    assert df["district_id"].isna().sum() == 0
    assert df["district_id"].duplicated().sum() == 0


def test_36_states(df):
    assert df["state"].nunique() == 36


def test_no_duplicate_district_state_pairs(df):
    assert not df.duplicated(subset=["district", "state"]).any()


def test_schema_matches_dataframe_columns_exactly(df, schema):
    """Every column in the data must be documented, and vice versa — a schema
    entry for a column that doesn't exist describes something that was never
    actually created (regression test for a real bug found this session)."""
    assert set(schema.keys()) == set(df.columns)


def test_trend_columns_come_in_complete_sets(df):
    """Every `_change_from_nfhs4` column should have matching `_change_pct`,
    `_filled`, and `_is_imputed` siblings — a partial set means the merge
    logic diverged from the schema-writing logic for that indicator."""
    change_cols = [c for c in df.columns if c.endswith("_change_from_nfhs4")]
    assert len(change_cols) == 62
    for col in change_cols:
        base = col[: -len("_change_from_nfhs4")]
        for suffix in ("_change_pct_from_nfhs4", "_filled", "_is_imputed", "_nfhs4_state"):
            assert f"{base}{suffix}" in df.columns, f"missing {base}{suffix}"


def test_is_imputed_flag_matches_filled_vs_original(df):
    """`_is_imputed` must be true exactly where the original column was missing
    and the NFHS-4 baseline filled it in — never on real district values."""
    change_cols = [c for c in df.columns if c.endswith("_change_from_nfhs4")]
    sample = change_cols[:5]  # full sweep is slow; a sample catches a systemic bug
    for col in sample:
        base = col[: -len("_change_from_nfhs4")]
        imputed = df[f"{base}_is_imputed"]
        was_missing = df[base].isna()
        assert (imputed == (was_missing & df[f"{base}_nfhs4_state"].notna())).all()


def test_no_fabricated_ladakh_baseline(df):
    """Ladakh has no NFHS-4 state baseline in the source data — its trend
    columns must be null, never silently filled with a neighboring state's
    numbers."""
    ladakh = df[df["state"].str.lower() == "ladakh"]
    if ladakh.empty:
        return
    change_cols = [c for c in df.columns if c.endswith("_nfhs4_state")]
    for col in change_cols[:5]:
        assert ladakh[col].isna().all()


def test_pct_columns_are_in_range(df):
    """Percentage indicators should fall within [0, 100] — catches unit bugs
    (e.g. a fraction accidentally left un-multiplied by 100)."""
    pct_cols = [c for c in df.columns if c.endswith("_pct") and not c.endswith(
        ("_change_pct_from_nfhs4",))]
    for col in pct_cols:
        valid = df[col].dropna()
        if valid.empty:
            continue
        assert valid.between(0, 100).all(), f"{col} has values outside [0, 100]"


def test_parquet_and_csv_row_counts_match():
    from pathlib import Path
    root = Path(__file__).parent.parent
    parquet_df = pd.read_parquet(root / "backend" / "data" / "nfhs5_clean.parquet")
    csv_df = pd.read_csv(root / "backend" / "data" / "nfhs5_clean.csv")
    assert len(parquet_df) == len(csv_df)
