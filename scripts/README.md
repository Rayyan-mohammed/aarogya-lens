# scripts/

Manual demo and smoke-test scripts — run by hand, not part of the automated suite.
The real, CI-style tests are in [`tests/`](../tests/) (63 pytest tests, run with `pytest`
from the repo root).

| Script | What it does |
|---|---|
| `demo.py` | Runs a handful of real queries against a running API and prints the results. |
| `quick_demo.py` | Prints dataset stats and a few sample rows directly (no API needed). |
| `final_system_check.py` | End-to-end sanity check: data, tools, API, frontend, eval framework, docs. |
| `test_tools.py`, `test_sql_tool.py`, `test_new_features.py`, `test_query.py` | Ad hoc scripts exercising specific tools/endpoints directly — predate the real `tests/` suite. |
| `add_final_questions.py`, `generate_remaining_questions.py` | One-off scripts used to build `backend/evaluation/benchmark_questions.json` up to 200 questions. `generate_remaining_questions.py` picks districts/domains with `random.choice()` (seeded), so re-running it does not reproduce the committed question set unless you also keep whatever it started from. |

All of these import from `backend/`, so run them from the repo root:

```bash
python scripts/demo.py
python scripts/quick_demo.py
python scripts/final_system_check.py
```
