import os
import pyperclip
import argparse
import io
import csv
import re
import time
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi

# 1. Load API Keys
load_dotenv()
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")

# 2. Connect to Alpaca (Paper Trading)
BASE_URL = "https://paper-api.alpaca.markets"
api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, BASE_URL, api_version="v2")

HEADER_MAP = {
    "TICKER": ["TICKER", "TICK", "SYMBOL"],
    "ACTION": ["ACTION", "ACT"],
    "QTY": ["QTY", "QUANTITY", "AMOUNT", "SIZE"],
    "TYPE": ["TYPE", "ORDER TYPE"],
    "LIMIT_PRICE": ["LIMIT_PRICE", "LIMIT PRICE", "LIMIT", "PRICE"],
    "STOP_LOSS": ["STOP_LOSS", "STOP LOSS", "STOP", "SL"],
    "TAKE_PROFIT": ["TAKE_PROFIT", "TAKE PROFIT", "TP", "TARGET"],
    # Optional / ignored by executor if present
    "REASON": ["REASON", "WHY", "RATIONALE"],
}


def clean_val(val):
    """
    Normalizes values coming from clipboard parsing.
    Returns None for empty/N/A fields.
    """
    if val is None:
        return None
    s = str(val).strip()
    s_up = s.upper().replace("$", "").replace(",", "").strip()
    if s_up in ["N/A", "NONE", "", "-"]:
        return None
    return s_up


def map_headers(row_keys):
    """
    Maps whatever headers the AI outputs to the canonical headers we support.
    Unknown columns are ignored.
    """
    mapped = {}
    for canonical, variations in HEADER_MAP.items():
        for var in variations:
            for rk in row_keys:
                if var == rk.upper().strip():
                    mapped[canonical] = rk
                    break
            if canonical in mapped:
                break
    return mapped


def print_preflight_status():
    """Print current account status, positions, and open orders before starting."""
    try:
        account = api.get_account()
        positions = api.list_positions()
        orders = api.list_orders(status="open")

        print("\n" + "=" * 50)
        print("📊 ALPACA PRE-FLIGHT STATUS")
        print("=" * 50)
        print(f"💰 Equity: ${float(account.equity):,.2f}")
        print(f"💸 Buying Power: ${float(account.buying_power):,.2f}")

        print("\n📂 Current Positions:")
        if not positions:
            print("   (No open positions)")
        else:
            for p in positions:
                print(
                    f"   • {p.symbol}: {p.qty} shares @ ${float(p.avg_entry_price):,.2f} "
                    f"(Current: ${float(p.current_price):,.2f})"
                )

        print("\n📝 Open Orders:")
        if not orders:
            print("   (No open orders)")
        else:
            for o in orders:
                type_str = f"{o.type} {o.side}".upper()
                price_str = (
                    f"@ ${float(o.limit_price):,.2f}"
                    if o.limit_price
                    else (f"Stop @ ${float(o.stop_price):,.2f}" if o.stop_price else "MARKET")
                )
                print(f"   • {o.symbol}: {type_str} {o.qty} shares {price_str} ({o.status})")

        print("\n" + "=" * 50 + "\n")
    except Exception as e:
        print(f"⚠️ Could not fetch account status: {e}")


def parse_clipboard_trades():
    """
    Parses the clipboard for an execution table.
    Supports:
      1) CSV output (Gemini-style)
      2) Markdown pipe table (ChatGPT/Claude-style)
      3) Regex fallback (last resort)
    Always returns a list (possibly empty).
    """
    text = pyperclip.paste().strip()
    print("📋 Analyzing Clipboard Strategy...\n")

    # Quick NO_TRADES detection (text-level)
    if "NO_TRADES" in text.upper() or "NO TRADES" in text.upper():
        print("🛑 AI Signal: NO TRADES TODAY.")
        return []

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    trades = []

    # -----------------------------
    # 1) CSV MODE (Gemini-style)
    # -----------------------------
    header_line_idx = None
    for i, line in enumerate(lines):
        if "ACTION" in line.upper() and "TICKER" in line.upper() and "," in line:
            header_line_idx = i
            break

    if header_line_idx is not None:
        csv_data = "\n".join(lines[header_line_idx:])
        f = io.StringIO(csv_data)
        reader = csv.DictReader(f)
        if reader.fieldnames:
            h_map = map_headers(reader.fieldnames)
            for row in reader:
                trade = {canonical: row.get(original) for canonical, original in h_map.items()}
                if trade.get("ACTION") and trade.get("TICKER"):
                    if clean_val(trade.get("ACTION")) == "NO_TRADES":
                        print("🛑 AI Signal: NO TRADES TODAY (CSV row).")
                        return []
                    trades.append(trade)

        if trades:
            print(f"🔎 Found {len(trades)} trade(s) (CSV).")
            return trades

    # -----------------------------
    # 2) MARKDOWN PIPE TABLE MODE
    # -----------------------------
    processed_lines = []
    for line in lines:
        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            processed_lines.append(",".join(parts))
        else:
            processed_lines.append(line)

    header_idx = -1
    for i, line in enumerate(processed_lines):
        if any(h in line.upper() for h in ["ACTION", "TICKER"]):
            header_idx = i
            break

    if header_idx != -1:
        csv_data = "\n".join(processed_lines[header_idx:])
        f = io.StringIO(csv_data)
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if fieldnames:
            h_map = map_headers(fieldnames)
            for row in reader:
                trade = {canonical: row.get(original) for canonical, original in h_map.items()}
                if trade.get("ACTION") and trade.get("TICKER"):
                    if clean_val(trade.get("ACTION")) == "NO_TRADES":
                        print("🛑 AI Signal: NO TRADES TODAY (table row).")
                        return []
                    trades.append(trade)

    if trades:
        print(f"🔎 Found {len(trades)} trade(s) (Markdown table).")
        return trades

    # -----------------------------
    # 3) REGEX FALLBACK (last resort)
    # -----------------------------
    pattern = r"(?:^|[,\s|])\s*(BUY|SELL|HOLD)\s*[,\s|]\s*([A-Z]+)\s*[,\s|]\s*([A-Z0-9\.]+)\s*[,\s|]\s*([A-Z\s/]+)\s*[,\s|]\s*(\$?[NA\d\.\-]+)\s*[,\s|]\s*(\$?[NA\d\.\-]+)\s*(?:[,\s|]\s*(\$?[NA\d\.\-]+))?"
    matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
    for m in matches:
        trades.append(
            {
                "ACTION": m[0].upper(),
                "TICKER": m[1].upper(),
                "QTY": m[2],
                "TYPE": m[3].upper(),
                "LIMIT_PRICE": m[4],
                "STOP_LOSS": m[5],
                "TAKE_PROFIT": m[6] if len(m) > 6 else None,
            }
        )

    if trades:
        print(f"🔎 Found {len(trades)} trade(s) (Regex fallback).")
        return trades

    print("⚠️ No valid trade data found in clipboard.")
    return []


