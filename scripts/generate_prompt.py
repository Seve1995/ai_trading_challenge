import os
import pyperclip
import alpaca_trade_api as tradeapi
import yfinance as yf
from dotenv import load_dotenv
from datetime import date
import json
import pathlib

import sys
import pathlib
# Add root directory to path to import config
root_dir = pathlib.Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))
import config

# -------------------------------------------------
# 1. Select Model and Get API
# -------------------------------------------------
model_info = config.select_model()
api = config.get_alpaca_api(model_info)

# Macro Data
MACRO_CACHE_DIR = config.MACRO_CACHE_DIR

def get_macro_data():
    """
    Fetches standardized macro data. Caches results for the day to avoid redundant calls.
    """
    today_str = date.today().isoformat()
    cache_file = MACRO_CACHE_DIR / f"{today_str}.json"

    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                print(f"   🏠 Loaded Macro Data from cache ({today_str})")
                return data["tnx"], data["dxy"]
        except Exception as e:
            print(f"⚠️ Cache read error: {e}. Re-fetching...")

    # --- TNX ---
    try:
        tnx = yf.Ticker("^TNX").history(period="5d")
        if len(tnx) >= 2:
            prev = float(tnx["Close"].iloc[-2])
            last = float(tnx["Close"].iloc[-1])
            pct = ((last - prev) / prev) * 100 if prev else 0.0
            tnx_str = f"TNX: {last:.2f} ({pct:+.2f}% vs prior close)"
        else:
            tnx_str = "TNX: Not enough data"
    except Exception as e:
        tnx_str = f"TNX: Data Error ({e})"

    # --- DXY (fallback to UUP) ---
    try:
        source = "DX-Y.NYB"
        dxy = yf.Ticker(source).history(period="5d")

        if dxy is None or dxy.empty or len(dxy) < 2:
            source = "UUP"
            dxy = yf.Ticker(source).history(period="5d")

        if dxy is not None and not dxy.empty and len(dxy) >= 2:
            col = "Adj Close" if "Adj Close" in dxy.columns else "Close"
            prev = float(dxy[col].iloc[-2])
            last = float(dxy[col].iloc[-1])

            direction = "UP" if last > prev else ("DOWN" if last < prev else "FLAT")
            pct = ((last - prev) / prev) * 100 if prev else 0.0

            dxy_str = f"DXY: {direction} ({pct:+.2f}% vs prior close, source={source})"
        else:
            dxy_str = "DXY: Not enough data"
    except Exception as e:
        dxy_str = f"DXY: Data Error ({e})"

    # Save to cache ONLY if data is valid (not errors)
    tnx_valid = "Not enough data" not in tnx_str and "Data Error" not in tnx_str
    dxy_valid = "Not enough data" not in dxy_str and "Data Error" not in dxy_str
    
    if tnx_valid and dxy_valid:
        try:
            MACRO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump({"tnx": tnx_str, "dxy": dxy_str}, f)
            print(f"   💾 Macro Data cached for {today_str}")
        except Exception as e:
            print(f"⚠️ Cache write error: {e}")
    else:
        print(f"   ⚠️ Macro Data NOT cached (errors detected, will retry next run)")

    return tnx_str, dxy_str

# -------------------------------------------------
# Technical Data for Holdings
# -------------------------------------------------
def get_technical_data(symbol: str) -> tuple:
    """
    Uses last daily close + 20SMA + 50SMA.
    Data source: Yahoo Finance, daily bars only.
    Returns: (tech_string, last_close) tuple
    """
    try:
        hist = yf.Ticker(symbol).history(period="6mo")
        if hist is None or len(hist) < 55:
            return "N/A (Insufficient history)", None

        closes = hist["Close"].dropna()
        if len(closes) < 55:
            return "N/A (Insufficient close data)", None

        last_close = float(closes.iloc[-1])
        sma_20 = closes.rolling(20).mean().iloc[-1]
        sma_50 = closes.rolling(50).mean().iloc[-1]

        above_20 = last_close > sma_20
        above_50 = last_close > sma_50

        if above_20 and above_50:
            trend = "ABOVE_20&50"
        elif not above_50:
            trend = "BELOW_50"
        else:
            trend = "BELOW_20"

        tech_str = (
            f"LastClose ${last_close:.2f} | "
            f"20SMA ${sma_20:.2f} | "
            f"50SMA ${sma_50:.2f} | "
            f"Trend {trend}"
        )
        return tech_str, last_close
    except Exception as e:
        return f"Data Error ({e})", None

