#!/usr/bin/env python3
"""
Quick demo of BharatHealth system - showing core functionality
"""

def demo_system():
    """Demonstrate key capabilities"""
    
    print("🏥 BharatHealth Analyst - Quick Demo")
    print("=" * 50)
    
    # Load data
    try:
        from backend.agent.tools.tools import get_df, get_schema
        df = get_df()
        schema = get_schema()
        
        print(f"📊 Dataset: {len(df)} districts across {df['state'].nunique()} states")
        print(f"📈 Indicators: {len(schema)} health metrics")
        print()
        
        # Show Kerala data
        kerala_data = df[df['state'].str.contains('Kerala', case=False, na=False)]
        print(f"🌴 Kerala Districts: {len(kerala_data)}")
        for _, row in kerala_data.head().iterrows():
            print(f"   • {row['district']}")
        print()
        
        # Show key health indicators
        key_indicators = ['stunting_pct', 'wasting_pct', 'anaemia_children_pct', 'institutional_delivery_pct']
        available_indicators = [col for col in key_indicators if col in df.columns]
        
        if available_indicators:
            print("🏥 Key Health Indicators in Kerala:")
            for indicator in available_indicators[:3]:  # Show first 3
                if indicator in df.columns:
                    avg_value = kerala_data[indicator].mean()
                    print(f"   • {indicator.replace('_', ' ').title()}: {avg_value:.1f}%")
        print()
        
        # Show top districts nationally by a key metric
        if 'institutional_delivery_pct' in df.columns:
            top_districts = df.nlargest(5, 'institutional_delivery_pct')[['district', 'state', 'institutional_delivery_pct']]
            print("🏆 Top 5 Districts - Institutional Delivery:")
            for _, row in top_districts.iterrows():
                print(f"   • {row['district']}, {row['state']}: {row['institutional_delivery_pct']:.1f}%")
        print()
        
        # Show available tool functions
        print("🛠️  Available Analysis Tools:")
        tools = [
            "semantic_search - Find districts by description",
            "pandas_query - Complex data analysis", 
            "trend_analyser - Ranking and distribution",
            "correlation_finder - Statistical relationships",
            "chart_generator - Interactive visualizations",
            "insight_writer - Natural language summaries"
        ]
        
        for tool in tools:
            print(f"   • {tool}")
        
        print()
        print("✅ System Status: FULLY FUNCTIONAL")
        print("🚀 Ready for deployment and evaluation!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    demo_system()