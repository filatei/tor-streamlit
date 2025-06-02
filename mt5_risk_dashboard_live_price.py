# mt5_risk_dashboard_signals.py

import streamlit as st
import requests
import json
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime

# === Session State Defaults ===
def ensure_session_state_defaults():
    defaults = {
        "selected_symbol": "BTCUSD",
        "plan_exported": False,
        "show_settings": False,
        "account_size": 10000.0,
        "lot_size": 0.10,
        "risk_percent": 1.0,
        "entry_price": 1.1400,
        "rr_choice": "1:2"
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

ensure_session_state_defaults()

# === App Title & Header ===
st.markdown("""
    <style>
    .drawer-button { position: fixed; top: 1rem; right: 1rem; z-index: 1001; }
    .drawer {
        position: fixed;
        top: 0;
        right: 0;
        height: 100%;
        width: 100vw;
        max-width: 320px;
        background-color: #111;
        padding: 1rem;
        overflow-y: auto;
        box-shadow: -2px 0 10px rgba(0,0,0,0.3);
        z-index: 1000;
        display: block;
    }
    .close-drawer {
        float: right;
        cursor: pointer;
        color: #fff;
    }
    @media (max-width: 768px) {
        .drawer { width: 100vw; }
    }
    </style>
""", unsafe_allow_html=True)

logo_col, title_col, settings_col = st.columns([1, 6, 1])
with logo_col:
    st.image("./images/logo.png", width=50)
with title_col:
    st.markdown("<h2 style='margin-top: 0.5em;'>MT5 Risk Dashboard</h2>", unsafe_allow_html=True)
with settings_col:
    if st.button("⚙️", key="drawer-btn", help="Open Trade Settings"):
        st.session_state.show_settings = True

# === Symbol Utilities ===
def load_symbols():
    try:
        response = requests.get("http://localhost:3600/api/trading/symbols", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        with open("symbols_config.json", "r") as f:
            return json.load(f)

def map_yf_symbol(mt5_symbol):
    overrides = {
        "XAUUSD": "GC=F",
        "BTCUSD": "BTC-USD",
        "USDJPY": "USDJPY=X",
        "EURUSD": "EURUSD=X",
        "USOIL": "CL=F",
        "NZDCAD": "NZDCAD=X"
    }
    return overrides.get(mt5_symbol, mt5_symbol + "=X")

def fetch_price(symbol):
    try:
        data = yf.Ticker(symbol)
        hist = data.history(period="1d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 5)
    except Exception:
        return None

def custom_analysis_nzdcad():
    df = yf.download("NZDCAD=X", period="7d", interval="1h")
    if df.empty:
        st.warning("No NZDCAD data returned.")
        return

    df["MA9"] = df["Close"].rolling(window=9).mean()
    df["MA21"] = df["Close"].rolling(window=21).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Close", line=dict(color="white")))
    fig.add_trace(go.Scatter(x=df.index, y=df["MA9"], name="MA9", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=df.index, y=df["MA21"], name="MA21", line=dict(color="red")))
    fig.update_layout(title="NZDCAD Trend (MA9 vs MA21)", xaxis_title="Time", yaxis_title="Price")
    st.plotly_chart(fig, use_container_width=True)

# === Load Symbols ===
symbols = load_symbols()
symbols.extend([
    {"symbol": "USOIL", "pip_precision": 0.1},
    {"symbol": "NZDCAD", "pip_precision": 0.0001}
])
symbol_names = [s["symbol"] for s in symbols]
selected_symbol = st.selectbox("🧭 Select Symbol", options=symbol_names, index=symbol_names.index(st.session_state.selected_symbol))
st.session_state.selected_symbol = selected_symbol
pip_precision = next((s["pip_precision"] for s in symbols if s["symbol"] == selected_symbol), 0.0001)
yf_symbol = map_yf_symbol(selected_symbol)
live_price = fetch_price(yf_symbol)

# === Trade Direction ===
trade_direction = st.radio("Trade Direction", ["📈 Buy", "📉 Sell"], horizontal=True)
is_buy = trade_direction.startswith("📈")

# === Drawer UI ===
if st.session_state.show_settings:
    st.markdown('<div class="drawer">', unsafe_allow_html=True)
    if st.button("❌", key="close_drawer"):
        st.session_state.show_settings = False

    st.session_state.account_size = st.number_input("💼 Account Balance ($)", min_value=100.0, value=st.session_state.account_size, step=100.0)
    st.session_state.lot_size = st.number_input("📦 Lot Size", min_value=0.01, value=st.session_state.lot_size, step=0.01)
    st.session_state.risk_percent = st.number_input("🎯 Risk per Trade (%)", min_value=0.1, max_value=10.0, value=st.session_state.risk_percent, step=0.1)
    st.session_state.entry_price = st.number_input("🎯 Entry Price", value=live_price or st.session_state.entry_price, format="%.5f", key="entry_price_drawer")
    st.session_state.rr_choice = st.selectbox("📐 Risk:Reward", ["1:1", "1:2", "1:3"], index=["1:1", "1:2", "1:3"].index(st.session_state.rr_choice), key="rr_drawer")
    st.markdown('</div>', unsafe_allow_html=True)

# === Apply Drawer Values ===
account_size = st.session_state.account_size
lot_size = st.session_state.lot_size
risk_percent = st.session_state.risk_percent
entry_price = st.session_state.entry_price
rr_value = {"1:1": 1.0, "1:2": 2.0, "1:3": 3.0}[st.session_state.rr_choice]

# === Custom Logic for NZDCAD ===
if selected_symbol == "NZDCAD":
    st.subheader("🧠 Custom Analysis for NZDCAD")
    custom_analysis_nzdcad()

# (rest of code remains unchanged)
