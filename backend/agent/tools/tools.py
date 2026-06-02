"""
BharatHealth Analyst — Agent Tools
All 6 tools used by the ReAct agent.
"""

import io
import json
import os
import re
import traceback
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent.parent.parent  # aarogya-lens/
DATA_DIR = ROOT / "backend" / "data"
CHARTS_DIR = ROOT / "charts_output"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Shared dataframe (loaded once) ───────────────────────────────────────────
_df: Optional[pd.DataFrame] = None
_schema: Optional[dict] = None

PLOTLY_TEMPLATE = "plotly_dark"
BRAND_COLORS = ["#6366f1", "#22d3ee", "#f59e0b", "#10b981", "#ef4444", "#a78bfa"]


def get_df() -> pd.DataFrame:
    global _df
    if _df is None:
        parquet_path = DATA_DIR / "nfhs5_clean.parquet"
        _df = pd.read_parquet(parquet_path)
    return _df


def get_schema() -> dict:
    global _schema
    if _schema is None:
        schema_path = DATA_DIR / "schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            _schema = json.load(f)
    return _schema


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1: Semantic Search
# ─────────────────────────────────────────────────────────────────────────────
def semantic_search(query: str, n_results: int = 5, state_filter: Optional[str] = None) -> dict:
    """
    Search ChromaDB vector index for districts matching a natural language query.
    Use for vague/exploratory queries like 'which districts are struggling with nutrition'.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        VECTOR_DIR = ROOT / "backend" / "vector_store" / "chroma_db"
        client = chromadb.PersistentClient(path=str(VECTOR_DIR))
        collection = client.get_collection("districts")
        model = SentenceTransformer("all-MiniLM-L6-v2")

        embedding = model.encode([query]).tolist()

        where_filter = None
        if state_filter:
            # Fuzzy match state name
            df = get_df()
            states = df["state"].unique().tolist()
            from rapidfuzz import process, fuzz
            match, score, _ = process.extractOne(state_filter, states, scorer=fuzz.token_sort_ratio)
            if score > 60:
                where_filter = {"state": {"$eq": match}}

        query_kwargs = {
            "query_embeddings": embedding,
            "n_results": min(n_results, 10),
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = collection.query(**query_kwargs)

        districts = []
        for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
            districts.append({
                "rank": i + 1,
                "district": meta.get("district"),
                "state": meta.get("state"),
                "summary_excerpt": doc[:300],
                "key_metrics": {
                    k: v for k, v in meta.items()
                    if k not in ["district_id", "district", "state"] and v != -1
                }
            })

        return {
            "status": "success",
            "query": query,
            "results": districts,
            "total_found": len(districts),
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2: Pandas Query (sandboxed code execution)
# ─────────────────────────────────────────────────────────────────────────────
PANDAS_SAFE_GLOBALS = {
    "__builtins__": {
        "len": len, "range": range, "int": int, "float": float,
        "str": str, "list": list, "dict": dict, "tuple": tuple,
        "round": round, "abs": abs, "min": min, "max": max,
        "sum": sum, "sorted": sorted, "enumerate": enumerate,
        "zip": zip, "print": print, "bool": bool, "type": type,
        "isinstance": isinstance,
    },
    "pd": pd,
    "np": np,
}


def pandas_query(code: str) -> dict:
    """
    Execute pandas code on the NFHS-5 dataframe (variable name: `df`).
    The dataframe has 706 rows (districts) and 107 columns.
    ALWAYS use the exact column names from the schema. Return results as `result`.

    Example: result = df[df['state'] == 'Bihar'].nlargest(5, 'stunting_pct')[['district', 'state', 'stunting_pct']]
    """
    try:
        df = get_df()
        local_vars = {"df": df, "result": None}
        safe_globals = {**PANDAS_SAFE_GLOBALS}

        # Validate code — block dangerous operations
        forbidden = ["import", "open(", "exec(", "eval(", "__", "os.", "sys.", "subprocess"]
        for f in forbidden:
            if f in code:
                return {"status": "error", "error": f"Forbidden operation: '{f}' not allowed in queries"}

        exec(code, safe_globals, local_vars)

        result = local_vars.get("result")
        if result is None:
            return {"status": "error", "error": "Code must assign output to variable `result`"}

        if isinstance(result, pd.DataFrame):
            # Sanitise for JSON
            result_clean = result.where(pd.notnull(result), None)
            return {
                "status": "success",
                "type": "dataframe",
                "columns": result.columns.tolist(),
                "data": result_clean.head(50).to_dict(orient="records"),
                "shape": list(result.shape),
                "code_executed": code,
            }
        elif isinstance(result, pd.Series):
            result_clean = result.where(pd.notnull(result), None)
            return {
                "status": "success",
                "type": "series",
                "data": result_clean.head(50).to_dict(),
                "code_executed": code,
            }
        else:
            return {
                "status": "success",
                "type": "scalar",
                "value": result if not isinstance(result, (np.integer, np.floating)) else float(result),
                "code_executed": code,
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "code_executed": code,
        }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3: Chart Generator
# ─────────────────────────────────────────────────────────────────────────────
def chart_generator(
    chart_type: str,
    title: str,
    data: list[dict],
    x_col: str,
    y_col: str,
    color_col: Optional[str] = None,
    filename: Optional[str] = None,
) -> dict:
    """
    Generate an interactive Plotly chart from data.
    chart_type: 'bar', 'scatter', 'choropleth_india', 'heatmap', 'box'
    Returns the path to the saved HTML file.
    """
    try:
        df_chart = pd.DataFrame(data)
        if df_chart.empty:
            return {"status": "error", "error": "Empty data provided to chart_generator"}

        fig = None

        if chart_type == "bar":
            fig = px.bar(
                df_chart, x=x_col, y=y_col, color=color_col,
                title=title, template=PLOTLY_TEMPLATE,
                color_discrete_sequence=BRAND_COLORS,
            )
            fig.update_layout(xaxis_tickangle=-45)

        elif chart_type == "scatter":
            fig = px.scatter(
                df_chart, x=x_col, y=y_col,
                color=color_col, hover_name=df_chart.columns[0] if "district" in df_chart.columns else None,
                title=title, template=PLOTLY_TEMPLATE,
                color_discrete_sequence=BRAND_COLORS,
                trendline="ols",
            )

        elif chart_type == "heatmap":
            pivot = df_chart.pivot_table(index=x_col, columns=color_col or y_col, values=y_col, aggfunc="mean")
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values,
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale="RdYlGn_r",
            ))
            fig.update_layout(title=title, template=PLOTLY_TEMPLATE)

        elif chart_type == "box":
            fig = px.box(
                df_chart, x=x_col, y=y_col, color=color_col,
                title=title, template=PLOTLY_TEMPLATE,
                color_discrete_sequence=BRAND_COLORS,
            )

        else:  # default bar
            fig = px.bar(df_chart, x=x_col, y=y_col, title=title, template=PLOTLY_TEMPLATE)

        # Style
        fig.update_layout(
            paper_bgcolor="#0f172a",
            plot_bgcolor="#1e293b",
            font=dict(family="Inter, sans-serif", color="#e2e8f0"),
            title_font_size=18,
            margin=dict(l=60, r=30, t=60, b=80),
        )

        # Save
        fname = filename or re.sub(r"[^\w]+", "_", title.lower())[:40]
        out_path = CHARTS_DIR / f"{fname}.html"
        fig.write_html(str(out_path))

        return {
            "status": "success",
            "chart_path": str(out_path),
            "chart_filename": f"{fname}.html",
            "chart_type": chart_type,
            "title": title,
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4: Insight Writer
# ─────────────────────────────────────────────────────────────────────────────
def insight_writer(data_result: dict, question: str, llm_client=None) -> dict:
    """
    Generate a plain-English insight from a data result.
    ONLY uses facts present in data_result — no external knowledge added.
    Returns structured insight with citations.
    """
    if data_result.get("status") != "success":
        return {"status": "error", "error": "Cannot write insight from failed data result"}

    data = data_result.get("data", data_result.get("value", data_result.get("data")))

    # Build a fact summary string directly from data (no hallucination risk)
    facts = []
    if isinstance(data, list) and len(data) > 0:
        for row in data[:5]:  # top 5 rows only
            parts = [f"{k}: {v}" for k, v in row.items() if v is not None]
            facts.append(", ".join(parts))
    elif isinstance(data, dict):
        for k, v in list(data.items())[:5]:
            facts.append(f"{k}: {v}")
    elif data_result.get("type") == "scalar":
        facts.append(f"Result: {data_result.get('value')}")

    fact_str = " | ".join(facts) if facts else "No data available"

    insight = {
        "question": question,
        "data_summary": fact_str,
        "citations": [
            {"source": "NFHS-5 (2019-21)", "url": "https://www.data.gov.in/catalog/national-family-health-survey-5-nfhs-5-india-districts-factsheet-data"},
        ],
        "generated_by": "BharatHealth Analyst",
        "note": "All figures sourced directly from NFHS-5 district factsheet data. No external information added."
    }

    return {"status": "success", "insight": insight}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5: Trend Analyser (NFHS-4 vs NFHS-5 delta within dataset)
# ─────────────────────────────────────────────────────────────────────────────
def trend_analyser(indicator: str, state_filter: Optional[str] = None, top_n: int = 10) -> dict:
    """
    Analyse improvement or decline in an indicator across districts.
    Since we only have NFHS-5 district data, this computes intra-NFHS5 distribution
    and ranks districts within a state/nationally by their indicator value.
    For true NFHS-4 vs NFHS-5 comparison, highlights states with best/worst status.
    """
    try:
        df = get_df()

        # Fuzzy match column name
        schema = get_schema()
        cols = [c for c in df.columns if c not in ["district", "state", "district_id"]]

        from rapidfuzz import process, fuzz
        match, score, _ = process.extractOne(indicator, cols, scorer=fuzz.token_sort_ratio)
        if score < 50:
            return {"status": "error", "error": f"Indicator '{indicator}' not found. Best match: '{match}' (score: {score})"}

        col = match
        df_work = df[["district", "state", col]].dropna(subset=[col])

        if state_filter:
            states = df["state"].unique().tolist()
            state_match, s_score, _ = process.extractOne(state_filter, states, scorer=fuzz.token_sort_ratio)
            if s_score > 60:
                df_work = df_work[df_work["state"] == state_match]

        # Lower is better for malnutrition indicators
        lower_is_better_indicators = ["stunting", "wasting", "underweight", "anaemia", "child_marriage",
                                      "unmet_fp", "spousal_violence", "teen_pregnancy"]
        is_lower_better = any(kw in col for kw in lower_is_better_indicators)

        df_worst = df_work.nlargest(top_n, col) if is_lower_better else df_work.nsmallest(top_n, col)
        df_best = df_work.nsmallest(top_n, col) if is_lower_better else df_work.nlargest(top_n, col)

        col_desc = schema.get(col, {}).get("description", col)

        return {
            "status": "success",
            "indicator": col,
            "indicator_description": col_desc,
            "lower_is_better": is_lower_better,
            "scope": state_filter or "National",
            "national_mean": round(df[col].mean(), 2),
            "national_median": round(df[col].median(), 2),
            "national_min": round(df[col].min(), 2),
            "national_max": round(df[col].max(), 2),
            f"worst_{top_n}_districts": df_worst[["district", "state", col]].to_dict(orient="records"),
            f"best_{top_n}_districts": df_best[["district", "state", col]].to_dict(orient="records"),
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 6: Correlation Finder
# ─────────────────────────────────────────────────────────────────────────────
def correlation_finder(indicator_a: str, indicator_b: str, state_filter: Optional[str] = None) -> dict:
    """
    Compute Pearson and Spearman correlation between two indicators across districts.
    Returns correlation coefficients, p-values, and scatter data for chart_generator.
    """
    try:
        from rapidfuzz import process, fuzz

        df = get_df()
        cols = [c for c in df.columns if c not in ["district", "state", "district_id"]]

        match_a, score_a, _ = process.extractOne(indicator_a, cols, scorer=fuzz.token_sort_ratio)
        match_b, score_b, _ = process.extractOne(indicator_b, cols, scorer=fuzz.token_sort_ratio)

        if score_a < 45:
            return {"status": "error", "error": f"Indicator A '{indicator_a}' not found. Best: '{match_a}'"}
        if score_b < 45:
            return {"status": "error", "error": f"Indicator B '{indicator_b}' not found. Best: '{match_b}'"}

        df_work = df[["district", "state", match_a, match_b]].dropna()

        if state_filter:
            states = df["state"].unique().tolist()
            state_match, s_score, _ = process.extractOne(state_filter, states, scorer=fuzz.token_sort_ratio)
            if s_score > 60:
                df_work = df_work[df_work["state"] == state_match]

        if len(df_work) < 5:
            return {"status": "error", "error": "Not enough data points for correlation after filtering"}

        x = df_work[match_a].values
        y = df_work[match_b].values

        pearson_r, pearson_p = stats.pearsonr(x, y)
        spearman_r, spearman_p = stats.spearmanr(x, y)

        schema = get_schema()

        scatter_data = df_work[["district", "state", match_a, match_b]].rename(
            columns={match_a: "x_value", match_b: "y_value"}
        ).to_dict(orient="records")

        return {
            "status": "success",
            "indicator_a": match_a,
            "indicator_a_description": schema.get(match_a, {}).get("description", match_a),
            "indicator_b": match_b,
            "indicator_b_description": schema.get(match_b, {}).get("description", match_b),
            "scope": state_filter or "National",
            "n_districts": len(df_work),
            "pearson_r": round(pearson_r, 4),
            "pearson_p_value": round(pearson_p, 6),
            "spearman_r": round(spearman_r, 4),
            "spearman_p_value": round(spearman_p, 6),
            "interpretation": _interpret_correlation(pearson_r, pearson_p),
            "scatter_data": scatter_data[:706],
            "x_col": "x_value",
            "y_col": "y_value",
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


def _interpret_correlation(r: float, p: float) -> str:
    sig = "statistically significant" if p < 0.05 else "not statistically significant"
    direction = "positive" if r > 0 else "negative"
    if abs(r) >= 0.7:
        strength = "strong"
    elif abs(r) >= 0.4:
        strength = "moderate"
    elif abs(r) >= 0.2:
        strength = "weak"
    else:
        strength = "very weak or no"
    return f"{strength.capitalize()} {direction} correlation (r={r:.3f}, p={p:.4f}) — {sig}."
