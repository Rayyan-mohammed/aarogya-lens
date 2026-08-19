# Why this folder exists

The real raw data lives in `dataset/` and is DVC-tracked, but the configured DVC
remote (`.dvc/config` → `localremote`, pointing at a local `remote/` folder) only
exists on the author's own machine — it was never pushed to a reachable location,
so `dvc pull` cannot work from a GitHub Actions runner.

Rather than faking a green check on an empty dataset, or standing up a paid cloud
DVC remote just for CI, these are plain copies of what's actually needed:

- the two small raw CSVs that `backend/data/pipeline.py` and
  `backend/data/nfhs4_integration.py` read (730 KB total)
- `benchmark_questions.json` (107 KB) — copied as-is rather than regenerated,
  because it isn't reproducible from code in the first place (see the note in
  `dvc.yaml`: 119 of its 200 questions come from a seeded script, the rest from
  a second script using unseeded `random.choice()`)

The CI workflow (`.github/workflows/tests.yml`) copies these into place at the
start of each run and regenerates `nfhs5_clean.parquet`/`schema.json` from the
CSVs before running pytest — the same commands a developer runs locally, just
pointed at fixture copies of the inputs instead of a `dvc pull`.

If a real DVC remote gets set up later, this folder and the copy step in the
workflow can be deleted in favor of `dvc pull`.
