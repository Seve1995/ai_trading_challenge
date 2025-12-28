import os
import csv
from datetime import datetime, date
import pathlib
import config

# Configuration
PERFORMANCE_LOG = pathlib.Path("logs/performance.csv")
EXPERIMENT_START_DATE = "2026-01-02"

def log_all_performance():
    """Fetches historical equity for all models and rebuilds the performance CSV."""
    print(f"📈 Rebuilding Performance History...")
    
    # master_data = { "YYYY-MM-DD": { "ModelName": equity, ... } }
    master_data = {}
    
    for key, info in config.MODELS.items():
        model_name = info['name']
        print(f"   ... Fetching History for {model_name} ...")
        
        try:
            api = config.get_alpaca_api(info)
            # Fetch last 1 month of daily history
            history = api.get_portfolio_history(period='1M', timeframe='1D')
            
            # Zip timestamps and equity values
            # Note: history.timestamp is a list of epoch seconds
            for ts, eq in zip(history.timestamp, history.equity):
                dt_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                
                if dt_str not in master_data:
                    master_data[dt_str] = {}
                
                master_data[dt_str][model_name] = eq
                
            print(f"   ✅ {model_name} synced.")
        except Exception as e:
            print(f"   ❌ Error fetching {model_name}: {e}")

    if not master_data:
        print("🛑 No performance data found. Check your API keys and connection.")
        return

    # Sort dates and filter (if you only want after start date, uncomment below)
    sorted_dates = sorted(master_data.keys())
    
    # Define headers based on model names in config
    headers = ["Date"] + [info['name'] for info in config.MODELS.values()]
    
    try:
        PERFORMANCE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(PERFORMANCE_LOG, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for dt in sorted_dates:
                row = {"Date": dt}
                # Fill in model values, handle missing with empty string
                for model in headers[1:]:
                    row[model] = master_data[dt].get(model, "")
                writer.writerow(row)
                
        print(f"\n📂 Performance history rebuilt and saved to: {PERFORMANCE_LOG}")
    except Exception as e:
        print(f"\n❌ Failed to save performance data: {e}")

if __name__ == "__main__":
    log_all_performance()
