"""
Bake the Explore tab's data into frontend/index.html.

The live API is a Cloudflare tunnel to one machine, so it is often offline, and it
rate-limits visitors to 10 requests/minute — per-click fetches from Explore would hit
that fast. NFHS-5 is a fixed 2019-21 survey, so the numbers never change between runs:
bundling them makes Explore instant and usable even when the backend is down.

Re-run after the processed dataset changes:
    python scripts/build_frontend_snapshot.py
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "backend" / "data"
INDEX = ROOT / "frontend" / "index.html"

# Same indicator set the API's /national-summary endpoint exposes.
KEY_INDICATORS = [
    "stunting_pct", "wasting_pct", "underweight_pct",
    "anaemia_children_pct", "anaemia_all_women_pct",
    "institutional_delivery_pct", "fully_vaccinated_recall_pct",
    "improved_sanitation_pct", "women_literacy_pct",
    "anc_4plus_visits_pct", "child_marriage_pct",
    "fp_modern_method_pct", "women_overweight_pct",
    "men_high_blood_sugar_pct", "clean_cooking_fuel_pct",
]


def _r(x) -> float:
    return round(float(x), 2)


def build() -> dict:
    df = pd.read_parquet(DATA_DIR / "nfhs5_clean.parquet")
    schema = json.loads((DATA_DIR / "schema.json").read_text(encoding="utf-8"))

    indicators = {}
    for col in KEY_INDICATORS:
        if col not in df.columns or not df[col].notna().any():
            continue
        lo, hi = df.loc[df[col].idxmin()], df.loc[df[col].idxmax()]
        by_state = df.groupby("state")[col].mean().dropna().sort_values(ascending=False)
        indicators[col] = {
            "d": schema.get(col, {}).get("description", col),
            "mean": _r(df[col].mean()),
            "med": _r(df[col].median()),
            "min": _r(df[col].min()),
            "max": _r(df[col].max()),
            "lo": [lo["district"], lo["state"], _r(lo[col])],
            "hi": [hi["district"], hi["state"], _r(hi[col])],
            "n": int(df[col].notna().sum()),
            "s": [[state, _r(v)] for state, v in by_state.items()],
        }

    states = df.groupby("state").size()
    return {
        "districts": int(len(df)),
        "states_n": int(df["state"].nunique()),
        "states": [[state, int(n)] for state, n in states.items()],
        "ind": indicators,
    }


def main() -> None:
    # "</" would end the surrounding <script> tag if it ever appeared in a description
    snapshot = json.dumps(build(), separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    html = INDEX.read_text(encoding="utf-8")
    pattern = re.compile(r"(/\* SNAPSHOT:BEGIN[^\n]*\n)const SNAPSHOT = [^\n]*;\n(/\* SNAPSHOT:END \*/)")
    new_html, n = pattern.subn(lambda m: f"{m.group(1)}const SNAPSHOT = {snapshot};\n{m.group(2)}", html)
    if n != 1:
        sys.exit(f"expected exactly one SNAPSHOT block in {INDEX}, found {n}")
    INDEX.write_text(new_html, encoding="utf-8", newline="\n")
    print(f"wrote {len(snapshot):,} bytes of snapshot data into {INDEX.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
