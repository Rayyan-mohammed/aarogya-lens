# BharatHealth Analyst — Submission Package

**An AI-Powered Data Analysis Agent for India's District-Level Public Health Data**

*Mohammed Rayyan | B.Tech CSE (Data Science), NMIMS University*

This file used to repeat the same "90% EA, 0% HR, 100% RCQ" figures as
`TECHNICAL_REPORT.md` and `COMPLETION_SUMMARY.md` — all three traced back to one
hardcoded mock answer, not a real evaluation run. See `COMPLETION_SUMMARY.md` for
current, real numbers.

## What's built and verified

- **Data**: 706 districts x 448 columns (NFHS-5 + real NFHS-4 state-level trend data
  for 62 indicators + NFHS-4 fallback fill for missing NFHS-5 values), ChromaDB index
  over all 706 district summaries.
- **Agent**: 7 tools (`semantic_search`, `pandas_query`, `sql_query`, `chart_generator`,
  `trend_analyser`, `correlation_finder`, `insight_writer`) via a LangChain/LangGraph
  ReAct agent — confirmed working end-to-end against a real LLM.
- **API**: FastAPI, 10 endpoints, rate limiting + request logging middleware.
- **Frontend**: single-page HTML/JS UI (not Next.js).
- **Evaluation**: 200-question benchmark, ground truth computed programmatically, 5
  metrics implemented in real code. A corrected full run (after fixing 3 scoring bugs
  found along the way) is what any reported numbers come from.
- **Deployment**: Docker build + run verified locally. Not deployed to a public URL.

## Query types the agent handles
- Factual: "What is the stunting rate in Kerala?"
- Ranking: "Which 10 districts have worst child anaemia?"
- Comparison: "Compare vaccination rates across UP, Bihar, Kerala"
- Correlation: "Is sanitation correlated with stunting rates?"
- Trend: "Which districts in Rajasthan improved most since NFHS-4?" (state-baseline
  comparison, disclosed as such — the underlying NFHS-4 file is state-level)

## Quick start
```bash
pip install -r requirements.txt
python -m uvicorn backend.api.main:app --reload --port 8000   # terminal 1
python -m http.server 3000 --directory frontend                # terminal 2
# http://localhost:3000
```

## Running the benchmark
```bash
python -m backend.evaluation.eval_runner --model groq --n 10   # sample
python -m backend.evaluation.eval_runner --model groq          # full 200
```
Requires `GROQ_API_KEY` (or `OPENROUTER_API_KEY`) in `.env` — no Anthropic/OpenAI key
is currently configured for this project, so those code paths in `agent.py` are
implemented but untested against a real key.

## What's honestly still missing against the original project blueprint
- No cloud deployment (Cloud Run / Vercel never attempted).
- Frontend isn't Next.js.
- No Claude/GPT-4o key configured — running on free-tier Groq/OpenRouter instead.
- No DVC data versioning.
- No automated test suite with coverage metrics.
- `TECHNICAL_REPORT.md`'s load-testing and user-acceptance-testing sections in an
  earlier version were never actually run — removed rather than restated unverified.

---

**Mohammed Rayyan** | rayyan1652@gmail.com | B.Tech CSE (Data Science), NMIMS University, Hyderabad
