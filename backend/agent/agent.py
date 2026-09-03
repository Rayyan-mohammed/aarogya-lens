"""
BharatHealth Analyst — Agent Core
LangChain ReAct agent wiring all 7 tools together.
Supports Claude (Anthropic) and GPT-4o (OpenAI) as LLM backends.
Falls back to a rule-based router when no API key is set (demo mode).
"""

import json
import os
import re
import time
import traceback
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "backend" / "data"


def get_gemini_keys() -> list:
    """All configured Gemini keys, in order (GEMINI_API_KEY, then _2, _3, _4, ...).
    Each comes from a separate Google account/project, so each has its own
    independent free-tier daily quota (20 requests/day/project) — rotating across
    them multiplies real daily throughput, unlike just having more keys on one
    account, which would all share the same exhausted quota."""
    keys = []
    base = os.getenv("GEMINI_API_KEY", "")
    if base:
        keys.append(base)
    i = 2
    while True:
        k = os.getenv(f"GEMINI_API_KEY_{i}", "")
        if not k:
            break
        keys.append(k)
        i += 1
    return keys


# ── Load schema for system prompt injection ───────────────────────────────────
def _load_schema_summary() -> str:
    schema_path = DATA_DIR / "schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # Group by cluster
    clusters: dict[str, list] = {}
    for col, meta in schema.items():
        cluster = meta.get("cluster", "other")
        # "trend" columns are excluded here — trend_analyser takes a plain indicator
        # name and looks up the right _change_from_nfhs4 column itself, so the model
        # doesn't need all 186 individual trend column names in its prompt
        if cluster not in ["identifier", "derived", "sample", "trend"]:
            clusters.setdefault(cluster, []).append(
                f"  - `{col}`: {meta.get('description', '')} [{meta.get('unit', '')}]"
            )

    lines = [f"## NFHS-5 Dataset Schema (706 districts × {len(schema)} columns, incl. NFHS-4 trend columns)\n"]
    for cluster, cols in sorted(clusters.items()):
        lines.append(f"### {cluster.replace('_', ' ').title()}")
        lines.extend(cols[:3])  # cap per cluster — keeps prompt small enough for free-tier TPM limits
        lines.append("")

    return "\n".join(lines)


# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT_TEMPLATE = """You are BharatHealth Analyst, an expert AI data analyst specialising in India's National Family Health Survey (NFHS-5) district-level public health data.

## Your Role
You help policymakers, NGO workers, and researchers extract precise, grounded insights from NFHS-5 data covering 706 districts across 36 states/UTs, with ~100 health indicators per district.

## Dataset Overview
- Survey: NFHS-5 (2019-21), Government of India — 706 districts, 36 states/UTs

{schema_summary}

## Tools Available
1. **semantic_search(query, n_results, state_filter)** — Find relevant districts using natural language. Use for vague queries like "struggling with nutrition".
2. **pandas_query(code)** — Execute pandas code on `df` (the NFHS-5 dataframe). Assign output to `result`. Use exact column names from schema.
3. **chart_generator(chart_type, title, data, x_col, y_col, color_col, filename)** — Create interactive charts. chart_type: 'bar', 'scatter', 'heatmap', 'box'.
4. **insight_writer(data_result, question)** — Synthesise grounded plain-English insights from data results.
5. **trend_analyser(indicator, state_filter, top_n)** — Rank districts by an indicator, find best/worst performers. When the indicator has real NFHS-4 (2015-16) trend data, also returns most-improved/most-declined districts since NFHS-4 — check `trend_data_available` in the result before making any "since NFHS-4" claim.
6. **correlation_finder(indicator_a, indicator_b, state_filter)** — Compute Pearson/Spearman correlation between two indicators.
7. **sql_query(query)** — Run a read-only SQL SELECT over the dataset for aggregation-style questions.

