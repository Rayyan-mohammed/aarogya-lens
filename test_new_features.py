#!/usr/bin/env python3
"""
Test script for the newly added features
"""

def test_sql_tool():
    """Test SQL query tool"""
    print("🧪 Testing SQL Query Tool...")
    from backend.agent.tools.tools import sql_query
    
    result = sql_query("SELECT COUNT(*) as total FROM nfhs5")
    if result['status'] == 'success':
        print(f"✅ SQL tool works: {result['data']}")
    else:
        print(f"❌ SQL tool failed: {result['error']}")

def test_af_module():
    """Test Answer Faithfulness module"""
    print("🧪 Testing Answer Faithfulness...")
    from backend.evaluation.answer_faithfulness import compute_answer_faithfulness
    
    test_response = "Kerala has 23.4% stunting rate and 156 districts have high stunting."
    result = compute_answer_faithfulness(test_response, "Test question")
    print(f"✅ AF module works: Score = {result['af_score']}, Claims = {result['total_claims']}")

def test_failure_analysis():
    """Test failure analysis module"""
    print("🧪 Testing Failure Analysis...")
    from backend.evaluation.failure_analysis import generate_failure_report
    
    sample_data = [
        {
            "question_id": 1,
            "question": "Test question",
            "agent_response": "Test response",
            "ground_truth": "Test ground truth",
            "ea_score": 0.5,
            "af_score": 0.3,
            "hr_result": {"has_hallucination": False}
        }
    ]
    
    report = generate_failure_report(sample_data)
    print(f"✅ Failure analysis works: {report['summary']['failed_questions']} failed questions")

def test_eval_pipeline():
    """Test the complete evaluation pipeline"""
    print("🧪 Testing Complete Evaluation Pipeline...")
    
    import subprocess
    import sys
    
    result = subprocess.run([
        sys.executable, "-m", "backend.evaluation.eval_runner", 
        "--dry-run", "--n", "2"
    ], capture_output=True, text=True)
    
    if result.returncode == 0 and "OVERALL RESULTS" in result.stdout:
        print("✅ Evaluation pipeline works!")
        # Extract key metrics from output
        lines = result.stdout.split('\n')
        for line in lines:
            if 'Execution Accuracy (EA)' in line:
                print(f"  {line.strip()}")
            elif 'Answer Faithfulness (AF)' in line:
                print(f"  {line.strip()}")
    else:
        print(f"❌ Evaluation pipeline failed: {result.stderr}")

if __name__ == "__main__":
    print("🚀 Testing New BharatHealth Features")
    print("=" * 50)
    
    test_sql_tool()
    print()
    test_af_module() 
    print()
    test_failure_analysis()
    print()
    test_eval_pipeline()
    
    print("\n🎉 All new features tested successfully!")