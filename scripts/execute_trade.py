import os
import pyperclip
import argparse
import io
import csv
import re
import time
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
import pathlib
from datetime import date

import sys
import pathlib
# Add root directory to path to import config
root_dir = pathlib.Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))
import config

# 1. Select Model and Get API
model_info = config.select_model()
api = config.get_alpaca_api(model_info)

# 2. Alpaca Connection (Setup in config.py)
print(f"✅ Connected to Alpaca for {model_info['name']}")

# Execution Logging
execution_logs = []

def log_execution(msg):
    """Prints and stores logging info for file saving."""
    print(msg)
    execution_logs.append(msg)

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
    log_execution("\n" + "=" * 50)
    log_execution(f"📊 ALPACA PRE-FLIGHT STATUS ({model_info['name']})")
    log_execution("=" * 50)
    try:
        account = api.get_account()
        positions = api.list_positions()
        # Fetch ALL orders to include 'held' (bracket OCO legs)
        all_orders = api.list_orders(status="all", limit=50)
        # Filter for active orders (new, accepted, partially_filled, held)
        active_statuses = {"new", "accepted", "partially_filled", "pending_new", "held"}
        orders = [o for o in all_orders if o.status in active_statuses]

        log_execution(f"💰 Equity: ${float(account.equity):,.2f}")
        log_execution(f"💸 Buying Power: ${float(account.buying_power):,.2f}")

        log_execution("\n📂 Current Positions:")
        if not positions:
            log_execution("   (No open positions)")
        else:
            for p in positions:
                log_execution(
                    f"   • {p.symbol}: {p.qty} shares @ ${float(p.avg_entry_price):,.2f} "
                    f"(Current: ${float(p.current_price):,.2f})"
                )

        log_execution("\n📝 Open Orders:")
        if not orders:
            log_execution("   (No open orders)")
        else:
            for o in orders:
                type_str = f"{o.type} {o.side}".upper()
                price_str = (
                    f"@ ${float(o.limit_price):,.2f}"
                    if o.limit_price
                    else (f"Stop @ ${float(o.stop_price):,.2f}" if o.stop_price else "MARKET")
                )
                # Show status with special label for 'held' (OCO leg)
                status_label = "OCO-held" if o.status == "held" else o.status
                log_execution(f"   • {o.symbol}: {type_str} {o.qty} shares {price_str} ({status_label})")

        log_execution("\n" + "=" * 50 + "\n")
    except Exception as e:
        log_execution(f"⚠️ Could not fetch account status: {e}")


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
    log_execution("📋 Parsing Portfolio Recommendation from Clipboard...")
    log_execution("-" * 20)
    log_execution("📋 CLIPBOARD CONTENT:")
    log_execution(text)
    log_execution("-" * 20 + "\n")

    # Note: NO_TRADES rows are handled at the row level during parsing
    # This allows other rows (HOLD, SELL, etc.) to be processed even if NO_TRADES is present

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
                        # Skip NO_TRADES rows but continue processing other rows
                        continue
                    trades.append(trade)

        if trades:
            log_execution(f"🔎 Found {len(trades)} trade(s) (CSV).")
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
                        # Skip NO_TRADES rows but continue processing other rows
                        continue
                    trades.append(trade)

    if trades:
        log_execution(f"🔎 Found {len(trades)} trade(s) (Markdown table).")
        return trades

    # -----------------------------
    # 3) REGEX FALLBACK (last resort)
    # -----------------------------
    pattern = r"(?:^|[,\s|])\s*(BUY|SELL|HOLD|CANCEL)\s*[,\s|]\s*([A-Z]+)\s*[,\s|]\s*([A-Z0-9\.]+)\s*[,\s|]\s*([A-Z\s/]+)\s*[,\s|]\s*(\$?[NA\d\.\-]+)\s*[,\s|]\s*(\$?[NA\d\.\-]+)\s*(?:[,\s|]\s*(\$?[NA\d\.\-]+))?"
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
        log_execution(f"🔎 Found {len(trades)} trade(s) (Regex fallback).")
        return trades

    log_execution("⚠️ No valid trade data found in clipboard.")
    return []