# -------------------------------------------------
# Prompt Generator
# -------------------------------------------------
def generate_daily_prompt():
    print(f"⏳ Generating {model_info['name']} AI Prompt for {date.today()}...")

    try:
        account = api.get_account()
        positions = api.list_positions()
        orders = api.list_orders(status='open')
    except Exception as e:
        print(f"❌ Alpaca Error: {e}")
        return

    cash = float(account.cash)
    equity = float(account.equity)
    max_risk = equity * 0.015

    # Macro
    print("   ... Fetching Macro Data ...")
    tnx_str, dxy_str = get_macro_data()

    # Holdings
    holdings_lines = []
    if positions:
        print(f"   ... Fetching Technicals for {len(positions)} positions ...")
        for p in positions:
            tech_str, last_close = get_technical_data(p.symbol)
            entry_price = float(p.avg_entry_price)
            # Calculate PnL from entry price vs last close (more reliable than Alpaca's unrealized_plpc)
            if last_close and entry_price > 0:
                pnl = ((last_close - entry_price) / entry_price) * 100
            else:
                pnl = float(p.unrealized_plpc) * 100  # fallback to Alpaca's value
            holdings_lines.append(
                f"- {p.symbol}: Qty {p.qty} | Entry ${entry_price:.2f} | "
                f"PnL {pnl:.2f}% | Last Close Data: {tech_str}"
            )
        holdings_txt = "\n".join(holdings_lines)
    else:
        holdings_txt = "No current positions."

    # Pending Orders
    orders_lines = []
    if orders:
        print(f"   ... Found {len(orders)} pending orders ...")
        for o in orders:
            # Format: SIDE SYMBOL QTY @ LIMIT/STOP PRICE (TYPE)
            details = []
            if o.limit_price: details.append(f"Lim: ${float(o.limit_price):.2f}")
            if o.stop_price: details.append(f"Stop: ${float(o.stop_price):.2f}")
            price_info = " | ".join(details)
            orders_lines.append(
                f"- {o.side.upper()} {o.symbol} {o.qty} ({o.type.upper()}) {price_info}"
            )
        orders_txt = "\n".join(orders_lines)
    else:
        orders_txt = "No pending orders."

    # -------------------------------------------------
    # FINAL PROMPT
    # -------------------------------------------------
    prompt_text = f"""**CURRENT DATE:** {date.today()}

**PORTFOLIO STATUS (ALPACA PAPER - {model_info['name']}):**
- Cash: ${cash:.2f}
- Equity: ${equity:.2f}

**MACRO DATA (STANDARDIZED SOURCE):**
- {tnx_str}
- {dxy_str}

**CURRENT HOLDINGS (STANDARDIZED LAST-CLOSE DATA):**
{holdings_txt}

**PENDING ORDERS:**
{orders_txt}

**ROLE:**
You are a Senior Portfolio Manager running a rules-based experiment.

**GOAL:**
Maximize 3-month risk-adjusted return.
Strictly follow all rules. Skip trades if uncertain.

------------------------------------------------------------
## OUTPUT RULES (MANDATORY)
You MUST output exactly TWO sections:
A) DAILY NOTES (bullets, max 8)
B) EXECUTION_TABLE (the ONLY table)
No extra text after the table.

------------------------------------------------------------
## PHASE 0 — PORTFOLIO AUDIT (FIRST PRIORITY)
For EACH holding:
- Use Last Close Data (daily bars only).
- Check overnight news and catalyst validity.

SELL if:
- Major negative news, catalyst invalidated, OR
- Trend shows BELOW_50 AND thesis weakened.

HOLD if not selling:
- You MUST output a HOLD row.
- STOP_LOSS required if a technical invalidation exists, else N/A.
- IMPORTANT: For HOLD positions, do NOT propose TAKE_PROFIT or limit sell orders.
  Risk management for existing holdings is STOP_LOSS ONLY.

------------------------------------------------------------
## PHASE 1 — PENDING ORDER REVIEW
For EACH pending order:
- Evaluate if the order is still valid.

CANCEL if:
- Order is stale (price moved >10% away from limit).
- Thesis invalidated or catalyst passed.
- You are about to SELL the same ticker (existing sell orders are auto-cancelled).

KEEP (do not output) if order is still valid and should remain open.

------------------------------------------------------------
## PHASE 2 — MACRO GATE (NEW BUYS ONLY)
If TNX is up >= +2.00% vs prior close:
- NO NEW BUYS today.
- SELLs, CANCELs, and HOLD stop updates are still allowed.

------------------------------------------------------------
## PHASE 3 — SCANNER (MAX ONE BUY)
Only if Macro allows:

UNIVERSE:
- US-listed common stock
- Price $3–$50
- Tradable on Alpaca
- Avoid reverse splits, halts, bankruptcy risk

SETUP:
- Catalyst in 30–45 days
- Price ABOVE 20SMA and 50SMA
- Short interest > 15% (cite source + date)
- Clear technical stop level

RISK:
- Max $risk = ${max_risk:.2f}
- STOP_LOSS MUST be strictly below LIMIT_PRICE
- Qty = floor(MaxRisk / (Entry − Stop))
- If Qty < 1 → NO BUY

ORDER:
- BUY must be LIMIT
- BUY must include STOP_LOSS and TAKE_PROFIT
- TAKE_PROFIT ≥ 2R
- If numbers are uncertain → NO BUY

------------------------------------------------------------
## PHASE 4 — EXECUTION TABLE (STRICT FORMAT)

| ACTION | TICKER | QTY | TYPE | LIMIT_PRICE | STOP_LOSS | TAKE_PROFIT | REASON |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :--- |

RULES FOR NUMERIC COLUMNS (STRICT):
1. **QTY**: Must be a clean whole integer.
2. **PRICES** (LIMIT_PRICE, STOP_LOSS, TAKE_PROFIT): Must be RAW NUMBERS ONLY.
3. **NO SYMBOLS**: Do NOT include '$' or ',' in the table.
4. **NO TEXT**: Do NOT add explanatory text (like "@ $7.85") inside numeric columns.
5. **N/A**: Use 'N/A' for any field that is unknown or not applicable.

ACTION VALUES: BUY, SELL, HOLD, CANCEL, NO_TRADES

If no actions are taken, use:
| NO_TRADES | N/A | N/A | N/A | N/A | N/A | N/A | Macro blocked / No valid setups |
"""

    pyperclip.copy(prompt_text)
    print("✅ PROMPT COPIED TO CLIPBOARD")

    # -------------------------------------------------
    # LOG PROMPT TO FILE
    # -------------------------------------------------
    log_dir = pathlib.Path(f"logs/prompts/{date.today()}")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    file_name = f"{model_info['name'].lower().replace(' ', '_')}.md"
    log_file = log_dir / file_name
    
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(prompt_text)
        print(f"📝 PROMPT SAVED TO: {log_file}")
    except Exception as e:
        print(f"❌ Failed to save prompt to file: {e}")

# -------------------------------------------------
if __name__ == "__main__":
    generate_daily_prompt()
