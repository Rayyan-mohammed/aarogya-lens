#!/usr/bin/env python3
"""
Generate the remaining 81 questions to complete the 200-question benchmark
"""

import json
import random
import pandas as pd
from pathlib import Path

# Load existing data
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "backend" / "data"
EVAL_DIR = ROOT / "backend" / "evaluation"

def load_data():
    """Load the dataset and existing benchmark"""
    df = pd.read_parquet(DATA_DIR / "nfhs5_clean.parquet")
    
    with open(EVAL_DIR / "benchmark_questions.json", "r") as f:
        benchmark = json.load(f)
    
    return df, benchmark

def generate_additional_questions(df, existing_benchmark):
    """Generate 81 more questions to reach 200 total"""
    
    existing_questions = existing_benchmark["questions"]
    next_id = max(q["id"] for q in existing_questions) + 1
    new_questions = []
    
    # Sample districts and states for variety
    districts = df['district'].unique()
    states = df['state'].unique()
    
    # Health indicators
    health_indicators = {
        'child_nutrition': ['stunting_pct', 'wasting_pct', 'underweight_pct'],
        'anaemia': ['anaemia_children_pct', 'anaemia_women_pct'],
        'maternal_health': ['institutional_delivery_pct', 'anc_4plus_visits_pct', 'csection_pct'],
        'vaccination': ['fully_vaccinated_recall_pct', 'bcg_pct', 'measles_pct'],
        'sanitation': ['improved_sanitation_pct', 'clean_water_access_pct'],
        'women_empowerment': ['women_literacy_pct', 'women_10yr_school_pct']
    }
    
    # Generate different types of questions
    questions_per_type = {
        'factual_lookup': 20,
        'aggregation_ranking': 25, 
        'state_comparison': 15,
        'trend_analysis': 10,
        'correlation': 11
    }
    
    current_id = next_id
    
    # 1. Factual lookup questions
    for i in range(questions_per_type['factual_lookup']):
        district = random.choice(districts)
        state = df[df['district'] == district]['state'].iloc[0]
        domain = random.choice(list(health_indicators.keys()))
        indicator = random.choice(health_indicators[domain])
        
        if indicator in df.columns:
            try:
                value = df[(df['district'] == district) & (df['state'] == state)][indicator].iloc[0]
                if pd.notna(value):
                    new_questions.append({
                        "id": current_id,
                        "question": f"What is the {indicator.replace('_', ' ')} in {district} district, {state}?",
                        "ground_truth": f"{value:.1f}%" if isinstance(value, (int, float)) else str(value),
                        "query_type": "factual_lookup",
                        "domain": domain,
                        "difficulty": "easy",
                        "answer_type": "numeric",
                        "gold_pandas_code": f"result = df[(df['district']=='{district}') & (df['state']=='{state}')]['{indicator}'].values[0]"
                    })
                    current_id += 1
            except:
                continue
    
    # 2. Aggregation and ranking questions
    for i in range(questions_per_type['aggregation_ranking']):
        domain = random.choice(list(health_indicators.keys()))
        indicator = random.choice(health_indicators[domain])
        ranking_type = random.choice(['highest', 'lowest'])
        top_n = random.choice([5, 10, 15])
        
        if indicator in df.columns:
            if ranking_type == 'highest':
                top_districts = df.nlargest(top_n, indicator)[['district', 'state', indicator]]
                question = f"Which {top_n} districts have the highest {indicator.replace('_', ' ')} nationally?"
            else:
                top_districts = df.nsmallest(top_n, indicator)[['district', 'state', indicator]]
                question = f"Which {top_n} districts have the lowest {indicator.replace('_', ' ')} nationally?"
            
            ground_truth = [f"{row['district']}, {row['state']}" for _, row in top_districts.iterrows()]
            
            new_questions.append({
                "id": current_id,
                "question": question,
                "ground_truth": ground_truth[:5],  # Just top 5 for ground truth
                "query_type": "aggregation_ranking", 
                "domain": domain,
                "difficulty": "medium",
                "answer_type": "ranking",
                "gold_pandas_code": f"result = df.n{'largest' if ranking_type == 'highest' else 'smallest'}({top_n}, '{indicator}')[['district', 'state', '{indicator}']].to_dict('records')"
            })
            current_id += 1
    
    # 3. State comparison questions  
    for i in range(questions_per_type['state_comparison']):
        states_sample = random.sample(list(states), 3)
        domain = random.choice(list(health_indicators.keys()))
        indicator = random.choice(health_indicators[domain])
        
        if indicator in df.columns:
            state_avgs = []
            for state in states_sample:
                state_data = df[df['state'] == state]
                avg_val = state_data[indicator].mean()
                if pd.notna(avg_val):
                    state_avgs.append(f"{state}: {avg_val:.1f}%")
            
            if len(state_avgs) >= 2:
                new_questions.append({
                    "id": current_id,
                    "question": f"Compare {indicator.replace('_', ' ')} across {', '.join(states_sample)}",
                    "ground_truth": state_avgs,
                    "query_type": "state_comparison",
                    "domain": domain, 
                    "difficulty": "medium",
                    "answer_type": "comparison",
                    "gold_pandas_code": f"result = df[df['state'].isin({states_sample})].groupby('state')['{indicator}'].mean().to_dict()"
                })
                current_id += 1
    
    # 4. Trend analysis questions (simplified without NFHS-4)
    for i in range(questions_per_type['trend_analysis']):
        state = random.choice(states)
        domain = random.choice(list(health_indicators.keys()))
        indicator = random.choice(health_indicators[domain])
        
        if indicator in df.columns:
            state_data = df[df['state'] == state].sort_values(indicator)
            if len(state_data) > 3:
                best_districts = state_data.tail(3)[['district', indicator]]
                worst_districts = state_data.head(3)[['district', indicator]]
                
                performance_type = random.choice(['best', 'worst'])
                districts_list = best_districts if performance_type == 'best' else worst_districts
                
                new_questions.append({
                    "id": current_id,
                    "question": f"Which districts in {state} have the {performance_type} {indicator.replace('_', ' ')}?",
                    "ground_truth": [f"{row['district']}: {row[indicator]:.1f}%" for _, row in districts_list.iterrows()],
                    "query_type": "trend_analysis",
                    "domain": domain,
                    "difficulty": "hard", 
                    "answer_type": "ranking",
                    "gold_pandas_code": f"result = df[df['state']=='{state}'].n{'largest' if performance_type == 'best' else 'smallest'}(3, '{indicator}')[['district', '{indicator}']].to_dict('records')"
                })
                current_id += 1
    
    # 5. Correlation questions
    for i in range(questions_per_type['correlation']):
        domain1 = random.choice(list(health_indicators.keys()))
        domain2 = random.choice(list(health_indicators.keys()))
        indicator1 = random.choice(health_indicators[domain1])
        indicator2 = random.choice(health_indicators[domain2])
        
        if indicator1 in df.columns and indicator2 in df.columns and indicator1 != indicator2:
            correlation = df[[indicator1, indicator2]].corr().iloc[0,1]
            
            if pd.notna(correlation):
                new_questions.append({
                    "id": current_id,
                    "question": f"Is there a correlation between {indicator1.replace('_', ' ')} and {indicator2.replace('_', ' ')} across districts?",
                    "ground_truth": f"Correlation: {correlation:.3f}",
                    "query_type": "correlation",
                    "domain": f"{domain1}_vs_{domain2}",
                    "difficulty": "hard",
                    "answer_type": "correlation", 
                    "gold_pandas_code": f"result = df[['{indicator1}', '{indicator2}']].corr().iloc[0,1]"
                })
                current_id += 1
    
    return new_questions[:81]  # Ensure exactly 81 questions

def main():
    """Generate and save additional questions"""
    print("🔄 Generating additional benchmark questions...")
    
    df, existing_benchmark = load_data()
    new_questions = generate_additional_questions(df, existing_benchmark)
    
    # Add new questions to existing benchmark
    all_questions = existing_benchmark["questions"] + new_questions
    
    # Update metadata
    existing_benchmark["questions"] = all_questions
    existing_benchmark["metadata"]["total_questions"] = len(all_questions)
    
    # Save updated benchmark
    with open(EVAL_DIR / "benchmark_questions.json", "w") as f:
        json.dump(existing_benchmark, f, indent=2)
    
    print(f"✅ Added {len(new_questions)} new questions")
    print(f"📊 Total questions: {len(all_questions)}")
    print(f"🎯 Target reached: {len(all_questions) >= 200}")

if __name__ == "__main__":
    main()