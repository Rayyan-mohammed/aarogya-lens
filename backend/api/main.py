"""
BharatHealth Analyst — FastAPI Backend
All endpoints for the agent API.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "backend" / "data"
CHARTS_DIR = ROOT / "charts_output"

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="BharatHealth Analyst API",
    description="LLM-powered natural language analytics over NFHS-5 India district health data (706 districts, 107 indicators)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount charts directory for file serving
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/charts", StaticFiles(directory=str(CHARTS_DIR)), name="charts")

# ── Load data once on startup ─────────────────────────────────────────────────
_df: Optional[pd.DataFrame] = None
_schema: Optional[dict] = None

def get_df() -> pd.DataFrame:
    global _df
    if _df is None:
        _df = pd.read_parquet(DATA_DIR / "nfhs5_clean.parquet")
    return _df

def get_schema() -> dict:
    global _schema
    if _schema is None:
        with open(DATA_DIR / "schema.json", "r", encoding="utf-8") as f:
            _schema = json.load(f)
    return _schema


# ── Request / Response Models ─────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    model: str = "claude"          # "claude" | "gpt4o"
    state_filter: Optional[str] = None
    api_key: Optional[str] = None  # optional override; falls back to env var


class QueryResponse(BaseModel):
    status: str
    question: str
    answer: str
    chart_url: Optional[str] = None
    tool_call_sequence: list[str] = []
    model_used: str
    latency_ms: int
    structured: dict = {}
    error: Optional[str] = None


class DirectQueryRequest(BaseModel):
    """For quick direct-tool queries without the full LLM agent."""
    tool: str          # "pandas_query" | "trend_analyser" | "correlation_finder" | "semantic_search"
    params: dict = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check — returns dataset stats."""
    df = get_df()
    return {
        "status": "healthy",
        "dataset": "NFHS-5 (2019-21)",
        "districts": len(df),
        "states": df["state"].nunique(),
        "columns": len(df.columns),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@app.post("/query", response_model=QueryResponse)
async def query_agent(req: QueryRequest):
    """
    Main endpoint — runs the LangChain ReAct agent on a natural language question.
    Requires ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable (or pass api_key in request).
    """
    from backend.agent.agent import run_query

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    result = run_query(
        question=req.question,
        model_name=req.model,
        api_key=req.api_key,
        state_filter=req.state_filter,
    )

    chart_url = None
    if result.get("chart_path"):
        chart_filename = Path(result["chart_path"]).name
        chart_url = f"/charts/{chart_filename}"

    return QueryResponse(
        status=result.get("status", "error"),
        question=req.question,
        answer=result.get("answer", result.get("error", "No answer generated")),
        chart_url=chart_url,
        tool_call_sequence=result.get("tool_call_sequence", []),
        model_used=result.get("model_used", req.model),
        latency_ms=result.get("latency_ms", 0),
        structured=result.get("structured", {}),
        error=result.get("error"),
    )


@app.post("/query/direct")
async def direct_tool_query(req: DirectQueryRequest):
    """
    Call a single agent tool directly (no LLM agent needed).
    Useful for the frontend's indicator explorer, correlation view, etc.
    """
    from backend.agent.tools.tools import (
        semantic_search, pandas_query, sql_query, trend_analyser,
        correlation_finder, chart_generator,
    )

    tool_map = {
        "semantic_search": semantic_search,
        "pandas_query": pandas_query,
        "sql_query": sql_query,
        "trend_analyser": trend_analyser,
        "correlation_finder": correlation_finder,
        "chart_generator": chart_generator,
    }

    if req.tool not in tool_map:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {req.tool}. Valid: {list(tool_map.keys())}")

    try:
        result = tool_map[req.tool](**req.params)
        return result
    except TypeError as e:
        raise HTTPException(status_code=422, detail=f"Invalid params for tool '{req.tool}': {e}")


@app.get("/schema")
async def get_schema_endpoint():
    """Return full schema with column names, descriptions, units, and clusters."""
    return get_schema()


@app.get("/indicators")
async def get_indicators():
    """Return list of all indicator columns grouped by cluster."""
    schema = get_schema()
    clusters: dict[str, list] = {}
    for col, meta in schema.items():
        cluster = meta.get("cluster", "other")
        if cluster not in ["identifier", "derived", "sample", "other"]:
            clusters.setdefault(cluster, []).append({
                "column": col,
                "description": meta.get("description", col),
                "unit": meta.get("unit", ""),
            })
    return {"clusters": clusters, "total_indicators": len(schema)}


@app.get("/states")
async def get_states():
    """Return list of all states/UTs with district counts."""
    df = get_df()
    state_counts = df.groupby("state").size().reset_index(name="districts")
    return {"states": state_counts.to_dict(orient="records"), "total": len(state_counts)}


@app.get("/districts/{state}")
async def get_districts_by_state(state: str):
    """Return all districts in a given state with key indicators."""
    from rapidfuzz import process, fuzz
    df = get_df()
    states = df["state"].unique().tolist()
    match, score, _ = process.extractOne(state, states, scorer=fuzz.token_sort_ratio)
    if score < 60:
        raise HTTPException(status_code=404, detail=f"State '{state}' not found. Did you mean '{match}'?")

    df_state = df[df["state"] == match]
    cols = ["district_id", "district", "state", "stunting_pct", "anaemia_children_pct",
            "institutional_delivery_pct", "fully_vaccinated_recall_pct",
            "improved_sanitation_pct", "women_literacy_pct", "child_health_score"]
    available = [c for c in cols if c in df_state.columns]
    result = df_state[available].where(pd.notnull(df_state[available]), None)
    return {
        "state": match,
        "districts": result.to_dict(orient="records"),
        "count": len(result),
    }


@app.get("/district/{district_id}")
async def get_district_detail(district_id: int):
    """Return full indicator profile for a district by ID."""
    df = get_df()
    schema = get_schema()
    row = df[df["district_id"] == district_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"District ID {district_id} not found")

    row_dict = row.iloc[0].where(pd.notnull(row.iloc[0]), None).to_dict()
    # Annotate with schema info
    annotated = {}
    for col, val in row_dict.items():
        meta = schema.get(col, {})
        annotated[col] = {
            "value": val,
            "description": meta.get("description", col),
            "unit": meta.get("unit", ""),
            "cluster": meta.get("cluster", "other"),
        }
    return {"district_id": district_id, "indicators": annotated}


@app.get("/national-summary")
async def national_summary():
    """Return national-level summary statistics for key indicators."""
    df = get_df()
    key_indicators = [
        "stunting_pct", "wasting_pct", "underweight_pct",
        "anaemia_children_pct", "anaemia_all_women_pct",
        "institutional_delivery_pct", "fully_vaccinated_recall_pct",
        "improved_sanitation_pct", "women_literacy_pct",
        "anc_4plus_visits_pct", "child_marriage_pct",
        "fp_modern_method_pct", "women_overweight_pct",
        "men_high_blood_sugar_pct", "clean_cooking_fuel_pct",
    ]
    schema = get_schema()
    summary = {}
    for col in key_indicators:
        if col in df.columns:
            summary[col] = {
                "description": schema.get(col, {}).get("description", col),
                "national_mean": round(float(df[col].mean()), 2) if df[col].notna().any() else None,
                "national_median": round(float(df[col].median()), 2) if df[col].notna().any() else None,
                "min": round(float(df[col].min()), 2) if df[col].notna().any() else None,
                "max": round(float(df[col].max()), 2) if df[col].notna().any() else None,
                "missing_districts": int(df[col].isna().sum()),
                "unit": schema.get(col, {}).get("unit", "percent"),
            }
    return {"source": "NFHS-5 (2019-21)", "n_districts": len(df), "indicators": summary}


@app.get("/state-comparison/{indicator}")
async def state_comparison(indicator: str):
    """Return state-level averages for a given indicator."""
    from rapidfuzz import process, fuzz
    df = get_df()
    schema = get_schema()

    cols = [c for c in df.columns if c not in ["district", "state", "district_id"]]
    match, score, _ = process.extractOne(indicator, cols, scorer=fuzz.token_sort_ratio)
    if score < 50:
        raise HTTPException(status_code=404, detail=f"Indicator '{indicator}' not found. Best match: '{match}'")

    state_avg = df.groupby("state")[match].mean().reset_index()
    state_avg.columns = ["state", "mean_value"]
    state_avg["mean_value"] = state_avg["mean_value"].round(2)
    state_avg = state_avg.sort_values("mean_value", ascending=False)
    result = state_avg.where(pd.notnull(state_avg), None)

    return {
        "indicator": match,
        "description": schema.get(match, {}).get("description", match),
        "unit": schema.get(match, {}).get("unit", "percent"),
        "data": result.to_dict(orient="records"),
    }


@app.get("/benchmark/questions")
async def get_benchmark_questions():
    """Return benchmark question set (if available)."""
    bench_path = ROOT / "backend" / "evaluation" / "benchmark_questions.json"
    if not bench_path.exists():
        raise HTTPException(status_code=404, detail="Benchmark not yet generated. Run evaluation/generate_benchmark.py")
    with open(bench_path, "r", encoding="utf-8") as f:
        return json.load(f)
