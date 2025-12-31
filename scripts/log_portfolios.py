import sys
import json
import pathlib
from datetime import datetime

# Add root directory to path to import config
root_dir = pathlib.Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))
import config

# Configuration
PORTFOLIOS_LOG = config.LOGS_DIR / "portfolios.json"

def load_existing_portfolios():
    """Load existing portfolio data from JSON file."""
    if PORTFOLIOS_LOG.exists():
        try:
            with open(PORTFOLIOS_LOG, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def log_all_portfolios():
    """Fetches current positions for all models and saves to portfolios.json."""
    print(f"\n📂 Logging Portfolio Holdings...")
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Load existing data
    all_portfolios = load_existing_portfolios()
    
    # Initialize today's entry
    today_portfolios = {}
    
    for key, info in config.MODELS.items():
        model_name = info['name']
        print(f"   ... Fetching positions for {model_name} ...")
        
        try:
            api = config.get_alpaca_api(info)
            positions = api.list_positions()
            
            holdings = []
            for pos in positions:
                holding = {
                    "ticker": pos.symbol,
                    "qty": float(pos.qty),
                    "avg_cost": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_pl_pct": float(pos.unrealized_plpc) * 100  # Convert to percentage
                }
                holdings.append(holding)
            
            today_portfolios[model_name] = holdings
            
            if holdings:
                print(f"   ✅ {model_name}: {len(holdings)} position(s)")
            else:
                print(f"   ✅ {model_name}: No positions (cash)")
                
        except Exception as e:
            print(f"   ❌ Error fetching {model_name}: {e}")
            today_portfolios[model_name] = []
    
    # Update the master data with today's snapshot
    all_portfolios[today] = today_portfolios
    
    # Save to JSON
    try:
        PORTFOLIOS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(PORTFOLIOS_LOG, 'w') as f:
            json.dump(all_portfolios, f, indent=2)
        print(f"\n📂 Portfolio holdings saved to: {PORTFOLIOS_LOG}")
    except Exception as e:
        print(f"\n❌ Failed to save portfolio data: {e}")

if __name__ == "__main__":
    log_all_portfolios()