## Critical Rules
1. Ground every claim — cite district name, value, and "NFHS-5 (2019-21)".
2. Use exact column names from the schema above, never guess.
3. Never hallucinate — if data isn't in the dataset, say so.
4. Ranking questions: pandas_query with nlargest/nsmallest.
5. Correlation questions: use correlation_finder.
6. Trend/"since NFHS-4" questions: use trend_analyser, check `trend_data_available` first. NFHS-4 here is STATE-level only, so disclose that any change figure compares a district's NFHS-5 value to its own state's 2015-16 baseline, not a true district-level figure.
7. End every answer with a JSON block: {{"answer": "...", "key_facts": ["fact1 [NFHS-5]"], "confidence": "high/medium/low", "data_limitation": "..."}}
"""


def build_system_prompt() -> str:
    schema_summary = _load_schema_summary()
    return SYSTEM_PROMPT_TEMPLATE.format(schema_summary=schema_summary)


# ── Tool Registry ─────────────────────────────────────────────────────────────
def get_tool_registry():
    from backend.agent.tools.tools import (
        semantic_search,
        pandas_query,
        sql_query,
        chart_generator,
        insight_writer,
        trend_analyser,
        correlation_finder,
    )
    return {
        "semantic_search": semantic_search,
        "pandas_query": pandas_query, 
        "sql_query": sql_query,
        "chart_generator": chart_generator,
        "insight_writer": insight_writer,
        "trend_analyser": trend_analyser,
        "correlation_finder": correlation_finder,
    }


# ── LangChain Tool Wrappers ───────────────────────────────────────────────────
def build_langchain_tools():
    from langchain.tools import tool
    from backend.agent.tools.tools import (
        semantic_search as _semantic_search,
        pandas_query as _pandas_query,
        sql_query as _sql_query,
        chart_generator as _chart_generator,
        insight_writer as _insight_writer,
        trend_analyser as _trend_analyser,
        correlation_finder as _correlation_finder,
    )

    @tool
    def semantic_search(query: str, n_results: int = 5, state_filter: str = "") -> str:
        """Find districts by vague natural-language query, e.g. 'struggling with nutrition'."""
        result = _semantic_search(query, n_results, state_filter or None)
        return json.dumps(result, default=str)

    @tool
    def pandas_query(code: str) -> str:
        """Run pandas code on `df` (706x107). Assign output to `result`. Use exact column names."""
        result = _pandas_query(code)
        return json.dumps(result, default=str)

    @tool
    def chart_generator(chart_type: str, title: str, data_json: str, x_col: str, y_col: str, color_col: str = "", filename: str = "") -> str:
        """Make a Plotly chart ('bar'/'scatter'/'heatmap'/'box') from a JSON list of dicts."""
        try:
            data = json.loads(data_json)
        except Exception:
            return json.dumps({"status": "error", "error": "data_json must be valid JSON string of list of dicts"})
        result = _chart_generator(chart_type, title, data, x_col, y_col, color_col or None, filename or None)
        return json.dumps(result, default=str)

    @tool
    def insight_writer(data_result_json: str, question: str) -> str:
        """Write a grounded plain-English insight from a data result — no facts outside the data."""
        try:
            data_result = json.loads(data_result_json)
        except Exception:
            return json.dumps({"status": "error", "error": "data_result_json must be valid JSON"})
        result = _insight_writer(data_result, question)
        return json.dumps(result, default=str)

    @tool
    def trend_analyser(indicator: str, state_filter: str = "", top_n: int = 10) -> str:
        """Rank districts by an indicator; includes real NFHS-4 vs NFHS-5 change when available."""
        result = _trend_analyser(indicator, state_filter or None, top_n)
        return json.dumps(result, default=str)

    @tool
    def correlation_finder(indicator_a: str, indicator_b: str, state_filter: str = "") -> str:
        """Pearson/Spearman correlation between two indicators across districts."""
        result = _correlation_finder(indicator_a, indicator_b, state_filter or None)
        return json.dumps(result, default=str)

    @tool
    def sql_query(query: str) -> str:
        """Run a read-only SQL SELECT against table 'nfhs5'."""
        result = _sql_query(query)
        return json.dumps(result, default=str)

    return [semantic_search, pandas_query, sql_query, chart_generator, insight_writer, trend_analyser, correlation_finder]


# ── Agent Factory ─────────────────────────────────────────────────────────────
def create_agent(model_name: str = "claude", api_key: Optional[str] = None):
    """
    Create a LangChain ReAct agent.
    model_name: 'claude' | 'gpt4o' | 'demo'
    """
    tools = build_langchain_tools()
    system_prompt = build_system_prompt()

    if model_name == "claude":
        from langchain_anthropic import ChatAnthropic
        anthropic_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        llm = ChatAnthropic(
            model="claude-sonnet-4-5",
            api_key=anthropic_key,
            max_tokens=4096,
            temperature=0,
        )

    elif model_name == "gpt4o":
        from langchain_openai import ChatOpenAI
        openai_key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not openai_key:
            raise ValueError("OPENAI_API_KEY not set")
        llm = ChatOpenAI(
            model="gpt-4o",
            api_key=openai_key,
            temperature=0,
            max_tokens=4096,
        )
    
    elif model_name == "groq":
        from langchain_groq import ChatGroq
        groq_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not groq_key:
            raise ValueError("GROQ_API_KEY not set")
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=groq_key,
            temperature=0,
            max_tokens=4096,
        )

    elif model_name == "openrouter":
        from langchain_openai import ChatOpenAI
        openrouter_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        llm = ChatOpenAI(
            model="google/gemini-2.5-flash",
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
            max_tokens=2048,
        )

    elif model_name == "gemini":
        # Direct Gemini API, not routed through OpenRouter — that path needs paid
        # OpenRouter credits (none available); this uses the raw GEMINI_API_KEY.
        from langchain_google_genai import ChatGoogleGenerativeAI
        gemini_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY not set")
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            google_api_key=gemini_key,
            temperature=0,
            max_tokens=4096,
        )

    else:
        raise ValueError(f"Unsupported model: {model_name}. Use 'claude', 'gpt4o', 'groq', 'openrouter', or 'gemini'")

    from langgraph.prebuilt import create_react_agent
    from langchain_core.messages import SystemMessage

    agent = create_react_agent(
        llm,
        tools,
        prompt=system_prompt,
    )

    return agent


RATE_LIMIT_MARKERS = ("rate_limit", "429", "413", "tokens per minute", "requires more credits")

# A ~25hr benchmark run once failed 184/200 questions in under a second each — too
# fast to be a quota wait, and it didn't match any of the markers above, so nothing
# retried it even once. Never found the exact error text (it wasn't being saved at
# the time), but it has every sign of a transient provider-side blip: covering these
# markers too means a real outage/5xx/timeout gets retried instead of failing cold.
TRANSIENT_ERROR_MARKERS = ("timeout", "timed out", "connection", "503", "502", "500",
                           "overloaded", "temporarily unavailable", "server error",
                           "internal error", "bad gateway", "service unavailable")

# Above this, a provider's "try again in Xs" is pointing at an hourly/daily quota reset,
# not a momentary dip — waiting it out would stall the whole run for one question.
MAX_RATE_LIMIT_WAIT = 300.0


def _parse_retry_after(message: str) -> Optional[float]:
    """Pull a provider-suggested wait time out of messages like
    'Please try again in 8m46.176s', '2h3m1s', or 'retry in 5.66s'."""
    m = re.search(r"(?:try again in|retry in)\s+(?:(\d+)h)?(?:(\d+)m)?(\d+\.?\d*)s", message, re.IGNORECASE)
    if not m:
        return None
    hours = float(m.group(1)) if m.group(1) else 0.0
    minutes = float(m.group(2)) if m.group(2) else 0.0
    return hours * 3600 + minutes * 60 + float(m.group(3))


def _invoke_with_retry(agent, question: str, max_retries: int = 3, base_wait: float = 20.0):
    """Retry on transient rate-limit errors (free-tier TPM caps, momentary credit dips)
    instead of recording a real question as a hard failure because of API pacing.
    Honors a provider's own suggested wait time when it gives one, and gives up right
    away (instead of burning a full 20/40/60s backoff for nothing) when that wait is
    clearly an hourly/daily quota reset rather than something a retry can fix."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return agent.invoke(
                {"messages": [{"role": "user", "content": question}]},
                config={"callbacks": []},
            )
        except Exception as e:
            last_error = e
            msg = str(e).lower()
            retryable = any(m in msg for m in RATE_LIMIT_MARKERS) or any(m in msg for m in TRANSIENT_ERROR_MARKERS)
            if attempt < max_retries and retryable:
                suggested = _parse_retry_after(str(e))
                if suggested is not None and suggested > MAX_RATE_LIMIT_WAIT:
                    raise last_error
                time.sleep(suggested + 1 if suggested is not None else base_wait * (attempt + 1))
                continue
            raise last_error


