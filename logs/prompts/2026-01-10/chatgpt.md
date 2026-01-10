**CURRENT DATE:** 2026-01-10

**PORTFOLIO STATUS (ALPACA PAPER - ChatGPT):**
- Cash: $758.61
- Equity: $939.35

**MACRO DATA (STANDARDIZED SOURCE):**
- TNX: 4.17 (-0.29% vs prior close)
- DXY: UP (+0.20% vs prior close, source=DX-Y.NYB)

**CURRENT HOLDINGS (STANDARDIZED LAST-CLOSE DATA):**
- NVAX: Qty 14 | Entry $7.44 | PnL -2.28% | Last Close Data: LastClose $7.27 | 20SMA $6.90 | 50SMA $7.02 | Trend ABOVE_20&50
- UAA: Qty 14 | Entry $5.78 | PnL -2.42% | Last Close Data: LastClose $5.64 | 20SMA $4.89 | 50SMA $4.66 | Trend ABOVE_20&50

**PENDING ORDERS:**
- SELL UAA 14 (LIMIT) Lim: $8.00
- SELL NVAX 14 (LIMIT) Lim: $10.00

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
- Max $risk = $14.09
- STOP_LOSS MUST be strictly below LIMIT_PRICE
- Qty = floor(MaxRisk / (Entry − Stop))
- If Qty < 1 → NO BUY

ORDER:
- BUY must be LIMIT
- BUY must include STOP_LOSS and TAKE_PROFIT
- TAKE_PROFIT ≥ 2R
- If numbers are uncertain → NO BUY

------------------------------------------------------------
## PHASE 4 — EXECUTION TABLE

| ACTION | TICKER | QTY | TYPE | LIMIT_PRICE | STOP_LOSS | TAKE_PROFIT | REASON |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :--- |

Rules:
- ACTION: BUY, SELL, HOLD, CANCEL, NO_TRADES
- SELL: MARKET, prices = 0.00
- BUY: LIMIT, numeric prices
- HOLD: TYPE=N/A, TAKE_PROFIT=N/A
- CANCEL: TYPE=N/A, all prices = N/A (cancels all open orders for ticker)
- Do NOT buy tickers already held

If no actions:
| NO_TRADES | N/A | N/A | N/A | N/A | N/A | N/A | Macro blocked / No valid setups |
