#!/usr/bin/env python3
"""
Test script to verify the BharatHealth agent works end-to-end
"""

import requests
import json
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_query():
    """Test a simple query to ensure the agent works"""
    
    url = "http://127.0.0.1:8000/query"
    
    # Simple test query - using a model with available API key
    payload = {
        "question": "What is the stunting rate in Kerala?",
        "model": "groq",  # Use Groq since we have the API key
        "api_key": os.getenv("GROQ_API_KEY"),  # Pass the API key
        "filters": {}
    }
    
    print("🧪 Testing BharatHealth Agent...")
    print(f"Query: {payload['question']}")
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=30)
        end_time = time.time()
        
        print(f"⏱️  Response time: {end_time - start_time:.2f}s")
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Query successful!")
            print(f"📝 Answer: {data.get('answer', 'No answer')}")
            print(f"📈 Charts: {data.get('chart_path', 'None')}")
            print(f"🔢 Confidence: {data.get('confidence', 'N/A')}")
            return True
        else:
            print(f"❌ Query failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_query()
    if success:
        print("\n🎉 System is working! Ready for deployment.")
    else:
        print("\n⚠️  System needs debugging before deployment.")