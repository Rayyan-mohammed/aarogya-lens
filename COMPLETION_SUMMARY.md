# BharatHealth Analyst — Status Summary

*Mohammed Rayyan | NMIMS University*

This replaces an earlier version of this file that claimed "100% complete" and
"90% EA, 0% HR" — those numbers were never produced by an actual benchmark run
(the only saved result at the time was a 1-question dry run with a hardcoded mock
answer). This version only states things that have been verified.

## What's real right now

| Component | Status |
|---|---|
| Data Pipeline | 706 districts x 324 columns, real NFHS-4 (2015-16) trend data merged in for 62 indicators (state-level baseline, documented as such — the raw NFHS-4 file here is state-level, not district-level) |
| Vector Database | ChromaDB, 706 district summaries embedded, verified live |
| AI Agent | 7 tools (semantic_search, pandas_query, sql_query, chart_generator, insight_writer, trend_analyser, correlation_finder), verified working end-to-end against a real LLM |
| API Backend | 10 FastAPI endpoints, rate limiting + request logging middleware, verified working in a built Docker container |
| Frontend | Single-page vanilla JS/HTML UI (not the Next.js the original blueprint specified) |
| Evaluation Framework | 200-question benchmark with programmatic ground truth; EA/AF/HR/RCQ/latency metrics computed by real code (not mocked) |
| Deployment | Dockerfile + docker-compose built and run locally, `/health` verified inside the container. GCP Cloud Run / Vercel deployment has **not** been done. |

## Benchmark results

The 200-question benchmark has been run against `llama-3.3-70b-versatile` (Groq free
tier — no Anthropic/OpenAI key is configured in this project). Three real bugs in the
scoring code were found and fixed first (they were making the agent look far worse than
it is): `extract_numeric` was grabbing the first number anywhere in an answer's text
(e.g. "15" from "aged 15-49" instead of the real answer), `extract_district_list`
returned nothing for any prose answer so every ranking question scored 0% regardless of
correctness, and `correlation_finder` was returning all 706 districts as scatter data,
which alone pushed one request to ~31,000 tokens.

*[Real EA / AF / HR / RCQ / latency numbers go here once the full run finishes —
see `backend/evaluation/eval_results.json` for the current numbers.]*

## Known gaps against the original blueprint

- No Anthropic or OpenAI API key configured — the agent runs on Groq/OpenRouter free
  tiers, not the Claude Sonnet / GPT-4o the blueprint specified as primary.
- Frontend is not Next.js.
- Nothing is deployed to a public URL.
- No DVC data versioning.
- `TECHNICAL_REPORT.md` and `SUBMISSION_PACKAGE.md` have not yet been checked for the
  same kind of unverified claims this file had — treat their numbers as unverified
  until reviewed the same way this file was.
