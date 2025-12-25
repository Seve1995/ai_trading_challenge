---
description: How to execute robust and safe trades using the Alpaca automation scripts.
---

# Robust Trading Workflow

To avoid missing position changes or duplicate executions, follow this standardized workflow:

### 1. Refresh Local State
Before generating a prompt for the AI, ensure your scripts are up to date and your API keys are active.
// turbo
```bash
.\.venv\Scripts\python generate_prompt.py
```
*   **Why**: This fetches your *actual* current holdings from Alpaca, ensuring the AI doesn't hallucinate positions you've already sold.

### 2. Verify with Pre-flight Summary
Before pasting any trade data into the prompt, run a dry-run of the execution script to see your current "Situation Report":
// turbo
```bash
.\.venv\Scripts\python execute_trade.py --dry-run
```
*   **Check for**: 
    - **Open Orders**: Are there pending stop-losses or limit sells that might interfere?
    - **Buying Power**: Do you have enough cash for new buys?
    - **WOLF/Missing Tickers**: If a stock isn't in the "Current Positions" list, it won't be protected by a `HOLD` action.

### 3. AI Analysis
Copy the prompt from `generate_prompt.py` to Gemini.
- **Tip**: If Gemini suggests a `HOLD`, verify that the stock appears in your "Pre-flight Status" from Step 2. If it's not there, you need a `BUY` order instead.

### 4. Idempotent Execution
Copy Gemini's output table and run the execution script.
```bash
.\.venv\Scripts\python execute_trade.py
```
*   **Safety**: The script will automatically skip duplicates and check buying power. If a trade is skipped, read the warning message (e.g., `⚠️ Already Owned`) to understand why.

### 5. Audit Histroy (Optional)
If you are confused by a portfolio change, run the audit script to see fills and cancellations from the last 24 hours:
// turbo
```bash
.\.venv\Scripts\python check_history.py
```
