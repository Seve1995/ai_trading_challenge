import os
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
import pathlib

# Load environment variables
load_dotenv()

# --- Paths ---
BASE_DIR = pathlib.Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / "logs"
PERFORMANCE_LOG = LOGS_DIR / "performance.csv"
MACRO_CACHE_DIR = LOGS_DIR / "macro_cache"
EXECUTION_LOGS_DIR = LOGS_DIR / "execution"

# --- URLs ---
# The GitHub Pages URL for the interactive dashboard
INTERACTIVE_URL = "https://seve1995.github.io/ai-portfolio-experiment/"

# --- Models ---
MODELS = {
    "1": {"name": "ChatGPT", "env_prefix": "CHATGPT"},
    "2": {"name": "Gemini", "env_prefix": "GEMINI"},
    "3": {"name": "Claude", "env_prefix": "CLAUDE"},
    "4": {"name": "Perplexity", "env_prefix": "PERPLEXITY"},
}

def select_model():
    """Interactively asks the user to select a model."""
    print("\nSelect the AI model for this session:")
    for key, info in MODELS.items():
        print(f"{key}. {info['name']}")
    
    while True:
        choice = input("\nEnter choice (1-4): ").strip()
        if choice in MODELS:
            return MODELS[choice]
        print("Invalid choice. Please enter a number between 1 and 4.")

def get_alpaca_api(model_info):
    """Returns an Alpaca REST API instance for the selected model."""
    prefix = model_info['env_prefix']
    key = os.getenv(f"{prefix}_ALPACA_KEY")
    secret = os.getenv(f"{prefix}_ALPACA_SECRET")
    
    if not key or not secret:
        # Fallback to default if model-specific keys are not found
        key = os.getenv("ALPACA_KEY")
        secret = os.getenv("ALPACA_SECRET")
        
        if not key or not secret:
            raise ValueError(f"No Alpaca API keys found for {model_info['name']} (Prefix: {prefix})")
        
        print(f"⚠️  Note: Using default ALPACA_KEY for {model_info['name']}")

    base_url = "https://paper-api.alpaca.markets"
    return tradeapi.REST(key, secret, base_url, api_version="v2")
