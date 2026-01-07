import sys
import json
import pathlib
from datetime import datetime
import os

# Add root directory to path to import config
root_dir = pathlib.Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))
import config

# Configuration
TRANSACTIONS_LOG = config.LOGS_DIR / "transactions.json"

def log_transactions():
    """Fetches closed orders (transactions) for all models."""
    print(f"\n📂 Logging Transactions...")
    
    all_transactions = {}
    
    for key, info in config.MODELS.items():
        model_name = info['name']
        print(f"   ... Fetching orders for {model_name} ...")
        
        try:
            api = config.get_alpaca_api(info)
            # Fetch closed orders, most recent first
            orders = api.list_orders(status='closed', limit=50) 
            
            # Filter for filled orders and format
            model_txs = []
            for order in orders:
                if order.status == 'filled':
                    tx = {
                        "symbol": order.symbol,
                        "side": order.side,
                        "qty": float(order.qty) if order.qty else 0,
                        "price": float(order.filled_avg_price) if order.filled_avg_price else 0,
                        "timestamp": order.filled_at.isoformat() if order.filled_at else order.created_at.isoformat(),
                        "type": order.type,
                        "id": order.id
                    }
                    model_txs.append(tx)
            
            all_transactions[model_name] = model_txs
            print(f"   ✅ {model_name}: {len(model_txs)} transaction(s)")
            
        except Exception as e:
            print(f"   ❌ Error fetching transactions for {model_name}: {e}")
            all_transactions[model_name] = []

    # Save to JSON
    try:
        TRANSACTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(TRANSACTIONS_LOG, 'w') as f:
            json.dump(all_transactions, f, indent=2)
        print(f"\n📂 Transactions saved to: {TRANSACTIONS_LOG}")
    except Exception as e:
        print(f"\n❌ Failed to save transaction data: {e}")

if __name__ == "__main__":
    log_transactions()
