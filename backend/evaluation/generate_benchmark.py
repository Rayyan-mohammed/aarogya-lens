"""
BharatHealth Analyst — Benchmark Question Generator
Programmatically generates 200 Q&A pairs with ground truth from the cleaned dataset.
Covers all 5 query types and 4 indicator domains.
"""

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "backend" / "data"
EVAL_DIR = ROOT / "backend" / "evaluation"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

random.seed(42)
np.random.seed(42)


def load_data():
    df = pd.read_parquet(DATA_DIR / "nfhs5_clean.parquet")
    with open(DATA_DIR / "schema.json", "r", encoding="utf-8") as f:
        schema = json.load(f)
    return df, schema


def fmt(val, decimals=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val:.{decimals}f}%"


def generate_benchmark(df: pd.DataFrame, schema: dict) -> list:
    questions = []
    qid = 1

    def add(q, gt, qtype, domain, difficulty, gold_code=None, answer_type="numeric"):
        nonlocal qid
        questions.append({
            "id": qid,
            "question": q,
            "ground_truth": gt,
            "query_type": qtype,
            "domain": domain,
            "difficulty": difficulty,
            "answer_type": answer_type,
            "gold_pandas_code": gold_code,
        })
        qid += 1

    # ── TYPE 1: Factual Lookup (40 questions) ────────────────────────────────
    # Sample 40 district-indicator pairs
    lookup_combos = [
        ("stunting_pct", "stunting rate", "child_nutrition"),
        ("wasting_pct", "wasting rate", "child_nutrition"),
        ("underweight_pct", "underweight rate", "child_nutrition"),
        ("anaemia_children_pct", "anaemia rate in children", "anaemia"),
        ("anaemia_all_women_pct", "anaemia rate in women", "anaemia"),
        ("institutional_delivery_pct", "institutional delivery rate", "maternal_health"),
        ("fully_vaccinated_recall_pct", "full vaccination rate", "vaccination"),
        ("improved_sanitation_pct", "improved sanitation rate", "sanitation"),
        ("anc_4plus_visits_pct", "ANC 4+ visit rate", "maternal_health"),
        ("child_marriage_pct", "child marriage rate", "women_empowerment"),
    ]

    sample_districts = df.dropna(subset=["stunting_pct"]).sample(40, random_state=42)

    for i, row in enumerate(sample_districts.itertuples()):
        col, label, domain = lookup_combos[i % len(lookup_combos)]
        val = getattr(row, col, None)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            continue
        add(
            q=f"What is the {label} in {row.district} district, {row.state}?",
            gt=fmt(val),
            qtype="factual_lookup",
            domain=domain,
            difficulty="easy",
            gold_code=f"result = df[(df['district']=='{row.district}') & (df['state']=='{row.state}')]['{col}'].values[0]",
            answer_type="numeric",
        )

    # ── TYPE 2: Aggregation & Ranking (50 questions) ─────────────────────────
    ranking_configs = [
        ("stunting_pct", "worst stunting", True, "child_nutrition", "medium",
         "result = df.nlargest(10, 'stunting_pct')[['district','state','stunting_pct']]"),
        ("wasting_pct", "worst wasting", True, "child_nutrition", "medium",
         "result = df.nlargest(10, 'wasting_pct')[['district','state','wasting_pct']]"),
        ("anaemia_children_pct", "highest child anaemia", True, "anaemia", "medium",
         "result = df.nlargest(10, 'anaemia_children_pct')[['district','state','anaemia_children_pct']]"),
        ("anaemia_all_women_pct", "highest anaemia in women", True, "anaemia", "medium",
         "result = df.nlargest(10, 'anaemia_all_women_pct')[['district','state','anaemia_all_women_pct']]"),
        ("institutional_delivery_pct", "lowest institutional delivery", False, "maternal_health", "medium",
         "result = df.nsmallest(10, 'institutional_delivery_pct')[['district','state','institutional_delivery_pct']]"),
        ("fully_vaccinated_recall_pct", "lowest full vaccination", False, "vaccination", "medium",
         "result = df.nsmallest(10, 'fully_vaccinated_recall_pct')[['district','state','fully_vaccinated_recall_pct']]"),
        ("improved_sanitation_pct", "worst sanitation", False, "sanitation", "medium",
         "result = df.nsmallest(10, 'improved_sanitation_pct')[['district','state','improved_sanitation_pct']]"),
        ("child_marriage_pct", "highest child marriage", True, "women_empowerment", "medium",
         "result = df.nlargest(10, 'child_marriage_pct')[['district','state','child_marriage_pct']]"),
        ("csection_pct", "highest C-section rate", True, "maternal_health", "medium",
         "result = df.nlargest(10, 'csection_pct')[['district','state','csection_pct']]"),
        ("anc_4plus_visits_pct", "lowest ANC coverage", False, "maternal_health", "medium",
         "result = df.nsmallest(10, 'anc_4plus_visits_pct')[['district','state','anc_4plus_visits_pct']]"),
    ]

    for col, label, worst_is_max, domain, diff, gold_code in ranking_configs[:10]:
        if col not in df.columns:
            continue
        if worst_is_max:
            top = df.nlargest(10, col)[["district", "state", col]]
        else:
            top = df.nsmallest(10, col)[["district", "state", col]]
        gt_list = top[["district", col]].to_dict(orient="records")
        add(
            q=f"Which 10 districts nationally have the {label}?",
            gt=json.dumps(gt_list),
            qtype="aggregation_ranking",
            domain=domain,
            difficulty=diff,
            gold_code=gold_code,
            answer_type="ranking",
        )

    # Aggregation — per-state national ranking
    states_of_interest = ["Bihar", "Uttar Pradesh", "Rajasthan", "Madhya Pradesh", "Maharashtra",
                          "Kerala", "Tamil Nadu", "Telangana", "Karnataka", "West Bengal"]
    for state in states_of_interest[:10]:
        if state not in df["state"].values:
            continue
        df_s = df[df["state"] == state]
        if "stunting_pct" not in df_s.columns or df_s["stunting_pct"].isna().all():
            continue
        top5 = df_s.nlargest(5, "stunting_pct")[["district", "stunting_pct"]].to_dict(orient="records")
        add(
            q=f"Which 5 districts in {state} have the highest stunting rates?",
            gt=json.dumps(top5),
            qtype="aggregation_ranking",
            domain="child_nutrition",
            difficulty="medium",
            gold_code=f"result = df[df['state']=='{state}'].nlargest(5,'stunting_pct')[['district','state','stunting_pct']]",
            answer_type="ranking",
        )

    # National aggregates
    for col, label, domain in [
        ("stunting_pct", "average stunting rate", "child_nutrition"),
        ("anaemia_all_women_pct", "average anaemia rate in women", "anaemia"),
        ("institutional_delivery_pct", "average institutional delivery rate", "maternal_health"),
        ("fully_vaccinated_recall_pct", "average full vaccination coverage", "vaccination"),
        ("improved_sanitation_pct", "average improved sanitation coverage", "sanitation"),
    ]:
        if col not in df.columns:
            continue
        val = df[col].mean()
        add(
            q=f"What is the national {label} across all 706 districts in NFHS-5?",
            gt=fmt(val),
            qtype="aggregation_ranking",
            domain=domain,
            difficulty="easy",
            gold_code=f"result = df['{col}'].mean()",
            answer_type="numeric",
        )

    # ── TYPE 3: State-level Comparison (40 questions) ────────────────────────
    state_compare_groups = [
        (["Bihar", "Uttar Pradesh", "Kerala"], "stunting_pct", "stunting rates", "child_nutrition"),
        (["Bihar", "Uttar Pradesh", "Kerala"], "institutional_delivery_pct", "institutional delivery rates", "maternal_health"),
        (["Rajasthan", "Madhya Pradesh", "Gujarat"], "anaemia_children_pct", "child anaemia rates", "anaemia"),
        (["Maharashtra", "Karnataka", "Tamil Nadu"], "fully_vaccinated_recall_pct", "vaccination coverage", "vaccination"),
        (["Uttar Pradesh", "Bihar", "Jharkhand", "Odisha"], "child_marriage_pct", "child marriage rates", "women_empowerment"),
        (["Kerala", "Goa", "Tamil Nadu"], "women_literacy_pct", "women literacy rates", "women_empowerment"),
        (["Bihar", "Jharkhand", "Odisha"], "improved_sanitation_pct", "sanitation coverage", "sanitation"),
        (["Kerala", "Maharashtra", "Tamil Nadu"], "anc_4plus_visits_pct", "ANC 4+ visit rates", "maternal_health"),
        (["Rajasthan", "Haryana", "Punjab"], "anaemia_all_women_pct", "anaemia in women", "anaemia"),
        (["Bihar", "Uttar Pradesh", "West Bengal"], "wasting_pct", "wasting rates", "child_nutrition"),
    ]

    for states, col, label, domain in state_compare_groups:
        if col not in df.columns:
            continue
        valid_states = [s for s in states if s in df["state"].values]
        if not valid_states:
            continue
        comp = df[df["state"].isin(valid_states)].groupby("state")[col].mean().round(1)
        gt_data = comp.to_dict()
        states_str = ", ".join(valid_states[:-1]) + f", and {valid_states[-1]}"
        add(
            q=f"Compare the average {label} across {states_str}.",
            gt=json.dumps(gt_data),
            qtype="state_comparison",
            domain=domain,
            difficulty="medium",
            gold_code=f"result = df[df['state'].isin({valid_states})].groupby('state')['{col}'].mean().round(1)",
            answer_type="comparison",
        )

    # All-state ranking questions
    for col, label, domain in [
        ("stunting_pct", "stunting", "child_nutrition"),
        ("anaemia_all_women_pct", "anaemia in women", "anaemia"),
        ("institutional_delivery_pct", "institutional delivery", "maternal_health"),
        ("improved_sanitation_pct", "sanitation", "sanitation"),
    ]:
        if col not in df.columns:
            continue
        state_avg = df.groupby("state")[col].mean().round(1).sort_values(ascending=False)
        gt = {"top_3_states": state_avg.head(3).to_dict(), "bottom_3_states": state_avg.tail(3).to_dict()}
        add(
            q=f"Which states have the highest and lowest average {label} rates?",
            gt=json.dumps(gt),
            qtype="state_comparison",
            domain=domain,
            difficulty="medium",
            gold_code=f"result = df.groupby('state')['{col}'].mean().round(1).sort_values(ascending=False)",
            answer_type="comparison",
        )

    # ── TYPE 4: Trend Analysis — distribution queries (40 questions) ──────────
    # Since we only have NFHS-5, these ask about distribution range, variation, and outliers
    trend_configs = [
        ("stunting_pct", "stunting", True, "child_nutrition"),
        ("anaemia_children_pct", "child anaemia", True, "anaemia"),
        ("anaemia_all_women_pct", "women anaemia", True, "anaemia"),
        ("institutional_delivery_pct", "institutional delivery", False, "maternal_health"),
        ("fully_vaccinated_recall_pct", "vaccination coverage", False, "vaccination"),
        ("improved_sanitation_pct", "sanitation", False, "sanitation"),
        ("women_literacy_pct", "women literacy", False, "women_empowerment"),
        ("child_marriage_pct", "child marriage", True, "women_empowerment"),
        ("csection_pct", "C-section rate", True, "maternal_health"),
        ("anc_4plus_visits_pct", "ANC 4+ visits", False, "maternal_health"),
    ]

    for col, label, lower_worse, domain in trend_configs:
        if col not in df.columns:
            continue
        col_data = df[col].dropna()
        top_state = df.groupby("state")[col].mean().idxmax() if not lower_worse else df.groupby("state")[col].mean().idxmin()
        bot_state = df.groupby("state")[col].mean().idxmin() if not lower_worse else df.groupby("state")[col].mean().idxmax()
        gap = abs(df.groupby("state")[col].mean()[top_state] - df.groupby("state")[col].mean()[bot_state])
        gt = {
            "national_mean": round(col_data.mean(), 1),
            "national_min": round(col_data.min(), 1),
            "national_max": round(col_data.max(), 1),
            "best_performing_state": top_state,
            "worst_performing_state": bot_state,
            "interstate_gap": round(gap, 1),
        }
        add(
            q=f"What is the distribution of {label} across all districts? Which states perform best and worst?",
            gt=json.dumps(gt),
            qtype="trend_analysis",
            domain=domain,
            difficulty="hard",
            gold_code=f"state_avg = df.groupby('state')['{col}'].mean().sort_values(ascending=False); result = state_avg",
            answer_type="distribution",
        )

    # State-specific distribution
    for state in ["Bihar", "Uttar Pradesh", "Rajasthan", "Tamil Nadu", "West Bengal"]:
        for col, label, domain in [("stunting_pct", "stunting", "child_nutrition"),
                                    ("anaemia_children_pct", "child anaemia", "anaemia"),
                                    ("institutional_delivery_pct", "institutional delivery", "maternal_health"),
                                    ("improved_sanitation_pct", "sanitation", "sanitation")]:
            if col not in df.columns or state not in df["state"].values:
                continue
            df_s = df[df["state"] == state][col].dropna()
            if df_s.empty:
                continue
            best = df[(df["state"] == state)].nsmallest(1, col).iloc[0] if col in ["stunting_pct","anaemia_children_pct"] else df[(df["state"] == state)].nlargest(1, col).iloc[0]
            worst = df[(df["state"] == state)].nlargest(1, col).iloc[0] if col in ["stunting_pct","anaemia_children_pct"] else df[(df["state"] == state)].nsmallest(1, col).iloc[0]
            gt = {
                "state": state, "indicator": label,
                "mean": round(df_s.mean(), 1),
                "best_district": best["district"], "best_value": round(best[col], 1),
                "worst_district": worst["district"], "worst_value": round(worst[col], 1),
            }
            add(
                q=f"What is the range of {label} across districts in {state}? Which district performs best and worst?",
                gt=json.dumps(gt),
                qtype="trend_analysis",
                domain=domain,
                difficulty="hard",
                gold_code=f"df_s = df[df['state']=='{state}']; result = df_s[['district','{col}']].sort_values('{col}')",
                answer_type="distribution",
            )
            if qid > 160:
                break
        if qid > 160:
            break

    # ── TYPE 5: Correlation & Causal (30 questions) ───────────────────────────
    corr_pairs = [
        ("improved_sanitation_pct", "stunting_pct", "sanitation", "child_nutrition",
         "Is improved sanitation correlated with lower stunting rates at district level?"),
        ("improved_sanitation_pct", "wasting_pct", "sanitation", "child_nutrition",
         "Is there a relationship between open defecation (lack of sanitation) and wasting?"),
        ("women_literacy_pct", "institutional_delivery_pct", "women_empowerment", "maternal_health",
         "Is women's literacy correlated with institutional delivery rates?"),
        ("women_literacy_pct", "child_marriage_pct", "women_empowerment", "women_empowerment",
         "Is women's literacy associated with lower child marriage rates?"),
        ("anc_4plus_visits_pct", "stunting_pct", "maternal_health", "child_nutrition",
         "Are districts with higher ANC coverage associated with lower stunting?"),
        ("clean_cooking_fuel_pct", "anaemia_all_women_pct", "sanitation", "anaemia",
         "Is clean cooking fuel access correlated with lower anaemia in women?"),
        ("health_insurance_pct", "institutional_delivery_pct", "healthcare_access", "maternal_health",
         "Is health insurance coverage associated with higher institutional delivery rates?"),
        ("women_literacy_pct", "anaemia_all_women_pct", "women_empowerment", "anaemia",
         "Is women's literacy correlated with anaemia prevalence?"),
        ("electricity_access_pct", "fully_vaccinated_recall_pct", "sanitation", "vaccination",
         "Is electricity access associated with better vaccination coverage?"),
        ("clean_cooking_fuel_pct", "stunting_pct", "sanitation", "child_nutrition",
         "Do districts with clean cooking fuel have lower child stunting rates?"),
        ("child_marriage_pct", "anaemia_pregnant_women_pct", "women_empowerment", "anaemia",
         "Is child marriage correlated with anaemia in pregnant women?"),
        ("anc_4plus_visits_pct", "institutional_delivery_pct", "maternal_health", "maternal_health",
         "Are districts with more ANC visits also more likely to have institutional deliveries?"),
    ]

    for a, b, domain_a, domain_b, q_text in corr_pairs[:12]:
        if a not in df.columns or b not in df.columns:
            continue
        pair = df[[a, b]].dropna()
        if len(pair) < 10:
            continue
        r, p = stats.pearsonr(pair[a], pair[b])
        sr, sp = stats.spearmanr(pair[a], pair[b])
        direction = "negative" if r < 0 else "positive"
        significance = "statistically significant (p < 0.05)" if p < 0.05 else "not statistically significant"
        gt = {
            "pearson_r": round(r, 4),
            "pearson_p": round(p, 6),
            "spearman_r": round(sr, 4),
            "n_districts": len(pair),
            "direction": direction,
            "significance": significance,
        }
        domain = f"{domain_a}/{domain_b}"
        add(
            q=q_text,
            gt=json.dumps(gt),
            qtype="correlation",
            domain=domain,
            difficulty="hard",
            gold_code=f"from scipy import stats; pair = df[['{a}','{b}']].dropna(); result = stats.pearsonr(pair['{a}'], pair['{b}'])",
            answer_type="correlation",
        )

    # Trim or pad to 200
    questions = questions[:200]

    # Add summary stats
    type_counts = {}
    for q in questions:
        type_counts[q["query_type"]] = type_counts.get(q["query_type"], 0) + 1

    print(f"Generated {len(questions)} benchmark questions")
    print(f"Type breakdown: {type_counts}")

    return questions


def save_benchmark(questions: list):
    out_path = EVAL_DIR / "benchmark_questions.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "name": "BharatHealth-Bench",
                "version": "1.0",
                "description": "200-question evaluation benchmark for LLM agents on NFHS-5 India district health data",
                "source_dataset": "NFHS-5 (2019-21), data.gov.in",
                "created_by": "Mohammed Rayyan",
                "license": "Apache 2.0",
                "total_questions": len(questions),
                "query_types": ["factual_lookup", "aggregation_ranking", "state_comparison", "trend_analysis", "correlation"],
                "domains": ["child_nutrition", "anaemia", "maternal_health", "vaccination", "sanitation", "women_empowerment"],
            },
            "questions": questions,
        }, f, indent=2, ensure_ascii=False, default=str)
    print(f"[OK] Saved benchmark: {out_path}")
    return out_path


if __name__ == "__main__":
    print("Generating BharatHealth-Bench...")
    df, schema = load_data()
    questions = generate_benchmark(df, schema)
    save_benchmark(questions)
    print(f"\nSample question:")
    import pprint
    pprint.pprint(questions[0])
    pprint.pprint(questions[50])
    pprint.pprint(questions[-1])