def manage_hold_protection(ticker, stop_loss_price, dry_run=False):
    try:
        qty = int(api.get_position(ticker).qty)
    except Exception:
        print(f"   ⚠️ No open position found for {ticker} to protect.")
        return

    print(f"\n🛡️ SYNCING PROTECTION: {ticker} (Target Stop: ${stop_loss_price:.2f})")

    open_orders = api.list_orders(status="open", symbols=[ticker])

    # Any non-stop SELL orders will reserve shares (e.g., limit sell take-profit)
    conflicting_sell_orders = [
        o for o in open_orders
        if o.side == "sell" and o.type != "stop"
    ]
    if conflicting_sell_orders:
        # Don’t try to place a stop—Alpaca will reject due to reserved qty.
        for o in conflicting_sell_orders:
            price_str = (
                f"@ ${float(o.limit_price):.2f}" if o.limit_price
                else (f"Stop @ ${float(o.stop_price):.2f}" if o.stop_price else "MARKET")
            )
            print(f"   ⚠️ Conflict: Open SELL order exists for {ticker}: {o.type.upper()} {price_str} ({o.status})")
        print(f"   ⚠️ Skipping STOP placement for {ticker} because shares are reserved by an open SELL order.")
        return

    # Manage existing STOP sell orders
    stop_orders = [o for o in open_orders if o.type == "stop" and o.side == "sell"]

    if stop_orders:
        for order in stop_orders:
            current_stop = float(order.stop_price)
            # If a replace is already pending, don't spam more actions
            if order.status and "PENDING" in order.status.upper():
                print(f"   ⏳ Stop order update already pending for {ticker} ({order.status}). Skipping for now.")
                return

            if abs(current_stop - stop_loss_price) < 0.01:
                print(f"   ✅ Already Protected: Existing stop for {ticker} matches ${current_stop:.2f}")
                return

            print(f"   🔄 Updating: Found stop @ ${current_stop:.2f}. Replacing with ${stop_loss_price:.2f}")
            if dry_run:
                print(f"   [DRY RUN] Would replace stop-loss for {ticker} to ${stop_loss_price:.2f}")
                return

            try:
                api.replace_order(order.id, stop_price=stop_loss_price)
                print(f"   ✅ SUCCESS: Stop-loss update requested for {ticker}.")
                return
            except Exception as e:
                print(f"   ⚠️ Replace failed: {e}. Falling back to Cancel/Re-submit.")
                try:
                    api.cancel_order(order.id)
                    time.sleep(1)
                except Exception as ce:
                    print(f"   ⚠️ Cancel failed: {ce}.")
                    return
    else:
        print(f"   ➕ Missing Protection: No stop-loss found for {ticker}.")

    if dry_run:
        print(f"   [DRY RUN] Would place stop-loss @ ${stop_loss_price:.2f}")
        return

    try:
        api.submit_order(
            symbol=ticker,
            qty=qty,
            side="sell",
            type="stop",
            time_in_force="gtc",
            stop_price=stop_loss_price,
        )
        print(f"   ✅ SUCCESS: New stop-loss placed for {ticker} @ ${stop_loss_price:.2f}")
    except Exception as e:
        print(f"   ❌ FAILED to place stop-loss: {e}")

