import os
import pyperclip
import alpaca_trade_api as tradeapi
import yfinance as yf
from dotenv import load_dotenv
from datetime import date

# -------------------------------------------------
# 1. Load API Keys
# -------------------------------------------------
load_dotenv()
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")

# -------------------------------------------------
# 2. Connect to Alpaca (Paper Trading)
# -------------------------------------------------
api = tradeapi.REST(
    ALPACA_KEY,
    ALPACA_SECRET,
    "https://paper-api.alpaca.markets",
    api_version="v2"
)

# -------------------------------------------------
# Macro Data
# -------------------------------------------------
def get_macro_data():
    """
    Fetches standardized macro data:
    - TNX: US 10Y Yield (% change vs prior close)
    - DXY: Dollar Index direction + % change
      (fallback to UUP ETF if index fails)
    """

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

    return tnx_str, dxy_str

# -------------------------------------------------
# Technical Data for Holdings
# -------------------------------------------------
def get_technical_data(symbol: str) -> str:
    """
    Uses last daily close + 20SMA + 50SMA.
    Data source: Yahoo Finance, daily bars only.
    """
    try:
        hist = yf.Ticker(symbol).history(period="6mo")
        if hist is None or len(hist) < 55:
            return "N/A (Insufficient history)"

        closes = hist["Close"].dropna()
        if len(closes) < 55:
            return "N/A (Insufficient close data)"

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

        return (
            f"LastClose ${last_close:.2f} | "
            f"20SMA ${sma_20:.2f} | "
            f"50SMA ${sma_50:.2f} | "
            f"Trend {trend}"
        )
    except Exception as e:
        return f"Data Error ({e})"

# -------------------------------------------------
# Prompt Generator
# -------------------------------------------------
def generate_daily_prompt():
    print(f"⏳ Generating AI Prompt for {date.today()}...")

    try:
        account = api.get_account()
        positions = api.list_positions()
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
            tech = get_technical_data(p.symbol)
            pnl = float(p.unrealized_plpc) * 100
            holdings_lines.append(
                f"- {p.symbol}: Qty {p.qty} | Entry ${float(p.avg_entry_price):.2f} | "
                f"PnL {pnl:.2f}% | Last Close Data: {tech}"
            )
        holdings_txt = "\n".join(holdings_lines)
    else:
        holdings_txt = "No current positions."

    # -------------------------------------------------
    # FINAL PROMPT
    # -------------------------------------------------
    prompt_text = f"""**CURRENT DATE:** {date.today()}

**PORTFOLIO STATUS (ALPACA PAPER):**
- Cash: ${cash:.2f}
- Equity: ${equity:.2f}

**MACRO DATA (STANDARDIZED SOURCE):**
- {tnx_str}
- {dxy_str}

**CURRENT HOLDINGS (STANDARDIZED LAST-CLOSE DATA):**
{holdings_txt}

**ROLE:**
You are a Senior Portfolio Manager running a rules-based experiment.

**GOAL:**
Maximize 3-month risk-adjusted return.
Strictly follow all rules. Skip trades if uncertain.

------------------------------------------------------------
## OUTPUT RULES (MANDATORY)
You MUST output exactly TWO sections:
A) WEEKLY/DAILY NOTES (bullets, max 8)
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
## PHASE 1 — MACRO GATE (NEW BUYS ONLY)
If TNX is up >= +2.00% vs prior close:
- NO NEW BUYS today.
- SELLs and HOLD stop updates are still allowed.

------------------------------------------------------------
## PHASE 2 — SCANNER (MAX ONE BUY)
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
## PHASE 3 — EXECUTION TABLE

| ACTION | TICKER | QTY | TYPE | LIMIT_PRICE | STOP_LOSS | TAKE_PROFIT | REASON |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :--- |

Rules:
- ACTION: BUY, SELL, HOLD, NO_TRADES
- SELL: MARKET, prices = 0.00
- BUY: LIMIT, numeric prices
- HOLD: TYPE=N/A, TAKE_PROFIT=N/A
- Do NOT buy tickers already held

If no actions:
| NO_TRADES | N/A | N/A | N/A | N/A | N/A | N/A | Macro blocked / No valid setups |
"""

    pyperclip.copy(prompt_text)
    print("✅ PROMPT COPIED TO CLIPBOARD")

# -------------------------------------------------
if __name__ == "__main__":
    generate_daily_prompt()
