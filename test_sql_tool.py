#!/usr/bin/env python3
"""
Test the new SQL query tool
"""

from backend.agent.tools.tools import sql_query
import json

def test_sql_queries():
    """Test various SQL queries on the NFHS-5 data"""
    
    print("🧪 Testing SQL Query Tool")
    print("=" * 40)
    
    test_queries = [
        {
            "name": "Count total districts",
            "query": "SELECT COUNT(*) as total_districts FROM nfhs5"
        },
        {
            "name": "Top 5 states by avg stunting",
            "query": "SELECT state, AVG(stunting_pct) as avg_stunting FROM nfhs5 GROUP BY state ORDER BY avg_stunting DESC LIMIT 5"
        },
        {
            "name": "Kerala district stats",
            "query": "SELECT district, stunting_pct, institutional_delivery_pct FROM nfhs5 WHERE state = 'Kerala' ORDER BY stunting_pct"
        },
        {
            "name": "Districts with high stunting",
            "query": "SELECT district, state, stunting_pct FROM nfhs5 WHERE stunting_pct > 40 ORDER BY stunting_pct DESC LIMIT 10"
        },
        {
            "name": "Security test (should fail)",
            "query": "DROP TABLE nfhs5"
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n[{i}] {test['name']}")
        print(f"Query: {test['query']}")
        
        try:
            result = sql_query(test['query'])
            
            if result['status'] == 'success':
                print(f"✅ Success: {result['row_count']} rows returned")
                if result['data'] and len(result['data']) <= 5:
                    print("Sample data:")
                    for row in result['data'][:3]:
                        print(f"  {row}")
            else:
                print(f"❌ Error: {result['error']}")
                
        except Exception as e:
            print(f"💥 Exception: {e}")
        
        print("-" * 30)

if __name__ == "__main__":
    test_sql_queries()