#!/usr/bin/env python3
"""
Failure Analysis Module
Categorizes all wrong answers and provides detailed failure analysis
"""

import json
import re
import pandas as pd
from typing import Dict, List, Any
from pathlib import Path

def categorize_failure(question: str, agent_response: str, ground_truth: str, 
                      ea_score: float, af_score: float, hr_result: dict) -> Dict[str, Any]:
    """
    Categorize failure type for incorrect agent responses.
    
    Categories:
    1. hallucination - agent made up facts (HR > 0)
    2. code_error - pandas/sql code failed to execute properly
    3. schema_confusion - wrong column names or misunderstood indicators
    4. reasoning_gap - correct data but wrong logical reasoning
    5. partial_correct - some parts right but overall incorrect
    """
    
    failure_category = "unknown"
    details = {}
    confidence = 0.0
    
    # Check for hallucination first (most serious)
    if hr_result.get("has_hallucination", False):
        failure_category = "hallucination"
        details = {
            "hallucination_types": hr_result.get("hallucination_types", []),
            "fabricated_facts": hr_result.get("details", [])
        }
        confidence = 0.9
        
    # Check for code execution errors
    elif "error" in agent_response.lower() or "failed" in agent_response.lower():
        failure_category = "code_error"
        # Extract error details from response
        error_patterns = [
            r"error[:\s]+(.+?)(?:\n|$)",
            r"exception[:\s]+(.+?)(?:\n|$)", 
            r"failed[:\s]+(.+?)(?:\n|$)"
        ]
        
        for pattern in error_patterns:
            match = re.search(pattern, agent_response, re.IGNORECASE)
            if match:
                details["error_message"] = match.group(1).strip()
                break
        
        confidence = 0.8
        
    # Check for schema confusion (wrong column references)
    elif any(phrase in agent_response.lower() for phrase in [
        "column not found", "keyerror", "not in dataframe", "no such column"
    ]):
        failure_category = "schema_confusion"
        # Try to extract column names mentioned
        column_pattern = r"'([^']+)'"
        mentioned_columns = re.findall(column_pattern, agent_response)
        details["mentioned_columns"] = mentioned_columns
        confidence = 0.8
        
    # Check reasoning quality based on AF score
    elif af_score < 0.5:
        failure_category = "reasoning_gap"
        details["af_score"] = af_score
        details["reasoning_issues"] = analyze_reasoning_issues(question, agent_response, ground_truth)
        confidence = 0.7
        
    # Check for partial correctness
    elif ea_score > 0.0 and ea_score < 0.8:
        failure_category = "partial_correct"
        details["ea_score"] = ea_score
        details["af_score"] = af_score
        confidence = 0.6
        
    # Generic failure if nothing else matches
    else:
        failure_category = "unknown"
        details = {
            "ea_score": ea_score,
            "af_score": af_score,
            "response_length": len(agent_response),
            "contains_numbers": bool(re.search(r'\d+\.?\d*', agent_response))
        }
        confidence = 0.3
    
    return {
        "failure_category": failure_category,
        "confidence": confidence,
        "details": details,
        "severity": get_failure_severity(failure_category, ea_score, af_score)
    }

def analyze_reasoning_issues(question: str, response: str, ground_truth: str) -> List[str]:
    """Identify specific reasoning problems in the agent response"""
    issues = []
    
    # Check if agent didn't use appropriate data analysis
    if "stunting" in question.lower() and "stunting" not in response.lower():
        issues.append("missed_key_indicator")
    
    # Check if agent gave generic response instead of specific analysis
    generic_phrases = ["i don't have", "cannot determine", "not available", "insufficient data"]
    if any(phrase in response.lower() for phrase in generic_phrases):
        issues.append("generic_response")
    
    # Check if agent confused different indicators
    health_indicators = ["stunting", "wasting", "anaemia", "vaccination", "delivery"]
    question_indicators = [ind for ind in health_indicators if ind in question.lower()]
    response_indicators = [ind for ind in health_indicators if ind in response.lower()]
    
    if question_indicators and not any(ind in response_indicators for ind in question_indicators):
        issues.append("indicator_confusion")
    
    # Check if agent mixed up states/districts
    if "state" in question.lower() and "district" in response.lower():
        issues.append("geographic_confusion")
    
    return issues

def get_failure_severity(category: str, ea_score: float, af_score: float) -> str:
    """Determine severity level of the failure"""
    
    if category == "hallucination":
        return "high" if af_score < 0.3 else "medium"
    elif category == "code_error":
        return "high" if ea_score == 0.0 else "medium"
    elif category == "schema_confusion":
        return "medium"
    elif category == "reasoning_gap":
        return "medium" if af_score < 0.3 else "low"
    elif category == "partial_correct":
        return "low"
    else:
        return "low"