# ── Query Runner ──────────────────────────────────────────────────────────────
def run_query(
    question: str,
    model_name: str = "claude",
    api_key: Optional[str] = None,
    state_filter: Optional[str] = None,
) -> dict:
    """
    Run a natural language query through the BharatHealth agent.
    Returns structured response with answer, chart path, tool calls, latency.
    """
    start_time = time.time()
    tool_call_sequence = []

    if state_filter:
        question = f"[Filter: State = {state_filter}] {question}"

    try:
        agent = create_agent(model_name, api_key)

        # Collect tool call trace
        events = []
        result = _invoke_with_retry(agent, question)

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract final message
        messages = result.get("messages", [])
        final_answer = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content:
                if hasattr(msg, "type") and msg.type == "ai":
                    final_answer = msg.content if isinstance(msg.content, str) else str(msg.content)
                    break

        # Extract tool calls from message history
        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_call_sequence.append(tc.get("name", "unknown"))

        # Try to extract structured JSON from answer
        structured = {}
        json_match = None
        json_blocks = re.findall(r"```json\s*(.*?)\s*```", final_answer, re.DOTALL)
        if json_blocks:
            try:
                structured = json.loads(json_blocks[-1])
            except Exception:
                pass

        # Find any chart paths in messages
        chart_path = None
        for msg in messages:
            content = str(msg.content) if hasattr(msg, "content") else ""
            chart_match = re.search(r'"chart_path":\s*"([^"]+\.html)"', content)
            if chart_match:
                chart_path = chart_match.group(1)

        return {
            "status": "success",
            "question": question,
            "answer": final_answer,
            "structured": structured,
            "chart_path": chart_path,
            "tool_call_sequence": tool_call_sequence,
            "model_used": model_name,
            "latency_ms": latency_ms,
        }

    except Exception as e:
        return {
            "status": "error",
            "question": question,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "model_used": model_name,
            "latency_ms": int((time.time() - start_time) * 1000),
        }
