# BharatHealth Analyst - Deployment Guide

## Quick Start (Local Development)

### Prerequisites
```bash
Python 3.11+
Git
```

### 1. Clone and Setup
```bash
git clone <repository-url>
cd aarogya-lens
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file with at least one LLM API key:
```bash
ANTHROPIC_API_KEY=sk-ant-...       # Claude — primary per project design
OPENAI_API_KEY=sk-...              # GPT-4o
GROQ_API_KEY=gsk_...               # Llama 3.3 70B, free tier (12000 TPM)
OPENROUTER_API_KEY=...             # Gemini 2.5 Flash via OpenRouter
```

### 3. Data Pipeline (already built, only needed if rebuilding from scratch)
```bash
python backend/data/pipeline.py             # clean NFHS-5 -> parquet + schema
python backend/data/nfhs4_integration.py    # merge real NFHS-4 state-level trend data
python backend/vector_store/build_index.py  # build ChromaDB index (downloads ~90MB embedding model)
```

### 4. Start the System
```bash
# Terminal 1
python -m uvicorn backend.api.main:app --reload --port 8000

# Terminal 2
python -m http.server 3000 --directory frontend

# API:      http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### 5. Verify
```bash
curl http://localhost:8000/health
python -m backend.evaluation.eval_runner --model groq --n 5
```

---

## Docker (verified working)

```bash
docker build -t bharathealth-backend .
docker compose up
```

`docker-compose.yml` runs two services:
- `backend` — the FastAPI app on port 8000, built from the repo's `Dockerfile`
- `frontend` — the static `frontend/index.html` served on port 3000 via `python -m http.server`

Both `Dockerfile` and `docker-compose.yml` have been built and run locally end-to-end
(`/health` returns the full 706x448 dataset from inside the container). `.dockerignore`
excludes the raw `dataset/` CSVs, local logs, and eval results from the image. The
Dockerfile binds to `$PORT` (falling back to 8000) so it also works unmodified on PaaS
hosts that inject their own port.

Note: the image is large (~1.5GB+) because `sentence-transformers` pulls in `torch`.
If image size matters for a real deploy, swap the embedding step to an API-based
embedding model instead of a local `sentence-transformers` model.

---

## Cloud Deployment

**Frontend: done.** The original `frontend/index.html` is live on GitHub Pages at
https://rayyan-mohammed.github.io/aarogya-lens/ (served from the `gh-pages` branch,
root path — GitHub auto-enabled Pages once that branch was pushed). Its `API_BASE`
still points at `localhost:8000`, so it can't reach a live backend yet.

**Backend: not yet done**, and not for lack of trying — three free-tier hosts were
attempted and each hit a real wall, not a config mistake:
- **Render**: API accepted everything (a public GitHub repo doesn't even need
  pre-authorization) but creating *any* service, free tier included, now requires a
  card on file for verification. `render.yaml` is in the repo, ready to go once that's
  sorted.
- **Hugging Face Spaces**: Docker/Gradio SDKs now require a PRO subscription even on
  cpu-basic; only static Spaces are free, which can't run a backend.
- **Vercel serverless**: hits the platform's 250MB function bundle limit before even
  counting ML dependencies — `pandas` + `numpy` + `scipy` + `plotly` alone are already
  ~267MB. Not fixable by trimming tools; the core stack itself is too big for a
  serverless function.

Next candidate: a self-hosted VM (e.g. Oracle Cloud's Always Free Ampere tier, up to
24GB RAM, no time limit) running the existing Docker image directly — no function-size
or Docker-SDK-billing constraints apply to a plain VM.

---

## What's actually implemented in the API

- **Rate limiting**: `backend/api/middleware.py` — in-memory sliding window, 10 req/min
  by default, 100 req/min with an `X-API-Key` header. Single-instance only; would need
  a shared store (Redis) behind multiple workers/instances.
- **Request logging**: same file, appends one JSON line per request to
  `backend/api/logs/requests.jsonl` (method, path, status, latency, client IP). This is
  a local stand-in for the blueprint's BigQuery/Cloud Logging analytics — swap in a real
  BigQuery client once GCP credentials exist.
- **No** Prometheus `/metrics`, Sentry, or structured JSON logging is wired up. If you
  want those, they'd need to be added — they are not currently in the codebase.

---

## Troubleshooting

**API won't start** — check the port isn't in use, `pip install -r requirements.txt` ran
clean, and `backend/data/nfhs5_clean.parquet` exists.

**ChromaDB issues** — delete `backend/vector_store/chroma_db/` and re-run
`python backend/vector_store/build_index.py`.

**LLM request too large / rate limited** — the system prompt + 7 tool schemas run
close to free-tier token-per-minute limits on smaller models. `backend/agent/agent.py`
already trims the schema summary and uses `llama-3.3-70b-versatile` (12000 TPM) rather
than `llama-3.1-8b-instant` (6000 TPM) for this reason. `run_query` retries automatically
on rate-limit errors with backoff.

---

**Prepared by Mohammed Rayyan** — rayyan1652@gmail.com
