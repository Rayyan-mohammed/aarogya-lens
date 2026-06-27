#!/usr/bin/env python3
"""
Answer Faithfulness (AF) Module
Measures whether factual claims in agent responses are grounded in the actual dataset
"""

import re
import json
import pandas as pd
from typing import List, Dict, Any
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "backend" / "data"

def load_ground_truth_data():
    """Load the NFHS-5 dataset for fact verification"""
    return pd.read_parquet(DATA_DIR / "nfhs5_clean.parquet")

def extract_factual_claims(response_text: str) -> List[Dict[str, str]]:
    """
    Extract factual claims from agent response text.
    Returns list of claims with location, indicator, and value information.
    """
    claims = []
    
    # Pattern 1: "District X has Y% indicator"
    pattern1 = r"(\w+(?:\s+\w+)*)\s+(?:district\s+)?(?:has|shows?)\s+(?:an?\s+)?(\w+(?:\s+\w+)*)\s+(?:rate\s+)?(?:of\s+)?(\d+\.?\d*)%?"
    matches1 = re.finditer(pattern1, response_text, re.IGNORECASE)
    
    for match in matches1:
        claims.append({
            "type": "district_value",
            "location": match.group(1).strip(),
            "indicator": match.group(2).strip(), 
            "value": float(match.group(3)),
            "original_text": match.group(0)
        })
    
    # Pattern 2: "In State X, indicator is Y%"
    pattern2 = r"in\s+(\w+(?:\s+\w+)*),?\s+(\w+(?:\s+\w+)*)\s+(?:is|are|rate)\s+(\d+\.?\d*)%?"
    matches2 = re.finditer(pattern2, response_text, re.IGNORECASE)
    
    for match in matches2:
        claims.append({
            "type": "state_value",
            "location": match.group(1).strip(),
            "indicator": match.group(2).strip(),
            "value": float(match.group(3)),
            "original_text": match.group(0)
        })
    
    # Pattern 3: "State A: X%, State B: Y%"
    pattern3 = r"(\w+(?:\s+\w+)*):?\s+(\d+\.?\d*)%"
    matches3 = re.finditer(pattern3, response_text, re.IGNORECASE)
    
    for match in matches3:
        claims.append({
            "type": "comparison_value",
            "location": match.group(1).strip(),
            "value": float(match.group(2)),
            "original_text": match.group(0)
        })
    
    # Pattern 4: "X districts have indicator above Y%"
    pattern4 = r"(\d+)\s+districts?\s+(?:have|show)\s+(\w+(?:\s+\w+)*)\s+(?:above|over|greater than)\s+(\d+\.?\d*)%?"
    matches4 = re.finditer(pattern4, response_text, re.IGNORECASE)
    
    for match in matches4:
        claims.append({
            "type": "count_claim",
            "count": int(match.group(1)),
            "indicator": match.group(2).strip(),
            "threshold": float(match.group(3)),
            "comparison": "above",
            "original_text": match.group(0)
        })
    
    return claims

