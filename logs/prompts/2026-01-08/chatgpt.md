**CURRENT DATE:** 2026-01-08

**PORTFOLIO STATUS (ALPACA PAPER - ChatGPT):**
- Cash: $851.44
- Equity: $995.31

**MACRO DATA (STANDARDIZED SOURCE):**
- TNX: 4.18 (+0.99% vs prior close)
- DXY: UP (+0.15% vs prior close, source=DX-Y.NYB)

**CURRENT HOLDINGS (STANDARDIZED LAST-CLOSE DATA):**
- AQST: Qty 23 | Entry $6.45 | PnL -3.02% | Last Close Data: LastClose $6.26 | 20SMA $6.11 | 50SMA $6.08 | Trend ABOVE_20&50

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
- Max $risk = $14.93
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
