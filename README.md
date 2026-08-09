# BharatHealth Analyst 🏥

**A natural-language LLM agent over India's NFHS-5 district health data.**

*Mohammed Rayyan | B.Tech CSE (Data Science), NMIMS University, Hyderabad*

This README replaces an earlier version that claimed "90% accuracy, 0% hallucination
rate, 100% reasoning quality" and a "50 concurrent users, 23.8 req/s" load test as
achieved results. None of that was real — the benchmark numbers traced back to a single
hardcoded mock answer, and the load test was never run. Below is only what has actually
been built and verified. See [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md) for the
fuller, continuously-updated status.

---

## What's real right now

| Component | Status |
|---|---|
| **Data Pipeline** | 706 districts × 448 columns. Real NFHS-4 (2015-16) state-level trend data merged for 62 indicators, missing NFHS-5 values fallback-filled (2,286 cells, each flagged `_is_imputed`). `schema.json` verified byte-for-byte in sync with the data. |
| **Vector Database** | ChromaDB, 706 district summaries embedded (`all-MiniLM-L6-v2`, no API key needed). |
| **AI Agent** | 7 tools (`semantic_search`, `pandas_query`, `sql_query`, `chart_generator`, `insight_writer`, `trend_analyser`, `correlation_finder`) via a LangChain/LangGraph ReAct agent — verified end-to-end against a real LLM (Groq). |
| **API Backend** | 11 FastAPI endpoints, rate limiting + request logging middleware, 93% test coverage. |
| **Frontend** | Two, both real: a single-page HTML/JS UI (deployed at [rayyan-mohammed.github.io/aarogya-lens](https://rayyan-mohammed.github.io/aarogya-lens/)), and a Next.js 14 App Router rewrite in `frontend-nextjs/` (builds and runs; not yet deployed). |
| **Evaluation Harness** | 200-question benchmark, ground truth computed programmatically, 5 metrics implemented in real code. Currently mid-run — see below. |
| **Automated Tests** | 63 pytest tests, all passing, across the data pipeline, all 7 tools, and every API endpoint. Coverage: `tools.py` 72%, `main.py` 93%, `eval_runner.py` 49% (the untested part is the LLM-calling orchestration loop, which needs a live run to exercise). |
| **Deployment** | Docker builds and runs locally. Frontend live on GitHub Pages. API not yet publicly deployed — free-tier hosts (Render, Hugging Face Spaces, Vercel) each hit a real blocker (billing requirement or a hard function-size limit); next step is a self-hosted VM. |
| **Data Versioning** | DVC configured (`dvc.yaml`, local remote) for the processed data files and vector store. Honest caveat: the pipeline stages reference a `backend/data/raw/` directory and CLI flags on `pipeline.py` that don't currently exist, so `dvc repro` won't run clean from scratch yet — versioning of already-generated outputs works, the from-scratch pipeline replay doesn't. |

## Benchmark status

BharatHealth-Bench: 200 questions across 5 query types (factual lookup 59, aggregation/
ranking 52, state comparison 30, trend analysis 38, correlation 21) and 6 health domains,
with ground truth computed directly from the dataset. All 5 metrics (EA, AF, HR, RCQ, LC)
are implemented in real code — several scoring bugs were found and fixed by running it
against live model output (see [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md) for the list).

The run itself is genuinely rate-limited by Groq's free tier: **100,000 tokens/day**, and
at ~6,000+ tokens per question, 200 questions need roughly 12x that daily budget. The
runner waits out the daily reset and retries rather than giving up, and checkpoints
after every question — but a full run realistically takes days, not one sitting, and it
restarts from question 1 if the host machine sleeps mid-run (no resume yet). Final
EA/AF/HR/RCQ numbers will be added here once a run completes.

## Quick start

```bash
pip install -r requirements.txt

# backend
python -m uvicorn backend.api.main:app --reload --port 8000

# original frontend (new terminal)
python -m http.server 3000 --directory frontend

# or the Next.js frontend (new terminal)
cd frontend-nextjs && npm install && npm run dev
```

Needs `GROQ_API_KEY` or `OPENROUTER_API_KEY` in `.env` — no Anthropic/OpenAI key is
configured for this project, so those code paths in `agent.py` exist but are untested
against a real key.

```bash
# run the test suite
pytest

# run a small sample of the benchmark
python -m backend.evaluation.eval_runner --model groq --n 5
```

## Architecture

```
Data Layer                Agent Layer              API Layer
NFHS-5 + NFHS-4      ->   LangGraph ReAct     ->   FastAPI, 11 endpoints
706 × 448 columns          7 tools                  rate limiting
ChromaDB index              Groq / OpenRouter        request logging
```

- **Sandboxed code execution**: `pandas_query` runs LLM-generated pandas code in a
  restricted `exec()` namespace with a whitelisted globals dict and a forbidden-operation
  substring filter (blocks `import`, `open(`, `__`, `os.`, `sys.`, `subprocess`). This is
  a custom implementation, not the `RestrictedPython` library.
- **Multi-provider LLM support**: the agent can be pointed at Claude, GPT-4o, Groq, or
  OpenRouter by name — this is manual provider *selection*, not an automatic fallback
  chain. Only Groq and OpenRouter have been tested against real keys.

## Query types the agent handles

- Factual: *"What is the stunting rate in Kerala?"*
- Ranking: *"Which 10 districts have the worst child anaemia?"*
- Comparison: *"Compare vaccination rates across UP, Bihar, Kerala"*
- Correlation: *"Is sanitation correlated with stunting rates?"*
- Trend: *"Which districts in Rajasthan improved most since NFHS-4?"* (state-baseline
  comparison, disclosed as such — the source NFHS-4 file is state-level, not district-level)

## Project structure

```
aarogya-lens/
├── backend/
│   ├── agent/agent.py                  # LangGraph ReAct agent + system prompt
│   ├── agent/tools/tools.py            # 7 tools
│   ├── api/main.py                     # FastAPI app (11 endpoints)
│   ├── api/middleware.py               # rate limiting + request logging
│   ├── data/nfhs4_integration.py       # real NFHS-4 trend merge + fallback fill
│   ├── data/pipeline.py                # NFHS-5 cleaning + schema generation
│   ├── data/*.parquet, schema.json     # processed dataset (DVC-tracked)
│   ├── evaluation/eval_runner.py       # benchmark runner, 5 metrics
│   ├── evaluation/benchmark_questions.json
│   └── vector_store/                   # ChromaDB build + index
├── frontend/index.html                 # original single-page UI (deployed)
├── frontend-nextjs/                    # Next.js 14 rewrite (builds, not deployed)
├── tests/                              # 63 pytest tests
├── dvc.yaml, .dvc/                     # data versioning (partially wired, see above)
├── Dockerfile, docker-compose.yml      # verified locally
└── COMPLETION_SUMMARY.md               # up-to-date honest status
```

## Known limitations

- No Anthropic/OpenAI key configured — results reflect free-tier Groq, not the models
  the original project blueprint specified as primary.
- NFHS-4 trend data is a state-level approximation, not a true district-level comparison,
  because that's what the source file contains.
- No public API deployment yet (see the Deployment row above).
- The DVC pipeline doesn't `repro` cleanly from scratch (see the Data Versioning row above).
- Benchmark numbers aren't final — the run is still in progress.

---

**Mohammed Rayyan** — rayyan1652@gmail.com — B.Tech CSE (Data Science), NMIMS University, Hyderabad