def verify_claim_against_data(claim: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    """
    Verify a single factual claim against the ground truth dataset.
    Returns verification result with accuracy score.
    """
    from rapidfuzz import process, fuzz
    
    verification = {
        "claim": claim,
        "verified": False,
        "accuracy_score": 0.0,
        "ground_truth_value": None,
        "error": None
    }
    
    try:
        if claim["type"] == "district_value":
            # Find matching district
            all_districts = df['district'].unique()
            district_match, district_score, _ = process.extractOne(
                claim["location"], all_districts, scorer=fuzz.token_sort_ratio
            )
            
            if district_score < 70:
                verification["error"] = f"District '{claim['location']}' not found. Best match: {district_match} (score: {district_score})"
                return verification
            
            # Find matching indicator column
            all_cols = [col for col in df.columns if not col in ['district', 'state']]
            indicator_match, indicator_score, _ = process.extractOne(
                claim["indicator"], all_cols, scorer=fuzz.token_sort_ratio
            )
            
            if indicator_score < 60:
                verification["error"] = f"Indicator '{claim['indicator']}' not found. Best match: {indicator_match} (score: {indicator_score})"
                return verification
            
            # Get actual value
            district_data = df[df['district'] == district_match]
            if district_data.empty:
                verification["error"] = f"No data found for district {district_match}"
                return verification
                
            actual_value = district_data[indicator_match].iloc[0]
            if pd.isna(actual_value):
                verification["error"] = f"Missing data for {indicator_match} in {district_match}"
                return verification
            
            verification["ground_truth_value"] = actual_value
            
            # Compare values (within 2% tolerance for rounding)
            diff = abs(claim["value"] - actual_value)
            if diff <= 2.0:  # 2% tolerance
                verification["verified"] = True
                verification["accuracy_score"] = max(0, 1.0 - (diff / 10.0))  # Score decreases with difference
            
        elif claim["type"] == "state_value":
            # Find matching state
            all_states = df['state'].unique()
            state_match, state_score, _ = process.extractOne(
                claim["location"], all_states, scorer=fuzz.token_sort_ratio
            )
            
            if state_score < 70:
                verification["error"] = f"State '{claim['location']}' not found"
                return verification
            
            # Find matching indicator
            all_cols = [col for col in df.columns if not col in ['district', 'state']]
            indicator_match, indicator_score, _ = process.extractOne(
                claim["indicator"], all_cols, scorer=fuzz.token_sort_ratio
            )
            
            if indicator_score < 60:
                verification["error"] = f"Indicator '{claim['indicator']}' not found"
                return verification
            
            # Calculate state average
            state_data = df[df['state'] == state_match]
            state_avg = state_data[indicator_match].mean()
            
            if pd.isna(state_avg):
                verification["error"] = f"No valid data for {indicator_match} in {state_match}"
                return verification
            
            verification["ground_truth_value"] = state_avg
            
            # Compare values
            diff = abs(claim["value"] - state_avg)
            if diff <= 3.0:  # 3% tolerance for state averages
                verification["verified"] = True
                verification["accuracy_score"] = max(0, 1.0 - (diff / 15.0))
            
        elif claim["type"] == "count_claim":
            # Find matching indicator
            all_cols = [col for col in df.columns if not col in ['district', 'state']]
            indicator_match, indicator_score, _ = process.extractOne(
                claim["indicator"], all_cols, scorer=fuzz.token_sort_ratio
            )
            
            if indicator_score < 60:
                verification["error"] = f"Indicator '{claim['indicator']}' not found"
                return verification
            
            # Count districts above threshold
            if claim["comparison"] == "above":
                actual_count = len(df[df[indicator_match] > claim["threshold"]])
            else:
                actual_count = len(df[df[indicator_match] < claim["threshold"]])
            
            verification["ground_truth_value"] = actual_count
            
            # Compare counts (within 10% tolerance)
            diff = abs(claim["count"] - actual_count)
            tolerance = max(1, actual_count * 0.1)  # 10% or at least 1
            
            if diff <= tolerance:
                verification["verified"] = True
                verification["accuracy_score"] = max(0, 1.0 - (diff / max(actual_count, 1)))
    
    except Exception as e:
        verification["error"] = f"Verification failed: {str(e)}"
    
    return verification

def compute_answer_faithfulness(agent_response: str, question: str = None) -> Dict[str, Any]:
    """
    Main function to compute Answer Faithfulness score for an agent response.
    
    Returns:
        - af_score: Overall faithfulness score (0-1)
        - total_claims: Number of claims extracted
        - verified_claims: Number of claims verified as correct
        - failed_claims: Number of claims that failed verification
        - claim_details: Detailed verification results for each claim
    """
    
    df = load_ground_truth_data()
    claims = extract_factual_claims(agent_response)
    
    if not claims:
        return {
            "af_score": 1.0,  # No claims = no false claims
            "total_claims": 0,
            "verified_claims": 0,
            "failed_claims": 0,
            "claim_details": [],
            "note": "No factual claims extracted from response"
        }
    
    verification_results = []
    verified_count = 0
    total_accuracy = 0.0
    
    for claim in claims:
        verification = verify_claim_against_data(claim, df)
        verification_results.append(verification)
        
        if verification["verified"]:
            verified_count += 1
            total_accuracy += verification["accuracy_score"]
    
    # Calculate overall AF score
    if len(claims) > 0:
        af_score = verified_count / len(claims)
        # Weight by accuracy scores if any claims were verified
        if verified_count > 0:
            weighted_accuracy = total_accuracy / verified_count
            af_score = af_score * weighted_accuracy
    else:
        af_score = 1.0
    
    return {
        "af_score": round(af_score, 3),
        "total_claims": len(claims),
        "verified_claims": verified_count,
        "failed_claims": len(claims) - verified_count,
        "claim_details": verification_results,
        "question": question
    }

def batch_compute_af(responses: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Compute AF scores for a batch of agent responses.
    
    Args:
        responses: List of dicts with 'response' and optionally 'question' keys
    
    Returns:
        Overall AF statistics and per-response results
    """
    
    results = []
    total_af = 0.0
    
    for i, resp in enumerate(responses):
        af_result = compute_answer_faithfulness(
            resp.get("response", ""), 
            resp.get("question", f"Question {i+1}")
        )
        results.append(af_result)
        total_af += af_result["af_score"]
    
    overall_af = total_af / len(responses) if responses else 0.0
    
    return {
        "overall_af_score": round(overall_af, 3),
        "total_responses": len(responses),
        "per_response_results": results,
        "summary": {
            "total_claims": sum(r["total_claims"] for r in results),
            "total_verified": sum(r["verified_claims"] for r in results),
            "total_failed": sum(r["failed_claims"] for r in results),
        }
    }

if __name__ == "__main__":
    # Test the AF module
    test_response = """
    Kerala has a stunting rate of 23.4%. In comparison, Bihar shows a stunting rate of 42.9%.
    The institutional delivery rate in Kerala is 99.1%, while Bihar has 63.8%.
    Overall, 156 districts have stunting rates above 40%.
    """
    
    result = compute_answer_faithfulness(test_response, "Compare Kerala and Bihar health indicators")
    print(json.dumps(result, indent=2))