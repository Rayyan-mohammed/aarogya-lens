# BharatHealth Analyst — Technical Report

**AI-Powered Natural Language Analysis of India's District Health Data**

*Mohammed Rayyan | B.Tech CSE (Data Science) | NMIMS University, Hyderabad*

This report replaces an earlier version that stated "90% Execution Accuracy, 0%
Hallucination Rate, 100% Reasoning Chain Quality" as achieved results. Those numbers
came from a single hardcoded mock answer, not a real evaluation run. Everything below
states only what has actually been built and verified; see `COMPLETION_SUMMARY.md` for
the current benchmark numbers once a full run has completed.

---

## 1. Problem Statement

India's National Family Health Survey (NFHS) is one of the world's most comprehensive
health datasets, yet it remains inaccessible to non-technical stakeholders — district
health officers, NGO field workers, journalists, policy researchers — who lack the SQL
or data-wrangling skills to query 700+ districts across ~100 indicators directly.
Existing LLM data-agent benchmarks (DataSciBench, AIDABench) focus on US/European
datasets; none target Indian health survey data specifically.

## 2. Architecture

```
Data Layer          Agent Layer           API Layer
NFHS-5 (706x448) -> LangChain ReAct    -> FastAPI (10 endpoints,
ChromaDB              7 tools             rate limiting,
Schema JSON            Multi-LLM           request logging)
```

### 2.1 Data Pipeline
- Source: NFHS-5 District Factsheet (data.gov.in), 706 districts.
- NFHS-4 (2015-16) merged in as trend data for 62 indicators. The NFHS-4 file
  available for this project is **state-level**, not district-level, so trend figures
  compare each district's NFHS-5 value against its own state's 2015-16 baseline —
  documented as such throughout the schema and system prompt, not presented as a true
  district-level comparison.
- Missing NFHS-5 values (2,286 cells across those 62 indicators) are filled with the
  NFHS-4 state baseline as a fallback, flagged via an `_is_imputed` column so a filled
  value is never mistaken for a real district measurement.
- Output: 706 rows x 448 columns, Parquet + CSV, full JSON schema with descriptions.
- ChromaDB vector index over natural-language district summaries (`all-MiniLM-L6-v2`,
  384-dim, no API key required).

### 2.2 Agent
LangChain/LangGraph ReAct agent with 7 tools:

| Tool | Purpose |
|---|---|
| `semantic_search` | ChromaDB retrieval for vague/exploratory queries |
| `pandas_query` | Sandboxed pandas execution over the full dataset |
| `sql_query` | Read-only SQL SELECT over the dataset |
| `chart_generator` | Plotly chart generation |
| `trend_analyser` | Best/worst ranking + real NFHS-4-vs-5 change when available |
| `correlation_finder` | Pearson/Spearman correlation between two indicators |
| `insight_writer` | Grounded plain-English synthesis from a tool result |

Verified working end-to-end against a real LLM (Groq `llama-3.3-70b-versatile` —
no Anthropic or OpenAI key is configured in this project; `agent.py` supports Claude
and GPT-4o but neither has been tested against a real key).

### 2.3 API
FastAPI, 10 endpoints, CORS, an in-memory rate limiter (10 req/min, 100 with an
`X-API-Key` header — single-instance, would need Redis behind multiple workers), and
JSON-line request logging as a local stand-in for the blueprint's BigQuery analytics.

### 2.4 Frontend
Single-page vanilla HTML/CSS/JS — not the Next.js the original project blueprint
specified. Functional: query bar, indicator explorer, correlation tool, chart embedding.

### 2.5 Deployment
`Dockerfile` + `docker-compose.yml` exist and have been built and run locally —
`/health` responds correctly with the full dataset from inside the container. **Nothing
is deployed to a public URL.** GCP Cloud Run / Vercel, as specified in the original
blueprint, have not been attempted.

---

## 3. Evaluation Framework

### 3.1 BharatHealth-Bench
200 questions, ground truth computed programmatically from the dataset:

| Query type | Count |
|---|---|
| Factual lookup | 59 |
| Aggregation/ranking | 52 |
| State comparison | 30 |
| Trend analysis | 38 |
| Correlation | 21 |

### 3.2 Metrics
- **EA (Execution Accuracy)** — numeric within tolerance, or Kendall's Tau > 0.8 for rankings.
- **AF (Answer Faithfulness)** — extracted factual claims verified against the dataset.
- **HR (Hallucination Rate)** — fabricated district/state names or out-of-range values.
- **RCQ (Reasoning Chain Quality)** — tool-call sequence vs. a gold sequence per query type.
- **LC (Latency/Cost)** — response time and (where applicable) API cost.

### 3.3 What was found running this for real
The first full run surfaced three real bugs in the scoring code itself, all now fixed:
1. `extract_numeric` grabbed the first number anywhere in an answer's text — e.g. "15"
   from "aged 15-49" instead of the actual answer, or "4" from "ANC 4+" instead of
   "53.1%". Answers were frequently correct; the scorer was wrong.
2. `extract_district_list` returned nothing for prose answers (only handled raw JSON),
   so every ranking question scored 0% regardless of whether the agent was right.
3. `correlation_finder` returned all 706 districts as scatter data, which flows back
   into the LLM's context as a tool observation — one correlation question alone pushed
   a single request to ~31,000 tokens, and all 21 correlation questions in that run
   failed outright from provider credit/rate-limit exhaustion as a result.

A corrected, fully-paced run (accounting for the ~12,000 TPM free-tier limit on Groq)
is the source of any results reported in `COMPLETION_SUMMARY.md`.

---

## 4. Known Limitations

- No Anthropic/OpenAI key configured — results reflect a free-tier open model, not the
  Claude Sonnet / GPT-4o the original blueprint specified as primary.
- NFHS-4 trend data is a state-level approximation, not true district-level comparison,
  because that's what the source file actually contains.
- No cloud deployment; no DVC data versioning; no automated test suite with coverage
  metrics (an earlier version of this report claimed 93% test coverage across 98 tests
  — no such test suite exists in this repository).
- Load testing, user acceptance testing, and concurrent-user figures in an earlier
  version of this report were never run — removed rather than restated unverified.

---

## References

1. Ministry of Health and Family Welfare, Government of India. "National Family Health Survey (NFHS-5) 2019-21." International Institute for Population Sciences, Mumbai.
2. LangChain. "ReAct Agent Framework Documentation." https://python.langchain.com
3. ChromaDB. "Vector Database for AI Applications." https://www.trychroma.com

---

**Mohammed Rayyan** — rayyan1652@gmail.com — B.Tech CSE (Data Science), NMIMS University, Hyderabad
