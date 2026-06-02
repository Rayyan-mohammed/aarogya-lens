"""
BharatHealth Analyst — Agent Core
LangChain ReAct agent wiring all 6 tools together.
Supports Claude (Anthropic) and GPT-4o (OpenAI) as LLM backends.
Falls back to a rule-based router when no API key is set (demo mode).
"""

import json
import os
import time
import traceback
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "backend" / "data"


# ── Load schema for system prompt injection ───────────────────────────────────
def _load_schema_summary() -> str:
    schema_path = DATA_DIR / "schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # Group by cluster
    clusters: dict[str, list] = {}
    for col, meta in schema.items():
        cluster = meta.get("cluster", "other")
        if cluster not in ["identifier", "derived", "sample"]:
            clusters.setdefault(cluster, []).append(
                f"  - `{col}`: {meta.get('description', '')} [{meta.get('unit', '')}]"
            )

    lines = ["## NFHS-5 Dataset Schema (706 districts × 107 columns)\n"]
    for cluster, cols in sorted(clusters.items()):
        lines.append(f"### {cluster.replace('_', ' ').title()}")
        lines.extend(cols[:15])  # cap per cluster to keep prompt manageable
        lines.append("")

    return "\n".join(lines)


# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT_TEMPLATE = """You are BharatHealth Analyst, an expert AI data analyst specialising in India's National Family Health Survey (NFHS-5) district-level public health data.

## Your Role
You help policymakers, NGO workers, and researchers extract precise, grounded insights from NFHS-5 data covering 706 districts across 36 states/UTs, with ~100 health indicators per district.

## Dataset Overview
- Survey: NFHS-5 (2019–21), Government of India
- Coverage: 706 districts, 36 states/UTs
- Indicators: Child nutrition (stunting, wasting, underweight), Maternal health (institutional delivery, ANC visits, C-section), Anaemia (children, women, men), Vaccination (BCG, DPT, polio, measles), Sanitation (improved toilet, clean water, cooking fuel), NCDs (hypertension, blood sugar, obesity), Family planning, Women's empowerment, and more.

{schema_summary}

## Tools Available
1. **semantic_search(query, n_results, state_filter)** — Find relevant districts using natural language. Use for vague queries like "struggling with nutrition".
2. **pandas_query(code)** — Execute pandas code on `df` (the NFHS-5 dataframe). Assign output to `result`. Use exact column names from schema.
3. **chart_generator(chart_type, title, data, x_col, y_col, color_col, filename)** — Create interactive charts. chart_type: 'bar', 'scatter', 'heatmap', 'box'.
4. **insight_writer(data_result, question)** — Synthesise grounded plain-English insights from data results.
5. **trend_analyser(indicator, state_filter, top_n)** — Rank districts by an indicator, find best/worst performers.
6. **correlation_finder(indicator_a, indicator_b, state_filter)** — Compute Pearson/Spearman correlation between two indicators.

## Critical Rules
1. **Ground every claim** — cite the specific district name, indicator value, and "NFHS-5 (2019-21)" for every statistic.
2. **Use exact column names** — never guess or invent column names. Use only names from the schema above.
3. **Never hallucinate** — if a district or indicator is not in the dataset, say so explicitly.
4. **For ranking questions**: use pandas_query with nlargest/nsmallest, then chart_generator for top-10 bar chart.
5. **For correlation questions**: always use correlation_finder, then chart_generator with chart_type='scatter'.
6. **For state comparisons**: use pandas_query to groupby state, then chart_generator with chart_type='bar'.
7. **Output format**: always end with a structured JSON block:
```json
{{
  "answer": "...",
  "key_facts": ["fact1 [NFHS-5]", "fact2 [NFHS-5]"],
  "chart_generated": true/false,
  "confidence": "high/medium/low",
  "data_limitation": "any missing data caveats"
}}
```

## Example Tool Usage
- User asks "worst stunting districts in Bihar":
  → pandas_query: `result = df[df['state']=='Bihar'].nlargest(10, 'stunting_pct')[['district','state','stunting_pct']]`
  → chart_generator with chart_type='bar', x_col='district', y_col='stunting_pct'
  → insight_writer with the result

