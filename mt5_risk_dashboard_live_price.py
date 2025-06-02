# mt5_risk_dashboard_signals.py

import streamlit as st
import requests
import json
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime

# === Session State Defaults ===
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "BTCUSD"
if "plan_exported" not in st.session_state:
    st.session_state.plan_exported = False
if "show_settings" not in st.session_state:
    st.session_state.show_settings = False

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

# === Load Symbols ===
symbols = load_symbols()
symbol_names = [s["symbol"] for s in symbols]
selected_symbol = st.selectbox("🧭 Select Symbol", options=symbol_names, index=symbol_names.index(st.session_state.selected_symbol))
st.session_state.selected_symbol = selected_symbol
pip_precision = next((s["pip_precision"] for s in symbols if s["symbol"] == selected_symbol), 0.0001)
yf_symbol = map_yf_symbol(selected_symbol)
live_price = fetch_price(yf_symbol)

# === Trade Direction ===
trade_direction = st.radio("Trade Direction", ["📈 Buy", "📉 Sell"], horizontal=True)
is_buy = trade_direction.startswith("📈")

# === Floating Drawer CSS ===
st.markdown("""
    <style>
    .drawer-button { position: fixed; top: 1rem; right: 1rem; z-index: 1001; }
    .drawer { position: fixed; top: 0; right: 0; height: 100%; width: 300px; background-color: #111; padding: 1rem; overflow-y: auto; box-shadow: -2px 0 10px rgba(0,0,0,0.3); z-index: 1000; display: block; }
    .close-drawer { float: right; cursor: pointer; color: #fff; }
    </style>
""", unsafe_allow_html=True)

if st.button("⚙️", key="drawer-btn", help="Open Trade Settings"):
    st.session_state.show_settings = True

# === Drawer UI ===
if st.session_state.show_settings:
    st.markdown('<div class="drawer">', unsafe_allow_html=True)
    if st.button("❌", key="close_drawer"):
        st.session_state.show_settings = False

    st.session_state.account_size = st.number_input("💼 Account Balance ($)", min_value=100.0, value=st.session_state.get("account_size", 10000.0), step=100.0)
    st.session_state.lot_size = st.number_input("📦 Lot Size", min_value=0.01, value=st.session_state.get("lot_size", 0.10), step=0.01)
    st.session_state.risk_percent = st.number_input("🎯 Risk per Trade (%)", min_value=0.1, max_value=10.0, value=st.session_state.get("risk_percent", 1.0), step=0.1)
    st.session_state.entry_price = st.number_input("🎯 Entry Price", value=live_price or 1.1400, format="%.5f", key="entry_price_drawer")
    st.session_state.rr_choice = st.selectbox("📐 Risk:Reward", ["1:1", "1:2", "1:3"], index=1, key="rr_drawer")
    st.markdown('</div>', unsafe_allow_html=True)

# === Apply Drawer Values ===
account_size = st.session_state.account_size
lot_size = st.session_state.lot_size
risk_percent = st.session_state.risk_percent
entry_price = st.session_state.entry_price
rr_value = {"1:1": 1.0, "1:2": 2.0, "1:3": 3.0}[st.session_state.rr_choice]

# === SL/TP Logic ===
risk_dollar = account_size * (risk_percent / 100)
sl_pips = risk_dollar / (lot_size * 10)
tp_pips = sl_pips * rr_value
sl_price = entry_price - (sl_pips * pip_precision) if is_buy else entry_price + (sl_pips * pip_precision)
tp_price = entry_price + (tp_pips * pip_precision) if is_buy else entry_price - (tp_pips * pip_precision)

stop_loss_price = st.number_input("🛑 Stop Loss Price", value=sl_price, format="%.5f")
take_profit_price = st.number_input("🎯 Take Profit Price", value=tp_price, format="%.5f")

# === Final Calculations ===
sl_pips = abs(entry_price - stop_loss_price) / pip_precision
tp_pips = abs(take_profit_price - entry_price) / pip_precision
risk_amount = sl_pips * lot_size * 10
reward_amount = tp_pips * lot_size * 10
rr_ratio = reward_amount / risk_amount if risk_amount else 0
suggested_lot_size = (account_size * risk_percent / 100) / (sl_pips * 10) if sl_pips else 0

# === Summary ===
st.subheader("📊 Trade Summary")
if live_price:
    st.info(f"💹 Current {selected_symbol} Price: {live_price}")
else:
    st.warning("⚠️ Live price unavailable.")

cols = st.columns(3)
cols[0].metric("SL", f"{sl_pips:.1f} pips")
cols[1].metric("TP", f"{tp_pips:.1f} pips")
cols[2].metric("R:R", f"{rr_ratio:.2f}")
cols2 = st.columns(2)
cols2[0].metric("Risk ($)", f"${risk_amount:.2f}")
cols2[1].metric("Reward ($)", f"${reward_amount:.2f}")
st.caption(f"Suggested Lot Size: {suggested_lot_size:.2f}")

# === Export ===
custom_path = st.text_input("📁 Export Path", value="trade_risk_calc.json")
if st.button("📤 Export Trade Plan"):
    trade_data = {
        "symbol": st.session_state.selected_symbol,
        "yf_symbol": map_yf_symbol(st.session_state.selected_symbol),
        "trade_type": "Buy" if is_buy else "Sell",
        "lot_size": lot_size,
        "account_size": account_size,
        "risk_percent": risk_percent,
        "entry_price": entry_price,
        "stop_loss": stop_loss_price,
        "take_profit": take_profit_price,
        "pip_precision": pip_precision,
        "stop_loss_pips": round(sl_pips, 1),
        "take_profit_pips": round(tp_pips, 1),
        "risk_usd": round(risk_amount, 2),
        "reward_usd": round(reward_amount, 2),
        "rr_ratio": round(rr_ratio, 2),
        "suggested_lot_size": round(suggested_lot_size, 2),
        "created_at": str(datetime.now())
    }
    with open(custom_path, "w") as f:
        json.dump(trade_data, f, indent=2)
    st.session_state.plan_exported = True
    st.success(f"✅ Saved to {custom_path}")

if st.button("📄 View Trade Plan", disabled=not st.session_state.plan_exported):
    try:
        with open(custom_path, "r") as f:
            content = f.read()
        st.code(content, language="json")
    except FileNotFoundError:
        st.warning("No trade plan found at given path.")

# === Chart ===
with st.expander("📈 Historical Price Chart"):
    period = st.selectbox("📅 Period", ["5d", "7d", "1mo", "3mo"])
    interval = st.selectbox("⏱️ Interval", ["1h", "30m", "15m"])
    if st.button("📥 Fetch & Plot History"):
        df = yf.download(map_yf_symbol(selected_symbol), period=period, interval=interval)
        if not df.empty:
            df["MA9"] = df["Close"].rolling(9).mean()
            df["MA21"] = df["Close"].rolling(21).mean()
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                                         low=df["Low"], close=df["Close"], name="Price"))
            fig.add_trace(go.Scatter(x=df.index, y=df["MA9"], line=dict(color='blue'), name="MA9"))
            fig.add_trace(go.Scatter(x=df.index, y=df["MA21"], line=dict(color='red'), name="MA21"))
            st.plotly_chart(fig, use_container_width=True)

            csv = df.to_csv().encode("utf-8")
            st.download_button("⬇️ Download CSV", data=csv, file_name=f"{selected_symbol}_{period}_{interval}.csv")
        else:
            st.warning("No historical data returned.")

# === Footer ===
st.markdown("---")
st.image("./images/logo.png", width=120)
st.caption("© 2025 Torama. All rights reserved.")
