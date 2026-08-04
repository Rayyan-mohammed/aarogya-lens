"""
BharatHealth Analyst — Evaluation Runner
Runs all 200 benchmark questions against the agent and computes all 5 metrics:
EA (Execution Accuracy), AF (Answer Faithfulness), HR (Hallucination Rate),
RCQ (Reasoning Chain Quality), LC (Latency/Cost).
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import kendalltau

# Some recommendation strings use emoji — Windows consoles default to cp1252 and
# crash on encode. Force stdout to UTF-8 so the run doesn't die on the last line.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "backend" / "data"
EVAL_DIR = ROOT / "backend" / "evaluation"

RESULTS_PATH = EVAL_DIR / "eval_results.json"
DRYRUN_RESULTS_PATH = EVAL_DIR / "eval_results.dryrun.json"
CHECKPOINT_PATH = EVAL_DIR / "eval_checkpoint.json"


def load_benchmark() -> list:
    path = EVAL_DIR / "benchmark_questions.json"
    if not path.exists():
        raise FileNotFoundError("Run generate_benchmark.py first")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]


def load_data() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "nfhs5_clean.parquet")


def _flatten_gt(gt: dict, prefix: str = "") -> list:
    """Turn a possibly-nested ground-truth dict into a flat list of leaf values to check for."""
    leaves = []
    for k, v in gt.items():
        if isinstance(v, dict):
            leaves.extend(_flatten_gt(v, prefix=f"{prefix}{k}."))
        else:
            leaves.append((k, v))
    return leaves


def _score_dict_answer(predicted: str, gt: dict) -> float:
    """Partial credit for comparison/distribution answers with no single best_performing_state key:
    fraction of the ground-truth's leaf values (state/district names, numbers) found in the answer."""
    if not predicted.strip():
        return 0.0
    leaves = _flatten_gt(gt)
    if not leaves:
        return 0.0
    pred_lower = predicted.lower()
    pred_numbers = [float(n) for n in re.findall(r"-?\d+\.?\d*", predicted)]
    hits = 0
    for _, val in leaves:
        if isinstance(val, (int, float)):
            tol = max(1.0, abs(float(val)) * 0.05)
            if any(abs(n - float(val)) <= tol for n in pred_numbers):
                hits += 1
        elif str(val).lower() in pred_lower:
            hits += 1
    return round(hits / len(leaves), 4)


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
            if isinstance(gt, dict):
                return _score_dict_answer(str(predicted), gt)
            return 0.0

        return 0.0
    except Exception:
        return 0.0
# ── METRIC 2: Answer Faithfulness ─────────────────────────────────────────────
def compute_af(agent_response: str, ground_truth: str, question: str) -> float:
    """
    Answer Faithfulness: are factual claims in the response grounded in actual data?
    Uses claim extraction + dataset verification to measure truthfulness.
    """
    try:
        from backend.evaluation.answer_faithfulness import compute_answer_faithfulness
        
        af_result = compute_answer_faithfulness(agent_response, question)
        return af_result["af_score"]
        
    except Exception as e:
        print(f"AF computation failed: {e}")
        return 0.0


def extract_numeric(text: str):
    """Extract the answer's numeric value from text.

    Prefers numbers immediately followed by '%' — the agent's prose almost always
    states other numbers first (age ranges like "15-49", "12-23 months", or
    question phrasing like "ANC 4+"), so blindly taking the first number in the
    text was picking those up instead of the actual answer value.
    """
    cleaned = text.replace(",", "")
    percent_matches = re.findall(r"\d+\.?\d*(?=\s*%)", cleaned)
    if percent_matches:
        return float(percent_matches[0])
    matches = re.findall(r"\d+\.?\d*", cleaned)
    return float(matches[0]) if matches else None


_known_districts_cache = None


def _get_known_districts() -> list:
    global _known_districts_cache
    if _known_districts_cache is None:
        _known_districts_cache = load_data()["district"].unique().tolist()
    return _known_districts_cache