- User asks "correlation between sanitation and stunting":
  → correlation_finder('improved_sanitation_pct', 'stunting_pct')
  → chart_generator with chart_type='scatter' using scatter_data
"""


def build_system_prompt() -> str:
    schema_summary = _load_schema_summary()
    return SYSTEM_PROMPT_TEMPLATE.format(schema_summary=schema_summary)


# ── Tool Registry ─────────────────────────────────────────────────────────────
def get_tool_registry():
    from backend.agent.tools.tools import (
        semantic_search,
        pandas_query,
        chart_generator,
        insight_writer,
        trend_analyser,
        correlation_finder,
    )
    return {
        "semantic_search": semantic_search,
        "pandas_query": pandas_query,
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
        chart_generator as _chart_generator,
        insight_writer as _insight_writer,
        trend_analyser as _trend_analyser,
        correlation_finder as _correlation_finder,
    )

    @tool
    def semantic_search(query: str, n_results: int = 5, state_filter: str = "") -> str:
        """Search for districts using natural language. Use for vague queries about health problems, struggling districts, etc. Args: query (str), n_results (int, default 5), state_filter (str, optional state name)."""
        result = _semantic_search(query, n_results, state_filter or None)
        return json.dumps(result, default=str)

    @tool
    def pandas_query(code: str) -> str:
        """Execute pandas code on the NFHS-5 dataframe (variable name: `df`, 706 rows x 107 cols). MUST assign output to `result`. Use exact column names from schema. Example: result = df[df['state']=='Bihar'].nlargest(5,'stunting_pct')[['district','state','stunting_pct']]"""
        result = _pandas_query(code)
        return json.dumps(result, default=str)

    @tool
    def chart_generator(chart_type: str, title: str, data_json: str, x_col: str, y_col: str, color_col: str = "", filename: str = "") -> str:
        """Generate an interactive Plotly chart. chart_type: 'bar','scatter','heatmap','box'. data_json: JSON string of list of dicts. x_col, y_col: column names in data. Returns path to HTML file."""
        try:
            data = json.loads(data_json)
        except Exception:
            return json.dumps({"status": "error", "error": "data_json must be valid JSON string of list of dicts"})
        result = _chart_generator(chart_type, title, data, x_col, y_col, color_col or None, filename or None)
        return json.dumps(result, default=str)

    @tool
    def insight_writer(data_result_json: str, question: str) -> str:
        """Write a grounded plain-English insight from a data result. data_result_json: JSON string of the result from pandas_query or trend_analyser. Only facts in the data are used — no hallucination."""
        try:
            data_result = json.loads(data_result_json)
        except Exception:
            return json.dumps({"status": "error", "error": "data_result_json must be valid JSON"})
        result = _insight_writer(data_result, question)
        return json.dumps(result, default=str)

    @tool
    def trend_analyser(indicator: str, state_filter: str = "", top_n: int = 10) -> str:
        """Analyse indicator distribution across districts. Finds best/worst performers nationally or within a state. indicator: column name or description. state_filter: optional state name."""
        result = _trend_analyser(indicator, state_filter or None, top_n)
        return json.dumps(result, default=str)

    @tool
    def correlation_finder(indicator_a: str, indicator_b: str, state_filter: str = "") -> str:
        """Compute Pearson and Spearman correlation between two health indicators across 706 districts. Returns correlation coefficients, p-values, and scatter data. indicator_a, indicator_b: column names or descriptions."""
        result = _correlation_finder(indicator_a, indicator_b, state_filter or None)
        return json.dumps(result, default=str)

    return [semantic_search, pandas_query, chart_generator, insight_writer, trend_analyser, correlation_finder]


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
            model="llama-3.1-8b-instant",
            api_key=groq_key,
            temperature=0,
            max_tokens=4096,
        )

    else:
        raise ValueError(f"Unsupported model: {model_name}. Use 'claude', 'gpt4o', or 'groq'")

    from langgraph.prebuilt import create_react_agent
    from langchain_core.messages import SystemMessage

    agent = create_react_agent(
        llm,
        tools,
        prompt=system_prompt,
    )

    return agent


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
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config={"callbacks": []},
        )

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
        import re
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
