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
(`/health` returns the full 706x324 dataset from inside the container). `.dockerignore`
excludes the raw `dataset/` CSVs, local logs, and eval results from the image.

Note: the image is large (~1.5GB+) because `sentence-transformers` pulls in `torch`.
If image size matters for a real deploy, swap the embedding step to an API-based
embedding model instead of a local `sentence-transformers` model.

---

## Cloud Deployment — not yet done

The blueprint's target architecture is GCP Cloud Run (backend) + Vercel (frontend).
**Neither has been deployed as of this writing.** The Docker image above is what you'd
push to Cloud Run's container registry; the frontend is a static file that Vercel (or
any static host) can serve directly once `API_BASE` in `frontend/index.html` is pointed
at the deployed backend URL. Treat any specific `gcloud`/`firebase` command as a sketch
to adapt, not a verified recipe — none of it has been run against a real GCP project.

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
