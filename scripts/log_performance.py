import sys
import csv
import json
import pathlib
import os
from datetime import datetime, timezone
# Add root directory to path to import config
root_dir = pathlib.Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))
import config

# Configuration
PERFORMANCE_LOG = config.PERFORMANCE_LOG
LAST_UPDATED_LOG = config.LOGS_DIR / "last_updated.json"
EXPERIMENT_START_DATE = config.EXPERIMENT_START_DATE

def log_all_performance():
    """Fetches historical equity for all models and rebuilds the performance CSV."""
    print(f"📈 Rebuilding Performance History (Start: {EXPERIMENT_START_DATE}) ...")
    
    # 1. Generate the list of dates we want to cover
    start_dt = datetime.strptime(EXPERIMENT_START_DATE, '%Y-%m-%d')
    end_dt = datetime.now()
    delta = end_dt - start_dt
    
    target_dates = []
    for i in range(delta.days + 1):
        day = start_dt + timedelta(days=i)
        target_dates.append(day.strftime('%Y-%m-%d'))
    
    # 2. Initialize master_data with default 1000.0 for all models on all target dates
    master_data = {dt: {info['name']: 1000.0 for info in config.MODELS.values()} for dt in target_dates}
    
    # 3. Fetch actual data from Alpaca
    for key, info in config.MODELS.items():
        model_name = info['name']
        print(f"   ... Fetching History for {model_name} ...")
        
        try:
            api = config.get_alpaca_api(info)
            # Fetch last 1 month of daily history
            history = api.get_portfolio_history(period='1M', timeframe='1D')
            
            for ts, eq in zip(history.timestamp, history.equity):
                dt_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                
                # Only update if the date is in our targets and equity is > 0
                # (Paper accounts sometimes return 0 for non-active days)
                if dt_str in master_data and eq and eq > 0:
                    master_data[dt_str][model_name] = eq
                
            print(f"   ✅ {model_name} synced.")
        except Exception as e:
            print(f"   ❌ Error fetching {model_name}: {e}")

    # 4. Save to CSV
    headers = ["Date"] + [info['name'] for info in config.MODELS.values()]
    
    try:
        PERFORMANCE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(PERFORMANCE_LOG, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for dt in sorted(master_data.keys()):
                row = {"Date": dt}
                for model in headers[1:]:
                    row[model] = master_data[dt].get(model, 1000.0)
                writer.writerow(row)
                
        print(f"\n📂 Performance history rebuilt and saved to: {PERFORMANCE_LOG}")
        
        # 5. Write last_updated.json for dashboard
        source = "github_actions" if os.getenv("GITHUB_ACTIONS") else "local"
        last_updated = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source
        }
        with open(LAST_UPDATED_LOG, "w") as f:
            json.dump(last_updated, f, indent=2)
        print(f"📅 Last updated timestamp saved to: {LAST_UPDATED_LOG}")
        
    except Exception as e:
        print(f"\n❌ Failed to save performance data: {e}")

if __name__ == "__main__":
    from datetime import timedelta # Need this for date generation
    log_all_performance()
    
    # Also log current portfolio holdings
    from log_portfolios import log_all_portfolios
    log_all_portfolios()