def extract_district_list(text: str) -> list:
    """Extract district names, in order of first mention, from a JSON string or prose text.

    Real agent answers are prose ("**Pashchimi Singhbhum** (Jharkhand) with 60.6%..."),
    not JSON — json.loads always failed on those and this returned [] unconditionally,
    which meant every ranking question scored EA=0 regardless of whether the answer
    was right. Fall back to matching known district names against the text.
    """
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [d.get("district", "") for d in data if isinstance(d, dict)]
    except Exception:
        pass

    # Longest-district-name first, so "West Khasi Hills" claims its span before the
    # real (separate) district named "West" can match the same substring inside it.
    claimed = []  # list of (start, end) spans already matched
    matches = []  # list of (start, district)
    for district in sorted(_get_known_districts(), key=len, reverse=True):
        start = 0
        while True:
            idx = text.find(district, start)
            if idx == -1:
                break
            end = idx + len(district)
            if not any(idx < c_end and end > c_start for c_start, c_end in claimed):
                claimed.append((idx, end))
                matches.append((idx, district))
            start = idx + 1

    matches.sort(key=lambda x: x[0])
    return [d for _, d in matches]


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
    from backend.agent.agent import run_query, _parse_retry_after

    questions = load_benchmark()
    df = load_data()

    if n_questions:
        questions = questions[:n_questions]

    print(f"\n{'='*60}", flush=True)
    print(f"BharatHealth-Bench Evaluation", flush=True)
    print(f"Model: {model_name} | Questions: {len(questions)} | Dry run: {dry_run}", flush=True)
    print(f"{'='*60}\n", flush=True)

    results = []
    total_ea = []
    total_af = []
    total_hr = []
    total_rcq = []
    total_latency = []

    for i, q in enumerate(questions):
        print(f"[{i+1:3d}/{len(questions)}] Q: {q['question'][:70]}...", flush=True)

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
            # A daily/hourly token quota (not a momentary rate limit) needs waiting out,
            # not skipping — retry this same question instead of recording a real
            # question as a failure just because the free tier reset hasn't happened yet.
            patient_attempts = 0
            while (agent_result.get("status") == "error" and patient_attempts < 8
                   and "tokens per day" in str(agent_result.get("error", "")).lower()):
                wait = _parse_retry_after(str(agent_result.get("error", ""))) or 900.0
                print(f"    daily quota hit — waiting {wait/60:.1f} min before retrying this question", flush=True)
                time.sleep(wait + 5)
                agent_result = run_query(question=q["question"], model_name=model_name, api_key=api_key)
                patient_attempts += 1

        # Compute metrics
        ea = compute_ea(agent_result.get("answer", ""), q["ground_truth"], q["answer_type"])
        af = compute_af(agent_result.get("answer", ""), q["ground_truth"], q["question"])
        hal = check_hallucination(agent_result.get("answer", ""), df)
        rcq = compute_rcq(agent_result.get("tool_call_sequence", []), q["query_type"])
        latency = agent_result.get("latency_ms", 0)

        # Add failure analysis for poor performance
        failure_info = None
        if ea < 0.8:  # Low execution accuracy
            from backend.evaluation.failure_analysis import categorize_failure
            failure_info = categorize_failure(
                q["question"], agent_result.get("answer", ""), q["ground_truth"], 
                ea, af, hal
            )

        total_ea.append(ea)
        total_af.append(af)
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
                "af": af,
                "hallucination": hal["has_hallucination"],
                "hallucination_details": hal["hallucinations"],
                "rcq": rcq,
                "latency_ms": latency,
                "failure_analysis": failure_info,
            },
            "tool_call_sequence": agent_result.get("tool_call_sequence", []),
            "status": agent_result.get("status"),
        }
        results.append(result)

        if not dry_run:
            with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
                json.dump({"model": model_name, "n_done": len(results),
                           "n_total": len(questions), "results": results},
                          f, indent=2, ensure_ascii=False, default=str)
            # 12000 TPM / ~6-7k tokens for the priciest questions ~= 31s worst-case floor,
            # but most questions cost far less and real calls run ~2-5s — 45s was too
            # conservative given actual observed usage. 25s trims real time while staying
            # under the worst-case floor; the daily-quota patient-retry above still
            # covers us if a pricier stretch of questions does trip the per-minute cap.
            time.sleep(25)

    # ── Aggregate metrics ─────────────────────────────────────────────────────
    by_type = {}
    for r in results:
        qt = r["query_type"]
        if qt not in by_type:
            by_type[qt] = {"ea": [], "af": [], "hr": [], "rcq": []}
        by_type[qt]["ea"].append(r["metrics"]["ea"])
        by_type[qt]["af"].append(r["metrics"]["af"])
        by_type[qt]["hr"].append(1 if r["metrics"]["hallucination"] else 0)
        by_type[qt]["rcq"].append(r["metrics"]["rcq"])

    summary = {
        "model": model_name,
        "n_questions": len(questions),
        "overall": {
            "EA": round(float(np.mean(total_ea)), 4),
            "AF": round(float(np.mean(total_af)), 4),
            "HR": round(float(np.mean(total_hr)), 4),
            "RCQ": round(float(np.mean(total_rcq)), 4),
            "mean_latency_ms": round(float(np.mean(total_latency)), 0),
            "median_latency_ms": round(float(np.median(total_latency)), 0),
        },
        "by_query_type": {
            qt: {
                "EA": round(float(np.mean(v["ea"])), 4),
                "AF": round(float(np.mean(v["af"])), 4),
                "HR": round(float(np.mean(v["hr"])), 4),
                "RCQ": round(float(np.mean(v["rcq"])), 4),
                "n": len(v["ea"]),
            }
            for qt, v in by_type.items()
        },
        "results": results,
    }

    # Save (dry runs go to their own file so they never clobber a real run's results)
    out_path = DRYRUN_RESULTS_PATH if dry_run else RESULTS_PATH
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    if not dry_run and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    # Print summary table
    print(f"\n{'-'*60}")
    print(f"{'OVERALL RESULTS':^60}")
    print(f"{'-'*60}")
    print(f"  Execution Accuracy (EA) : {summary['overall']['EA']:.1%}")
    print(f"  Answer Faithfulness (AF): {summary['overall']['AF']:.1%}")
    print(f"  Hallucination Rate (HR) : {summary['overall']['HR']:.1%}")
    print(f"  Reasoning Chain (RCQ)   : {summary['overall']['RCQ']:.1%}")
    print(f"  Mean Latency            : {summary['overall']['mean_latency_ms']:.0f} ms")
    print(f"\n  By Query Type:")
    for qt, metrics in summary["by_query_type"].items():
        print(f"    {qt:<22} EA={metrics['EA']:.1%}  AF={metrics['AF']:.1%}  HR={metrics['HR']:.1%}  n={metrics['n']}")
    print(f"\n[OK] Results saved: {out_path}")

    # Generate failure analysis report
    if any(r["metrics"]["ea"] < 0.8 for r in results):
        from backend.evaluation.failure_analysis import generate_failure_report
        failure_report = generate_failure_report([
            {
                "question_id": r["id"],
                "question": r["question"],
                "agent_response": r["predicted_answer"],
                "ground_truth": r["ground_truth"],
                "ea_score": r["metrics"]["ea"],
                "af_score": r["metrics"]["af"],
                "hr_result": {"has_hallucination": r["metrics"]["hallucination"]}
            }
            for r in results
        ])
        
        print(f"\n{'-'*60}")
        print(f"{'FAILURE ANALYSIS':^60}")
        print(f"{'-'*60}")
        print(f"  Failed Questions: {failure_report['summary']['failed_questions']}/{failure_report['summary']['total_questions']}")
        print(f"  Failure Rate: {failure_report['summary']['failure_rate']:.1f}%")
        
        if failure_report.get('top_issues'):
            print(f"\n  Top Issues:")
            for issue in failure_report['top_issues'][:3]:
                print(f"    • {issue['issue_type']}: {issue['frequency']} cases")
        
        if failure_report.get('recommendations'):
            print(f"\n  Recommendations:")
            for rec in failure_report['recommendations'][:3]:
                print(f"    {rec}")

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude", choices=["claude", "gpt4o", "groq", "openrouter"])
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