def manage_hold_protection(ticker, stop_loss_price, dry_run=False):
    try:
        qty = int(api.get_position(ticker).qty)
    except Exception:
        log_execution(f"   ⚠️ No open position found for {ticker} to protect.")
        return

    log_execution(f"\n🛡️ SYNCING PROTECTION: {ticker} (Target Stop: ${stop_loss_price:.2f})")

    # Fetch ALL orders to find 'held' stop orders (part of brackets)
    all_orders = api.list_orders(status="all", symbols=[ticker])
    active_statuses = {"new", "accepted", "partially_filled", "pending_new", "held"}
    open_orders = [o for o in all_orders if o.status in active_statuses]

    # Manage existing STOP sell orders (including 'held' ones from brackets)
    stop_orders = [o for o in open_orders if o.side == "sell" and o.type == "stop"]
    
    # Any non-stop SELL orders that are NOT part of a bracket will reserve shares exclusively
    # (If they ARE part of a bracket, they share the reservation with the stop leg in OCO)
    conflicting_sell_orders = [
        o for o in open_orders
        if o.side == "sell" and o.type != "stop" and o.order_class != "bracket"
    ]

    if conflicting_sell_orders:
        for o in conflicting_sell_orders:
            price_str = (
                f"@ ${float(o.limit_price):.2f}" if o.limit_price
                else (f"Stop @ ${float(o.stop_price):.2f}" if o.stop_price else "MARKET")
            )
            log_execution(f"   ⚠️ Conflict: Open standalone SELL order exists for {ticker}: {o.type.upper()} {price_str} ({o.status})")
        log_execution(f"   ⚠️ Skipping STOP placement for {ticker} because shares are reserved by a standalone SELL order.")
        return

    if stop_orders:
        for order in stop_orders:
            current_stop = float(order.stop_price)
            if order.status and "PENDING" in order.status.upper():
                log_execution(f"   ⏳ Stop order update already pending for {ticker} ({order.status}). Skipping.")
                return

            if abs(current_stop - stop_loss_price) < 0.01:
                status_label = "OCO-held" if order.status == "held" else order.status
                log_execution(f"   ✅ Already Protected: Existing stop for {ticker} matches ${current_stop:.2f} ({status_label})")
                return

            log_execution(f"   🔄 Updating: Found stop @ ${current_stop:.2f} ({order.status}). Replacing with ${stop_loss_price:.2f}")
            if dry_run:
                log_execution(f"   [DRY RUN] Would replace stop-loss for {ticker} to ${stop_loss_price:.2f}")
                return

            try:
                api.replace_order(order.id, stop_price=stop_loss_price)
                log_execution(f"   ✅ SUCCESS: Stop-loss update requested for {ticker}.")
                return
            except Exception as e:
                log_execution(f"   ⚠️ Replace failed: {e}. Falling back to Cancel/Re-submit.")
                try:
                    api.cancel_order(order.id)
                    time.sleep(1)
                except Exception as ce:
                    log_execution(f"   ⚠️ Cancel failed: {ce}.")
                    return
    else:
        log_execution(f"   ➕ Missing Protection: No stop-loss found for {ticker}.")

    if dry_run:
        log_execution(f"   [DRY RUN] Would place stop-loss @ ${stop_loss_price:.2f}")
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
        log_execution(f"   ✅ SUCCESS: New stop-loss placed for {ticker} @ ${stop_loss_price:.2f}")
    except Exception as e:
        log_execution(f"   ❌ FAILED to place stop-loss: {e}")

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
        log_execution("🛑 NO_TRADES row encountered. Skipping.")
        return

    if action == "HOLD":
        try:
            stop_price = float(stop_loss_str) if stop_loss_str else None
        except ValueError:
            stop_price = None

        if stop_price:
            manage_hold_protection(ticker, stop_price, dry_run=dry_run)
        else:
            log_execution(f"\n✋ HOLDING: {ticker} (No stop-loss specified)")
        return

    if action == "CANCEL":
        log_execution(f"\n🚫 PROCESSING CANCEL: {ticker}")
        try:
            open_orders = api.list_orders(status="open", symbols=[ticker])
            if not open_orders:
                log_execution(f"   ⚠️ No open orders found for {ticker}. Nothing to cancel.")
                return

            log_execution(f"   🧹 Cancelling {len(open_orders)} open order(s) for {ticker}...")
            for o in open_orders:
                if dry_run:
                    price_str = (
                        f"@ ${float(o.limit_price):.2f}" if o.limit_price
                        else (f"Stop @ ${float(o.stop_price):.2f}" if o.stop_price else "MARKET")
                    )
                    log_execution(f"   [DRY RUN] Would cancel {o.side.upper()} {o.type.upper()} order {price_str}")
                else:
                    api.cancel_order(o.id)
                    log_execution(f"   ✅ Cancelled order {o.id}")

            if not dry_run:
                # Wait for cancellations to process
                time.sleep(1)
                remaining = api.list_orders(status="open", symbols=[ticker])
                if remaining:
                    log_execution(f"   ⚠️ {len(remaining)} order(s) still pending cancellation for {ticker}.")
                else:
                    log_execution(f"   ✅ All orders for {ticker} successfully cancelled.")
        except Exception as e:
            log_execution(f"   ❌ CANCEL FAILED: {e}")
        return

    try:
        if action == "SELL":
            log_execution(f"\n📉 PROCESSING SELL: {ticker}")
            try:
                # --- NEW: Clear any open orders for this ticker first ---
                open_orders = api.list_orders(status="open", symbols=[ticker])
                if open_orders:
                    log_execution(f"   🧹 Clearing {len(open_orders)} open order(s) for {ticker} before selling.")
                    for o in open_orders:
                        if not dry_run:
                            api.cancel_order(o.id)
                        else:
                            log_execution(f"   [DRY RUN] Would cancel order {o.id}")
                    
                    if not dry_run:
                        # Polling loop: Wait up to 10 seconds for orders to clear
                        attempts = 0
                        while attempts < 10:
                            time.sleep(1)
                            remaining = api.list_orders(status="open", symbols=[ticker])
                            if not remaining:
                                break
                            attempts += 1
                            log_execution(f"   ⏳ Waiting for orders to clear ({attempts}/10)...")
                        
                        if attempts == 10:
                            log_execution(f"   ⚠️ WARNING: Orders for {ticker} did not clear in time. Sell might fail.")

                try:
                    api.get_position(ticker)
                except Exception:
                    log_execution(f"   ✅ Position already closed or doesn't exist for {ticker}.")
                    return

                if qty_str and "ALL" in qty_str:
                    if dry_run:
                        log_execution(f"   [DRY RUN] Would close position for {ticker}.")
                    else:
                        api.close_position(ticker)
                else:
                    qty = int(qty_str) if qty_str else 0
                    if qty <= 0:
                        log_execution(f"   ⚠️ Invalid qty for SELL {ticker}: {qty_str}. Skipping.")
                        return

                    if dry_run:
                        log_execution(f"   [DRY RUN] Would submit MARKET sell {qty} {ticker}.")
                    else:
                        api.submit_order(symbol=ticker, qty=qty, side="sell", type="market", time_in_force="day")

                log_execution(f"   ✅ SELL submitted for {ticker}")
            except Exception as e:
                log_execution(f"   ❌ SELL FAILED: {e}")
            return

        if action == "BUY":
            log_execution(f"\n🚀 PROCESSING BUY: {ticker}")

            # --- CHECK 1: Ticker Validity ---
            try:
                asset = api.get_asset(ticker)
                if not asset.tradable:
                    log_execution(f"   ❌ Invalid Ticker: {ticker} is not tradable on Alpaca.")
                    return
            except Exception:
                log_execution(f"   ❌ Invalid Ticker: Could not find {ticker} on Alpaca.")
                return

            # --- CHECK 2: Existing Position (Idempotency) ---
            try:
                pos = api.get_position(ticker)
                log_execution(f"   ⚠️ Already Owned: You currently hold {pos.qty} shares of {ticker}. Skipping execution.")
                return
            except Exception:
                pass

            # --- CHECK 3: Open Buy Order (Idempotency) ---
            open_orders = api.list_orders(status="open", symbols=[ticker])
            buy_orders = [o for o in open_orders if o.side == "buy"]
            if buy_orders:
                log_execution(f"   ⚠️ Pending Order: There is already an open BUY order for {ticker}. Skipping duplicates.")
                return

            qty = int(qty_str) if qty_str else 0
            limit_price = float(limit_price_str) if limit_price_str else 0.0
            if qty <= 0 or limit_price <= 0:
                log_execution(f"   ⚠️ Skipping {ticker}: Missing/invalid Qty or LIMIT_PRICE.")
                return

            stop_price = float(stop_loss_str) if stop_loss_str else None
            tp_price = float(take_profit_str) if take_profit_str else None

            # Guard: STOP_LOSS must be < LIMIT_PRICE if provided
            if stop_price is not None and stop_price >= limit_price:
                log_execution(f"   ❌ Invalid BUY: STOP_LOSS ({stop_price}) >= LIMIT_PRICE ({limit_price}). Skipping.")
                return

            account = api.get_account()
            bp = float(account.buying_power)
            est_cost = qty * limit_price
            msg = f"   Order: {action} {qty} {ticker} @ ${limit_price:.2f}"
            if stop_price or tp_price:
                sl_str = f"SL: ${stop_price:.2f}" if stop_price else "SL: N/A"
                tp_str = f"TP: ${tp_price:.2f}" if tp_price else "TP: N/A"
                msg += f" ({sl_str}, {tp_str})"
            
            msg += f" (Est. Cost: ${est_cost:.2f})"
            log_execution(msg)

            if est_cost > bp:
                log_execution(f"   ⚠️ WARNING: Insufficient Buying Power! (Need ${est_cost:.2f}, Have ${bp:.2f})")
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
                log_execution("   [DRY RUN] Would place buy order.")
            else:
                api.submit_order(**params)
                log_execution("   ✅ SUCCESS: Buy order placed!")
    except Exception as e:
        log_execution(f"   ❌ EXECUTION ERROR for {ticker}: {e}")


def save_execution_log():
    """Saves the recorded execution log to a file."""
    if not execution_logs:
        return

    log_dir = pathlib.Path(f"logs/trades/{date.today()}")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    file_name = f"{model_info['name'].lower().replace(' ', '_')}.md"
    log_file = log_dir / file_name
    
    # Format as markdown
    content = "# Trade Execution Log\n\n"
    content += f"**Model:** {model_info['name']}\n"
    content += f"**Date:** {date.today()}\n\n"
    content += "```text\n"
    content += "\n".join(execution_logs)
    content += "\n```\n"

    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n📂 EXECUTION LOG SAVED TO: {log_file}")
    except Exception as e:
        print(f"\n❌ Failed to save execution log: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print_preflight_status()
    trades = parse_clipboard_trades()
    for t in trades:
        execute_trade(t, dry_run=args.dry_run)
    
    save_execution_log()

