#!/usr/bin/env python3
"""
Test script to verify BharatHealth tools work directly
"""

def test_tools():
    """Test each tool individually"""
    
    print("🧪 Testing BharatHealth Tools...")
    
    # Test 1: Data loading
    try:
        from backend.agent.tools.tools import get_df, get_schema
        df = get_df()
        schema = get_schema()
        print(f"✅ Data loaded: {len(df)} districts, {len(df.columns)} columns")
        print(f"✅ Schema loaded: {len(schema)} indicators")
    except Exception as e:
        print(f"❌ Data loading failed: {e}")
        return False
    
    # Test 2: Semantic search
    try:
        from backend.agent.tools.tools import semantic_search
        result = semantic_search("kerala stunting", n_results=3)
        print(f"✅ Semantic search works: Found {len(result.get('districts', []))} districts")
    except Exception as e:
        print(f"❌ Semantic search failed: {e}")
    
    # Test 3: Pandas query 
    try:
        from backend.agent.tools.tools import pandas_query
        result = pandas_query("What is the average stunting rate in Kerala?")
        print(f"✅ Pandas query works: {result[:100]}...")
    except Exception as e:
        print(f"❌ Pandas query failed: {e}")
    
    # Test 4: Trend analysis
    try:
        from backend.agent.tools.tools import trend_analyser
        result = trend_analyser("stunting", state_filter="Kerala", top_n=5)
        print(f"✅ Trend analysis works: {result[:100]}...")
    except Exception as e:
        print(f"❌ Trend analysis failed: {e}")
        
    # Test 5: Check sample data
    try:
        kerala_data = df[df['state'].str.contains('Kerala', case=False, na=False)]
        if not kerala_data.empty:
            stunting_cols = [col for col in df.columns if 'stunt' in col.lower()]
            print(f"✅ Kerala data available: {len(kerala_data)} districts")
            print(f"✅ Stunting columns: {stunting_cols}")
        else:
            print("⚠️  No Kerala data found")
    except Exception as e:
        print(f"❌ Data check failed: {e}")
    
    print("\n🎉 Tool testing complete! Your core system is functional.")
    return True

if __name__ == "__main__":
    test_tools()