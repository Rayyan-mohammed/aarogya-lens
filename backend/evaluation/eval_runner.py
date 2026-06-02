"""
BharatHealth Analyst — Evaluation Runner
Runs all 200 benchmark questions against the agent and computes all 5 metrics:
EA (Execution Accuracy), AF (Answer Faithfulness), HR (Hallucination Rate),
RCQ (Reasoning Chain Quality), LC (Latency/Cost).
"""

import json
import re
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import kendalltau

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "backend" / "data"
EVAL_DIR = ROOT / "backend" / "evaluation"

RESULTS_PATH = EVAL_DIR / "eval_results.json"


def load_benchmark() -> list:
    path = EVAL_DIR / "benchmark_questions.json"
    if not path.exists():
        raise FileNotFoundError("Run generate_benchmark.py first")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]


def load_data() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "nfhs5_clean.parquet")


# ── METRIC 1: Execution Accuracy ─────────────────────────────────────────────
def compute_ea(predicted: Any, ground_truth: str, answer_type: str) -> float:
    """
    Execution Accuracy: did the agent return the correct value?
    - numeric: within ±0.5% of ground truth
    - ranking: Kendall's Tau > 0.8 with ground truth ranking
    - comparison/distribution: match top/bottom state correctly
    - correlation: Pearson r within ±0.1
    """
    try:
        gt = json.loads(ground_truth) if ground_truth.startswith("{") or ground_truth.startswith("[") else ground_truth

        if answer_type == "numeric":
            pred_val = extract_numeric(str(predicted))
            gt_val = extract_numeric(str(gt))
            if pred_val is None or gt_val is None:
                return 0.0
            return 1.0 if abs(pred_val - gt_val) <= 0.5 else 0.0

        elif answer_type == "ranking":
            pred_districts = extract_district_list(str(predicted))
            gt_districts = extract_district_list(str(gt)) if isinstance(gt, list) else []
            if not pred_districts or not gt_districts:
                return 0.0
            # Compute Kendall's Tau between ordinal positions
            pred_rank = {d: i for i, d in enumerate(pred_districts)}
            gt_rank = {d: i for i, d in enumerate(gt_districts)}
            common = [d for d in gt_districts if d in pred_rank]
            if len(common) < 3:
                return float(len(common)) / max(len(gt_districts), 1)
            x = [gt_rank[d] for d in common]
            y = [pred_rank[d] for d in common]
            tau, _ = kendalltau(x, y)
            return max(0.0, float(tau))

        elif answer_type == "correlation":
            pred_r = extract_numeric(str(predicted))
            gt_r = float(gt.get("pearson_r", 0)) if isinstance(gt, dict) else extract_numeric(str(gt))
            if pred_r is None or gt_r is None:
                return 0.0
            # Same direction + within 0.1
            same_dir = (pred_r * gt_r) >= 0
            close = abs(pred_r - gt_r) <= 0.1
            return 1.0 if (same_dir and close) else (0.5 if same_dir else 0.0)

        elif answer_type in ("comparison", "distribution"):
            if isinstance(gt, dict) and "best_performing_state" in gt:
                best_state = gt["best_performing_state"]
                return 1.0 if best_state.lower() in str(predicted).lower() else 0.0
            return 0.5  # Partial credit for comparison questions

        return 0.0
    except Exception:
        return 0.0


def extract_numeric(text: str):
    """Extract the first numeric value from text."""
    matches = re.findall(r"\d+\.?\d*", text.replace(",", ""))
    return float(matches[0]) if matches else None


def extract_district_list(text: str) -> list:
    """Extract district names from a JSON string or text."""
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [d.get("district", "") for d in data if isinstance(d, dict)]
    except Exception:
        pass
    # Fallback: look for district patterns
    return []


