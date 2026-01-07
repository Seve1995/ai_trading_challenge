import sys
import json
import pathlib
from datetime import datetime

# Add root directory to path to import config
root_dir = pathlib.Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))
import config

# Configuration
import yfinance as yf

# Configuration
PORTFOLIOS_LOG = config.LOGS_DIR / "portfolios.json"
MACRO_CACHE_DIR = config.LOGS_DIR / "macro_cache"
TICKER_METADATA_CACHE = MACRO_CACHE_DIR / "ticker_metadata.json"

def get_ticker_metadata(ticker):
    """Fetches sector and industry data from yfinance with caching."""
    # Ensure cache dir exists
    MACRO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    cache = {}
    if TICKER_METADATA_CACHE.exists():
        try:
            with open(TICKER_METADATA_CACHE, 'r') as f:
                cache = json.load(f)
        except:
            pass
            
    if ticker in cache:
        return cache[ticker]
        
    # Fetch from yfinance
    try:
        print(f"      > Fetching metadata for {ticker}...")
        tk = yf.Ticker(ticker)
        info = tk.info
        data = {
            "sector": info.get('sector', 'Unknown'),
            "industry": info.get('industry', 'Unknown')
        }
        cache[ticker] = data
        
        # Save cache
        with open(TICKER_METADATA_CACHE, 'w') as f:
            json.dump(cache, f)
            
        return data
    except Exception as e:
        print(f"      ! Error fetching metadata for {ticker}: {e}")
        return {"sector": "Unknown", "industry": "Unknown"}

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
            
            # Fetch Account Data (Equity & Cash)
            account = api.get_account()
            
            # Fetch Positions
            positions = api.list_positions()
            
            holdings = []
            for pos in positions:
                metadata = get_ticker_metadata(pos.symbol)
                holding = {
                    "ticker": pos.symbol,
                    "qty": float(pos.qty),
                    "avg_cost": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_pl_pct": float(pos.unrealized_plpc) * 100,
                    "sector": metadata['sector'],
                    "industry": metadata['industry']
                }
                holdings.append(holding)
            
            # Structure the data with top-level account info
            today_portfolios[model_name] = {
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "positions": holdings
            }
            
            if holdings:
                print(f"   ✅ {model_name}: {len(holdings)} position(s) | Equity: ${float(account.equity):.2f}")
            else:
                print(f"   ✅ {model_name}: All Cash | Equity: ${float(account.equity):.2f}")
                
        except Exception as e:
            print(f"   ❌ Error fetching {model_name}: {e}")
            today_portfolios[model_name] = {
                "equity": 0, "cash": 0, "buying_power": 0, "positions": []
            }
    
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
