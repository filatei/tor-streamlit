# mt5_risk_dashboard_signals.py

import streamlit as st
import requests
import json
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime

# === Symbol Utilities ===
def load_symbols():
    try:
        response = requests.get("http://localhost:3600/api/trading/symbols", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        st.warning("⚠️ API not available. Loading local config.")
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

# === Load Symbols & Price ===
symbols = load_symbols()
symbol_names = [s["symbol"] for s in symbols]

# Use session_state to persist symbol choice
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "BTCUSD"

selected_symbol = st.selectbox("🧭 Select Symbol", options=symbol_names, index=symbol_names.index(st.session_state.selected_symbol))
st.session_state.selected_symbol = selected_symbol
pip_precision = next((s["pip_precision"] for s in symbols if s["symbol"] == selected_symbol), 0.0001)
yf_symbol = map_yf_symbol(selected_symbol)
live_price = fetch_price(yf_symbol)

# === Trade Direction ===
trade_direction = st.radio("Trade Direction", ["📈 Buy", "📉 Sell"], horizontal=True)
is_buy = trade_direction.startswith("📈")

# === Trade Settings ===
with st.expander("⚙️ Trade Settings", expanded=True):
    account_size = st.number_input("💼 Account Balance ($)", min_value=100.0, value=10000.0, step=100.0)
    lot_size = st.number_input("📦 Lot Size", min_value=0.01, value=0.10, step=0.01)
    risk_percent = st.number_input("🎯 Risk per Trade (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)
    entry_price = st.number_input("🎯 Entry Price", value=live_price or 1.1400, format="%.5f")
    rr_choice = st.selectbox("📐 Select Risk:Reward", ["1:1", "1:2", "1:3"], index=1)
    rr_map = {"1:1": 1.0, "1:2": 2.0, "1:3": 3.0}
    rr_value = rr_map[rr_choice]

# === SL/TP Calculation
risk_dollar = account_size * (risk_percent / 100)
sl_pips = risk_dollar / (lot_size * 10)
tp_pips = sl_pips * rr_value

sl_price = entry_price - (sl_pips * pip_precision) if is_buy else entry_price + (sl_pips * pip_precision)
tp_price = entry_price + (tp_pips * pip_precision) if is_buy else entry_price - (tp_pips * pip_precision)

stop_loss_price = st.number_input("🛑 Stop Loss Price", value=sl_price, format="%.5f")
take_profit_price = st.number_input("🎯 Take Profit Price", value=tp_price, format="%.5f")

# === Recalculate
sl_pips = abs(entry_price - stop_loss_price) / pip_precision
tp_pips = abs(take_profit_price - entry_price) / pip_precision
risk_amount = sl_pips * lot_size * 10
reward_amount = tp_pips * lot_size * 10
rr_ratio = reward_amount / risk_amount if risk_amount else 0
suggested_lot_size = (account_size * risk_percent / 100) / (sl_pips * 10) if sl_pips else 0

# === Trade Summary
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

# === Export Trade Plan ===
custom_path = st.text_input("📁 Export Path", value="trade_risk_calc.json")
if st.button("📤 Export Trade Plan"):
    export_symbol = st.session_state.selected_symbol
    export_yf_symbol = map_yf_symbol(export_symbol)
    trade_data = {
        "symbol": export_symbol,
        "yf_symbol": export_yf_symbol,
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
    st.success(f"✅ Saved to {custom_path}")

# === View Trade JSON ===
if st.button("📄 View Trade Plan"):
    try:
        with open(custom_path, "r") as f:
            content = f.read()
        st.code(content, language="json")
    except FileNotFoundError:
        st.warning("No trade plan found at given path.")

# === Historical Data Chart ===
with st.expander("📈 Historical Price Chart"):
    period = st.selectbox("📅 Period", ["5d", "7d", "1mo", "3mo"])
    interval = st.selectbox("⏱️ Interval", ["1h", "30m", "15m"])
    if st.button("📥 Fetch & Plot History"):
        df = yf.download(yf_symbol, period=period, interval=interval)
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