def execute_trade(trade, dry_run=False):
    action = clean_val(trade.get("ACTION"))
    ticker = clean_val(trade.get("TICKER"))
    qty_str = clean_val(trade.get("QTY"))
    limit_price_str = clean_val(trade.get("LIMIT_PRICE"))
    stop_loss_str = clean_val(trade.get("STOP_LOSS"))
    take_profit_str = clean_val(trade.get("TAKE_PROFIT"))

    if not action:
        return

    # Ignore NO_TRADES if it slips through
    if action == "NO_TRADES":
        print("🛑 NO_TRADES row encountered. Skipping.")
        return

    if action == "HOLD":
        try:
            stop_price = float(stop_loss_str) if stop_loss_str else None
        except ValueError:
            stop_price = None

        if stop_price:
            manage_hold_protection(ticker, stop_price, dry_run=dry_run)
        else:
            print(f"\n✋ HOLDING: {ticker} (No stop-loss specified)")
        return

    try:
        if action == "SELL":
            print(f"\n📉 PROCESSING SELL: {ticker}")
            try:
                try:
                    api.get_position(ticker)
                except Exception:
                    print(f"   ✅ Position already closed or doesn't exist for {ticker}.")
                    return

                if qty_str and "ALL" in qty_str:
                    if dry_run:
                        print(f"   [DRY RUN] Would close position for {ticker}.")
                    else:
                        api.close_position(ticker)
                else:
                    qty = int(qty_str) if qty_str else 0
                    if qty <= 0:
                        print(f"   ⚠️ Invalid qty for SELL {ticker}: {qty_str}. Skipping.")
                        return

                    if dry_run:
                        print(f"   [DRY RUN] Would submit MARKET sell {qty} {ticker}.")
                    else:
                        api.submit_order(symbol=ticker, qty=qty, side="sell", type="market", time_in_force="day")

                print(f"   ✅ SELL submitted for {ticker}")
            except Exception as e:
                print(f"   ❌ SELL FAILED: {e}")
            return

        if action == "BUY":
            print(f"\n🚀 PROCESSING BUY: {ticker}")

            # --- CHECK 1: Ticker Validity ---
            try:
                asset = api.get_asset(ticker)
                if not asset.tradable:
                    print(f"   ❌ Invalid Ticker: {ticker} is not tradable on Alpaca.")
                    return
            except Exception:
                print(f"   ❌ Invalid Ticker: Could not find {ticker} on Alpaca.")
                return

            # --- CHECK 2: Existing Position (Idempotency) ---
            try:
                pos = api.get_position(ticker)
                print(f"   ⚠️ Already Owned: You currently hold {pos.qty} shares of {ticker}. Skipping execution.")
                return
            except Exception:
                pass

            # --- CHECK 3: Open Buy Order (Idempotency) ---
            open_orders = api.list_orders(status="open", symbols=[ticker])
            buy_orders = [o for o in open_orders if o.side == "buy"]
            if buy_orders:
                print(f"   ⚠️ Pending Order: There is already an open BUY order for {ticker}. Skipping duplicates.")
                return

            qty = int(qty_str) if qty_str else 0
            limit_price = float(limit_price_str) if limit_price_str else 0.0
            if qty <= 0 or limit_price <= 0:
                print(f"   ⚠️ Skipping {ticker}: Missing/invalid Qty or LIMIT_PRICE.")
                return

            stop_price = float(stop_loss_str) if stop_loss_str else None
            tp_price = float(take_profit_str) if take_profit_str else None

            # Guard: STOP_LOSS must be < LIMIT_PRICE if provided
            if stop_price is not None and stop_price >= limit_price:
                print(f"   ❌ Invalid BUY: STOP_LOSS ({stop_price}) >= LIMIT_PRICE ({limit_price}). Skipping.")
                return

            account = api.get_account()
            bp = float(account.buying_power)
            est_cost = qty * limit_price
            print(f"   Order: BUY {qty} {ticker} @ ${limit_price:.2f} (Est. Cost: ${est_cost:.2f})")

            if est_cost > bp:
                print(f"   ⚠️ WARNING: Insufficient Buying Power! (Need ${est_cost:.2f}, Have ${bp:.2f})")
                if not dry_run:
                    return

            params = {
                "symbol": ticker,
                "qty": qty,
                "side": "buy",
                "type": "limit",
                "time_in_force": "gtc",
                "limit_price": limit_price,
            }

            if stop_price and tp_price:
                params.update(
                    {
                        "order_class": "bracket",
                        "stop_loss": {"stop_price": stop_price},
                        "take_profit": {"limit_price": tp_price},
                    }
                )
            elif stop_price:
                params.update({"order_class": "oto", "stop_loss": {"stop_price": stop_price}})
            else:
                params["order_class"] = "simple"

            if dry_run:
                print("   [DRY RUN] Would place buy order.")
            else:
                api.submit_order(**params)
                print("   ✅ SUCCESS: Buy order placed!")
    except Exception as e:
        print(f"   ❌ EXECUTION ERROR for {ticker}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print_preflight_status()
    trades = parse_clipboard_trades()
    for t in trades:
        execute_trade(t, dry_run=args.dry_run)

