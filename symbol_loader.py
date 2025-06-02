import requests
import json

def load_symbols():
    """
    Load symbol list from localhost API, fallback to local JSON.
    """
    try:
        response = requests.get("http://localhost:3600/api/trading/symbols", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        print("⚠️ Could not fetch from API. Loading local symbol config.")
        with open("symbols_config.json", "r") as f:
            return json.load(f)