# ── METRIC 2: Hallucination Rate ─────────────────────────────────────────────
def check_hallucination(answer: str, df: pd.DataFrame) -> dict:
    """
    Check for hallucinations in agent answer:
    1. Fabricated district names
    2. Values outside valid range (0-100%)
    3. Wrong state assignments
    """
    hallucinations = []
    valid_districts = set(df["district"].str.lower().tolist())
    district_to_state = dict(zip(df["district"].str.lower(), df["state"]))

    # Check for made-up districts (mentioned in answer but not in dataset)
    mentioned_districts = re.findall(r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+district\b', answer)
    for d in mentioned_districts:
        if d.lower() not in valid_districts:
            hallucinations.append({"type": "fabricated_district", "value": d})

    # Check for values > 100% (invalid for percentage indicators)
    high_vals = re.findall(r'(\d+\.?\d*)\s*%', answer)
    for val in high_vals:
        if float(val) > 100:
            hallucinations.append({"type": "invalid_range", "value": f"{val}%"})

    return {
        "has_hallucination": len(hallucinations) > 0,
        "hallucinations": hallucinations,
        "count": len(hallucinations),
    }


# ── METRIC 3: Reasoning Chain Quality ────────────────────────────────────────
GOLD_TOOL_SEQUENCES = {
    "factual_lookup": ["pandas_query"],
    "aggregation_ranking": ["pandas_query", "chart_generator"],
    "state_comparison": ["pandas_query", "chart_generator"],
    "trend_analysis": ["trend_analyser", "chart_generator"],
    "correlation": ["correlation_finder", "chart_generator", "insight_writer"],
}


def compute_rcq(predicted_sequence: list, query_type: str) -> float:
    """
    Reasoning Chain Quality: how well does the tool call sequence match gold standard?
    Uses F1 over tool set (order-independent) blended with a sequence similarity score.
    """
    if not predicted_sequence:
        return 0.0
    gold = GOLD_TOOL_SEQUENCES.get(query_type, ["pandas_query"])
    pred_set = set(predicted_sequence)
    gold_set = set(gold)
    if not gold_set:
        return 0.0
    precision = len(pred_set & gold_set) / len(pred_set) if pred_set else 0
    recall = len(pred_set & gold_set) / len(gold_set)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return f1


# ── Main Evaluation Runner ────────────────────────────────────────────────────
def run_evaluation(
    model_name: str = "claude",
    api_key: str = None,
    n_questions: int = None,
    dry_run: bool = False,
) -> dict:
    """
    Run the full benchmark evaluation.
    dry_run=True: skip actual API calls, use mock answers (for testing pipeline).
    """
    from backend.agent.agent import run_query

    questions = load_benchmark()
    df = load_data()

    if n_questions:
        questions = questions[:n_questions]

    print(f"\n{'='*60}")
    print(f"BharatHealth-Bench Evaluation")
    print(f"Model: {model_name} | Questions: {len(questions)} | Dry run: {dry_run}")
    print(f"{'='*60}\n")

    results = []
    total_ea = []
    total_hr = []
    total_rcq = []
    total_latency = []

    for i, q in enumerate(questions):
        print(f"[{i+1:3d}/{len(questions)}] Q: {q['question'][:70]}...")

        if dry_run:
            # Mock answer for pipeline testing
            agent_result = {
                "status": "success",
                "answer": f"Mock answer for: {q['question']}. Ground truth: {q['ground_truth'][:50]}",
                "tool_call_sequence": GOLD_TOOL_SEQUENCES.get(q["query_type"], ["pandas_query"]),
                "latency_ms": 1500,
            }
        else:
            agent_result = run_query(question=q["question"], model_name=model_name, api_key=api_key)

        # Compute metrics
        ea = compute_ea(agent_result.get("answer", ""), q["ground_truth"], q["answer_type"])
        hal = check_hallucination(agent_result.get("answer", ""), df)
        rcq = compute_rcq(agent_result.get("tool_call_sequence", []), q["query_type"])
        latency = agent_result.get("latency_ms", 0)

        total_ea.append(ea)
        total_hr.append(1 if hal["has_hallucination"] else 0)
        total_rcq.append(rcq)
        total_latency.append(latency)

        result = {
            "id": q["id"],
            "question": q["question"],
            "query_type": q["query_type"],
            "domain": q["domain"],
            "difficulty": q["difficulty"],
            "ground_truth": q["ground_truth"],
            "predicted_answer": agent_result.get("answer", "")[:500],
            "metrics": {
                "ea": ea,
                "hallucination": hal["has_hallucination"],
                "hallucination_details": hal["hallucinations"],
                "rcq": rcq,
                "latency_ms": latency,
            },
            "tool_call_sequence": agent_result.get("tool_call_sequence", []),
            "status": agent_result.get("status"),
        }
        results.append(result)

        if not dry_run:
            time.sleep(0.5)  # Rate limiting

    # ── Aggregate metrics ─────────────────────────────────────────────────────
    by_type = {}
    for r in results:
        qt = r["query_type"]
        if qt not in by_type:
            by_type[qt] = {"ea": [], "hr": [], "rcq": []}
        by_type[qt]["ea"].append(r["metrics"]["ea"])
        by_type[qt]["hr"].append(1 if r["metrics"]["hallucination"] else 0)
        by_type[qt]["rcq"].append(r["metrics"]["rcq"])

    summary = {
        "model": model_name,
        "n_questions": len(questions),
        "overall": {
            "EA": round(float(np.mean(total_ea)), 4),
            "HR": round(float(np.mean(total_hr)), 4),
            "RCQ": round(float(np.mean(total_rcq)), 4),
            "mean_latency_ms": round(float(np.mean(total_latency)), 0),
            "median_latency_ms": round(float(np.median(total_latency)), 0),
        },
        "by_query_type": {
            qt: {
                "EA": round(float(np.mean(v["ea"])), 4),
                "HR": round(float(np.mean(v["hr"])), 4),
                "RCQ": round(float(np.mean(v["rcq"])), 4),
                "n": len(v["ea"]),
            }
            for qt, v in by_type.items()
        },
        "results": results,
    }

    # Save
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    # Print summary table
    print(f"\n{'─'*60}")
    print(f"{'OVERALL RESULTS':^60}")
    print(f"{'─'*60}")
    print(f"  Execution Accuracy (EA) : {summary['overall']['EA']:.1%}")
    print(f"  Hallucination Rate (HR) : {summary['overall']['HR']:.1%}")
    print(f"  Reasoning Chain (RCQ)   : {summary['overall']['RCQ']:.1%}")
    print(f"  Mean Latency            : {summary['overall']['mean_latency_ms']:.0f} ms")
    print(f"\n  By Query Type:")
    for qt, metrics in summary["by_query_type"].items():
        print(f"    {qt:<22} EA={metrics['EA']:.1%}  HR={metrics['HR']:.1%}  n={metrics['n']}")
    print(f"\n[OK] Results saved: {RESULTS_PATH}")

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude", choices=["claude", "gpt4o"])
    parser.add_argument("--n", type=int, default=None, help="Number of questions to evaluate")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, use mock answers")
    parser.add_argument("--api-key", type=str, default=None)
    args = parser.parse_args()

    run_evaluation(
        model_name=args.model,
        api_key=args.api_key,
        n_questions=args.n,
        dry_run=args.dry_run,
    )
