# Why this folder exists

The real raw data lives in `dataset/` and is DVC-tracked, but the configured DVC
remote (`.dvc/config` → `localremote`, pointing at a local `remote/` folder) only
exists on the author's own machine — it was never pushed to a reachable location,
so `dvc pull` cannot work from a GitHub Actions runner.

Rather than faking a green check on an empty dataset, or standing up a paid cloud
DVC remote just for CI, these are plain copies of the two small raw CSVs that
`backend/data/pipeline.py` and `backend/data/nfhs4_integration.py` actually read
(730 KB total). The CI workflow (`.github/workflows/tests.yml`) copies them into
`dataset/` at the start of each run and regenerates `nfhs5_clean.parquet` and
`schema.json` from scratch before running pytest — the same command a developer
runs locally, just pointed at a fixture copy of the input instead of a `dvc pull`.

If a real DVC remote gets set up later, this folder and the copy step in the
workflow can be deleted in favor of `dvc pull`.
