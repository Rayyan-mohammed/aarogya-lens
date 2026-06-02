#!/usr/bin/env python3
"""
Add final 10 questions to reach exactly 200
"""

import json
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "backend" / "data" 
EVAL_DIR = ROOT / "backend" / "evaluation"

def add_final_questions():
    """Add 10 more strategic questions"""
    
    # Load data
    df = pd.read_parquet(DATA_DIR / "nfhs5_clean.parquet")
    
    with open(EVAL_DIR / "benchmark_questions.json", "r") as f:
        benchmark = json.load(f)
    
    existing_questions = benchmark["questions"]
    next_id = max(q["id"] for q in existing_questions) + 1
    
    # Add 10 high-quality questions covering important scenarios
    final_questions = [
        {
            "id": next_id,
            "question": "What is the national average stunting rate across all districts?",
            "ground_truth": f"{df['stunting_pct'].mean():.1f}%",
            "query_type": "aggregation_ranking",
            "domain": "child_nutrition", 
            "difficulty": "easy",
            "answer_type": "numeric",
            "gold_pandas_code": "result = df['stunting_pct'].mean()"
        },
        {
            "id": next_id + 1,
            "question": "Which state has the highest average institutional delivery rate?",
            "ground_truth": df.groupby('state')['institutional_delivery_pct'].mean().idxmax(),
            "query_type": "aggregation_ranking",
            "domain": "maternal_health",
            "difficulty": "medium", 
            "answer_type": "categorical",
            "gold_pandas_code": "result = df.groupby('state')['institutional_delivery_pct'].mean().idxmax()"
        },
        {
            "id": next_id + 2, 
            "question": "How many districts have stunting rate above 40%?",
            "ground_truth": str(len(df[df['stunting_pct'] > 40])),
            "query_type": "aggregation_ranking",
            "domain": "child_nutrition",
            "difficulty": "medium",
            "answer_type": "numeric", 
            "gold_pandas_code": "result = len(df[df['stunting_pct'] > 40])"
        },
        {
            "id": next_id + 3,
            "question": "What is the median anaemia rate in children across all districts?",
            "ground_truth": f"{df['anaemia_children_pct'].median():.1f}%",
            "query_type": "aggregation_ranking",
            "domain": "anaemia",
            "difficulty": "medium",
            "answer_type": "numeric",
            "gold_pandas_code": "result = df['anaemia_children_pct'].median()"
        },
        {
            "id": next_id + 4,
            "question": "What is the average wasting rate in Uttar Pradesh?",
            "ground_truth": f"{df[df['state'] == 'Uttar Pradesh']['wasting_pct'].mean():.1f}%",
            "query_type": "state_comparison", 
            "domain": "child_nutrition",
            "difficulty": "medium",
            "answer_type": "numeric",
            "gold_pandas_code": "result = df[df['state'] == 'Uttar Pradesh']['wasting_pct'].mean()"
        },
        {
            "id": next_id + 5,
            "question": "Is vaccination coverage positively correlated with institutional delivery rates?",
            "ground_truth": f"Correlation: {df[['fully_vaccinated_recall_pct', 'institutional_delivery_pct']].corr().iloc[0,1]:.3f}",
            "query_type": "correlation",
            "domain": "vaccination_vs_maternal_health",
            "difficulty": "hard",
            "answer_type": "correlation",
            "gold_pandas_code": "result = df[['fully_vaccinated_recall_pct', 'institutional_delivery_pct']].corr().iloc[0,1]"
        },
        {
            "id": next_id + 6,
            "question": "What percentage of districts have clean water access above 90%?",
            "ground_truth": f"{(len(df[df['clean_water_access_pct'] > 90]) / len(df) * 100):.1f}%",
            "query_type": "aggregation_ranking",
            "domain": "sanitation",
            "difficulty": "medium", 
            "answer_type": "numeric",
            "gold_pandas_code": "result = len(df[df['clean_water_access_pct'] > 90]) / len(df) * 100"
        },
        {
            "id": next_id + 7,
            "question": "Compare women's literacy rates between Kerala and Bihar",
            "ground_truth": [
                f"Kerala: {df[df['state'] == 'Kerala']['women_literacy_pct'].mean():.1f}%",
                f"Bihar: {df[df['state'] == 'Bihar']['women_literacy_pct'].mean():.1f}%"
            ],
            "query_type": "state_comparison",
            "domain": "women_empowerment",
            "difficulty": "medium",
            "answer_type": "comparison", 
            "gold_pandas_code": "result = df[df['state'].isin(['Kerala', 'Bihar'])].groupby('state')['women_literacy_pct'].mean().to_dict()"
        },
        {
            "id": next_id + 8,
            "question": "What is the standard deviation of stunting rates across all districts?",
            "ground_truth": f"{df['stunting_pct'].std():.2f}",
            "query_type": "aggregation_ranking",
            "domain": "child_nutrition",
            "difficulty": "hard",
            "answer_type": "numeric",
            "gold_pandas_code": "result = df['stunting_pct'].std()" 
        },
        {
            "id": next_id + 9,
            "question": "Which 3 districts have the most balanced health profile (low stunting, high vaccination, high delivery)?",
            "ground_truth": "Requires composite scoring analysis",
            "query_type": "trend_analysis", 
            "domain": "composite_health",
            "difficulty": "hard",
            "answer_type": "ranking",
            "gold_pandas_code": "df['composite_score'] = (100-df['stunting_pct']) + df['fully_vaccinated_recall_pct'] + df['institutional_delivery_pct']; result = df.nlargest(3, 'composite_score')[['district', 'state']].to_dict('records')"
        }
    ]
    
    # Add to existing questions
    all_questions = existing_questions + final_questions
    benchmark["questions"] = all_questions
    benchmark["metadata"]["total_questions"] = len(all_questions)
    
    # Save
    with open(EVAL_DIR / "benchmark_questions.json", "w") as f:
        json.dump(benchmark, f, indent=2)
    
    print(f"✅ Added {len(final_questions)} final questions")
    print(f"🎯 Total questions: {len(all_questions)}")
    print(f"🏆 Benchmark complete: 200 questions!")

if __name__ == "__main__":
    add_final_questions()