def generate_failure_report(evaluation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate comprehensive failure analysis report from evaluation results
    """
    
    total_questions = len(evaluation_results)
    failed_questions = [r for r in evaluation_results if r.get("ea_score", 0) < 0.8]
    
    if not failed_questions:
        return {
            "summary": {
                "total_questions": total_questions,
                "failed_questions": 0,
                "failure_rate": 0.0
            },
            "message": "No failures to analyze - excellent performance!"
        }
    
    # Categorize all failures
    failure_categories = {}
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    
    for result in failed_questions:
        # Simulate failure analysis (in real implementation, this would be computed during evaluation)
        category_result = categorize_failure(
            result.get("question", ""),
            result.get("agent_response", ""),
            result.get("ground_truth", ""),
            result.get("ea_score", 0),
            result.get("af_score", 0),
            result.get("hr_result", {})
        )
        
        category = category_result["failure_category"]
        severity = category_result["severity"]
        
        if category not in failure_categories:
            failure_categories[category] = []
        
        failure_categories[category].append({
            "question_id": result.get("question_id", "unknown"),
            "question": result.get("question", "")[:100] + "..." if len(result.get("question", "")) > 100 else result.get("question", ""),
            "severity": severity,
            "details": category_result["details"]
        })
        
        severity_counts[severity] += 1
    
    # Generate recommendations
    recommendations = generate_recommendations(failure_categories)
    
    # Calculate category percentages
    category_stats = {}
    for category, failures in failure_categories.items():
        category_stats[category] = {
            "count": len(failures),
            "percentage": round((len(failures) / len(failed_questions)) * 100, 1)
        }
    
    return {
        "summary": {
            "total_questions": total_questions,
            "failed_questions": len(failed_questions),
            "failure_rate": round((len(failed_questions) / total_questions) * 100, 1),
            "severity_breakdown": severity_counts
        },
        "failure_categories": category_stats,
        "detailed_failures": failure_categories,
        "recommendations": recommendations,
        "top_issues": get_top_issues(failure_categories)
    }

def generate_recommendations(failure_categories: Dict[str, List]) -> List[str]:
    """Generate specific recommendations based on failure patterns"""
    recommendations = []
    
    if "hallucination" in failure_categories:
        count = len(failure_categories["hallucination"])
        if count > 2:
            recommendations.append(f"🚨 High Priority: Fix hallucination issues ({count} cases). Strengthen grounding rules in system prompt.")
    
    if "code_error" in failure_categories:
        count = len(failure_categories["code_error"])
        recommendations.append(f"🔧 Fix code execution issues ({count} cases). Review pandas query tool error handling.")
    
    if "schema_confusion" in failure_categories:
        count = len(failure_categories["schema_confusion"])
        recommendations.append(f"📋 Schema issues detected ({count} cases). Improve column name fuzzy matching and add more examples.")
    
    if "reasoning_gap" in failure_categories:
        count = len(failure_categories["reasoning_gap"])
        recommendations.append(f"🧠 Reasoning improvements needed ({count} cases). Add few-shot examples for complex query types.")
    
    if not recommendations:
        recommendations.append("✅ No critical issues detected. System performance is good!")
    
    return recommendations

def get_top_issues(failure_categories: Dict[str, List]) -> List[Dict[str, Any]]:
    """Identify the most common failure patterns"""
    
    issues = []
    
    # Count by category
    for category, failures in failure_categories.items():
        issues.append({
            "issue_type": category,
            "frequency": len(failures),
            "sample_question": failures[0]["question"] if failures else "N/A",
            "priority": "high" if category in ["hallucination", "code_error"] else "medium"
        })
    
    # Sort by frequency
    issues.sort(key=lambda x: x["frequency"], reverse=True)
    
    return issues[:5]  # Top 5 issues

def export_failure_analysis(results: Dict[str, Any], output_path: str = None):
    """Export failure analysis results to JSON file"""
    
    if output_path is None:
        output_path = Path(__file__).parent / "failure_analysis_report.json"
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Failure analysis report saved to: {output_path}")

if __name__ == "__main__":
    # Test failure analysis with sample data
    sample_results = [
        {
            "question_id": 1,
            "question": "What is the stunting rate in Kerala?",
            "agent_response": "The stunting rate in Kerala is 23.4%",
            "ground_truth": "23.3%",
            "ea_score": 0.9,
            "af_score": 0.95,
            "hr_result": {"has_hallucination": False}
        },
        {
            "question_id": 2,
            "question": "Which districts have highest anaemia?",
            "agent_response": "Error: column 'anaemia_rate' not found in dataframe",
            "ground_truth": "['District A', 'District B']",
            "ea_score": 0.0,
            "af_score": 0.0,
            "hr_result": {"has_hallucination": False}
        }
    ]
    
    report = generate_failure_report(sample_results)
    print(json.dumps(report, indent=2))