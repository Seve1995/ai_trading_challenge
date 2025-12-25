import os
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta

# 1. Load API Keys
load_dotenv()
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")

# 2. Connect to Alpaca
BASE_URL = 'https://paper-api.alpaca.markets'
api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, BASE_URL, api_version='v2')

def get_history():
    print("\n" + "="*60)
    print("📜 ALPACA ACCOUNT ACTIVITY (Last 24 Hours)")
    print("="*60)
    
    try:
        # 1. Check Fills (Actual Trades)
        activities = api.get_activities(activity_types=['FILL'])
        
        if not activities:
            print("No recent fills found.")
        else:
            print("✅ COMPLETED TRADES (Fills):")
            for act in activities:
                # Handle possible Timestamp or String
                ts = act.transaction_time
                if hasattr(ts, 'strftime'):
                    time_str = ts.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    time_str = str(ts)
                print(f"   • {time_str} | {act.side.upper()} {act.qty} {act.symbol} @ ${float(act.price):,.2f}")

        # 2. Check Order History (to see cancellations/failures)
        print("\n📝 RECENT ORDER HISTORY:")
        orders = api.list_orders(status='all', limit=10)
        if not orders:
            print("   (No recent orders)")
        else:
            for o in orders:
                type_str = f"{o.type} {o.side}".upper()
                price_str = f"@ ${float(o.limit_price):,.2f}" if getattr(o, 'limit_price', None) else (f"Stop @ ${float(o.stop_price):,.2f}" if getattr(o, 'stop_price', None) else "MARKET")
                print(f"   • {o.symbol}: {type_str} {o.qty} shares {price_str} | Status: {o.status}")
                
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"⚠️ Error fetching history: {e}")

if __name__ == "__main__":
    get_history()
