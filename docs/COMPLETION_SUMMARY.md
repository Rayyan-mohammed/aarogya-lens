# BharatHealth Analyst — Status Summary

*Mohammed Rayyan | NMIMS University*

This replaces an earlier version of this file that claimed "100% complete" and
"90% EA, 0% HR" — those numbers were never produced by an actual benchmark run
(the only saved result at the time was a 1-question dry run with a hardcoded mock
answer). This version only states things that have been verified.

## What's real right now

| Component | Status |
|---|---|
| Data Pipeline | 706 districts x 448 columns, real NFHS-4 (2015-16) trend data merged in for 62 indicators (state-level baseline, documented as such — the raw NFHS-4 file here is state-level, not district-level), plus NFHS-4 fallback fill for 2,286 missing NFHS-5 cells (each flagged `_is_imputed`) |
| Vector Database | ChromaDB, 706 district summaries embedded, verified live |
| AI Agent | 7 tools (semantic_search, pandas_query, sql_query, chart_generator, insight_writer, trend_analyser, correlation_finder), verified working end-to-end against a real LLM |
| API Backend | 11 FastAPI endpoints, rate limiting + request logging middleware, verified working in a built Docker container |
| Frontend | Two, both real: the original single-page HTML/JS UI (**deployed** at [rayyan-mohammed.github.io/aarogya-lens](https://rayyan-mohammed.github.io/aarogya-lens/)), and a Next.js 14 App Router rewrite in `frontend-nextjs/` — found it had never been built even once, fixed 8 real bugs (including an XSS-relevant one) to get it building and running; not deployed yet. |
| Evaluation Framework | 200-question benchmark with programmatic ground truth; EA/AF/HR/RCQ/latency metrics computed by real code (not mocked) |
| Automated Tests | 63 pytest tests covering the data pipeline, all 7 tools, and every API endpoint — several are regression tests for real bugs found this session. Measured coverage: `tools.py` 72%, `main.py` 93%, `eval_runner.py` 49% (the untested part is the LLM-calling loop itself) |
| Data Versioning | DVC pipeline (`dvc.yaml`) — 3 real stages, verified end to end with `dvc repro` (diffed every regenerated output against what was already on disk: byte-for-byte identical). Raw source CSVs, processed data, vector store, and benchmark questions are all DVC-tracked. `dvc status` reports clean. |
| Deployment | Dockerfile + docker-compose built and run locally, `/health` verified inside the container. Original frontend live on GitHub Pages. API not deployed yet — Render, Hugging Face Spaces, and Vercel were each tried and each hit a genuine platform wall (billing requirement, billing requirement, 250MB serverless size limit), not a config mistake. |

## Benchmark results

The 200-question benchmark has been run against `llama-3.3-70b-versatile` (Groq free
tier — no Anthropic/OpenAI key is configured in this project). Several real bugs in the
scoring code were found and fixed along the way (they were making the agent look far
worse, or in one case better, than it actually is): `extract_numeric` was grabbing the
first number anywhere in an answer's text (e.g. "15" from "aged 15-49" instead of the
real answer), `extract_district_list` returned nothing for any prose answer so every
ranking question scored 0% regardless of correctness, `correlation_finder` was returning
all 706 districts as scatter data (one request alone hit ~31,000 tokens), and
`compute_ea` was silently handing out a free 0.5 score to comparison/distribution
questions no matter what the agent answered — including a blank answer.

**A real ceiling, not a bug**: the first corrected full run came back 100% `error` status
on all 200 questions. Direct testing traced this to Groq's free tier having a **100,000
tokens/day** cap on top of the 12,000 tokens/minute limit already accounted for. At
~6,266 tokens/question, 200 questions need roughly 1.25M tokens — about 12x the daily
budget. The other four configured keys (OpenRouter, Gemini, Grok, DeepSeek) were checked
too and are each at zero or near-zero account balance right now, so Groq is the only
provider currently reachable at all.

The eval runner now waits out a daily-quota reset and retries the same question instead
of recording it as a failure (`backend/evaluation/eval_runner.py`), and checkpoints
progress after every question so a multi-day run can't lose completed work.

**Update, 2026-09 to 2026-10:** Groq was abandoned (the 100k/day token cap made it
unworkable) in favor of Gemini `gemini-3.6-flash` with multiple rotating API keys, each
with its own independent free-tier daily quota. The full 200-question run **completed**
on 2026-09-16. Four more scoring-harness bugs surfaced and were fixed afterward (missing
comparison-claim verification in the AF checker, a hallucination-checker regex that
flagged generic words like "National"/"The" as fabricated districts, a missing
negative-sign in the numeric extractor, and a ranking-scorer bug that let a repeated
district mention overwrite its correct rank). Rescored final numbers:

| Metric | Overall (200 questions) |
|---|---|
| EA | 71.1% |
| AF | 82.0% |
| HR | 5.0% |
| RCQ | 64.7% |
| Mean latency | 120s/question |

Separately, a routing gap was found in the agent's own system prompt: the purpose-built
`trend_analyser` tool was only used 2/38 times on `trend_analysis`-category questions
because the prompt only triggered it for explicit "trend"/"NFHS-4" wording, which those
questions never actually use. Fixed and re-validated live on a full, clean 38-question
re-run of that category alone: EA 54.4% → 84.5%, RCQ 37.2% → 89.2%. The other four
categories (162/200 questions) have not yet been re-run against this fix, so the 64.7%
overall RCQ above is a confirmed floor, not the final number. See
[README.md § Results](../README.md#results) for the full per-category breakdown and the
honest-scope caveats (AF still undercounts markdown-bullet-formatted answers).

## Other real bugs found and fixed this session

- `schema.json` documented 124 trend columns that were never actually created —
  the schema writer looped over all 93 candidate NFHS-4 indicators, but the merge
  itself only adds change/filled columns for the 62 that successfully matched an
  NFHS-5 column. Fixed so schema.json and the actual data are always in exact sync
  (verified: 448/448 columns, zero drift either direction, still idempotent on rerun).
- `pandas_query` had the same NaN-serialization bug already fixed in the API
  endpoints — a missing value (e.g. Thrissur's vaccination rate) came back as
  `NaN` instead of `null`, which isn't valid JSON.
- `README.md` had never been touched this whole project and still had the exact
  fabricated "90% accuracy, 0% hallucination, 100% reasoning quality" numbers plus a
  fake "50 concurrent users, 23.8 req/s" load test front and center — the highest-
  visibility file in the repo, and the last one still making those claims. Rewritten.
- The `frontend-nextjs/` app (from the "Add Next.js frontend and DVC data versioning"
  commit) had never actually been built. `npm run build` failed immediately: a broken
  HTML-escaping function with a syntax error that also did nothing useful even if it
  had compiled, `formatAnswer` trying to return JSX from inside `.replace()` (silently
  broken — JS just stringifies it), unescaped LLM output going into
  `dangerouslySetInnerHTML` (a real XSS opening), three invalid Tailwind classes,
  Plotly crashing on server-side prerender, a Plotly type error, and a corrupted
  indicator value (`'stępu'` instead of `'stunting_pct'`). All fixed; it builds and
  runs now.
- The DVC pipeline (`dvc.yaml`) referenced CLI flags on `pipeline.py`/`build_index.py`
  that don't exist and a `backend/data/raw/` directory that was never created — `dvc
  repro` would fail from scratch. Rebuilt as 3 real stages matching what the scripts
  actually do, and discovered along the way that `generate_benchmark.py` alone only
  produces 119 of the real 200 benchmark questions — the rest come from a second
  script using unseeded `random.choice()` for district/domain selection, so the full
  200-question file isn't actually regenerable byte-for-byte and is now tracked as
  data rather than a fake pipeline output. (A third script, `add_final_questions.py`,
  turned out to be unused — 119 + 81 already equals 200.)

## Known gaps against the original blueprint

- No Anthropic or OpenAI API key configured — the agent runs on Groq's free tier, the
  only one of five configured provider keys with any usable quota right now.
- A full 200-question benchmark run cannot complete in a single session on free-tier
  Groq alone — see above. It also doesn't survive the host machine sleeping/restarting
  yet (no resume from checkpoint on restart), so it has had to be restarted from
  question 1 more than once.
- Next.js frontend exists and works but isn't deployed; only the original HTML/JS UI
  is live.
- The API itself isn't deployed to a public URL yet (see Deployment above).
