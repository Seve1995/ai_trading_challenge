import os
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta

import sys
import pathlib
# Add root directory to path to import config
root_dir = pathlib.Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))
import config

# 1. Select Model and Get API
model_info = config.select_model()
api = config.get_alpaca_api(model_info)

def get_history():
    print("\n" + "="*60)
    print(f"📜 ALPACA ACCOUNT ACTIVITY ({model_info['name']}) - Last 24 Hours")
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
