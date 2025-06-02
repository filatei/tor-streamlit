# mt5_risk_dashboard_signals.py

import streamlit as st
import requests
import json
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import pytz

from datetime import datetime

# === Session State Defaults ===
def ensure_session_state_defaults():
    defaults = {
        "selected_symbol": "BTCUSD",
        "plan_exported": False,
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
logo_col, title_col = st.columns([1, 8])
with logo_col:
    st.image("./images/logo.png", width=50)
with title_col:
    st.markdown("<h2 style='margin-top: 0.5em;'>MT5 Risk Dashboard</h2>", unsafe_allow_html=True)

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

# === Inline Trade Settings ===
st.markdown("### ⚙️ Trade Settings")
st.session_state.account_size = st.number_input("💼 Account Balance ($)", min_value=100.0, value=st.session_state.account_size, step=100.0)
st.session_state.lot_size = st.number_input("📦 Lot Size", min_value=0.01, value=st.session_state.lot_size, step=0.01)
st.session_state.risk_percent = st.number_input("🎯 Risk per Trade (%)", min_value=0.1, max_value=10.0, value=st.session_state.risk_percent, step=0.1)
st.session_state.entry_price = st.number_input("🎯 Entry Price", value=live_price or st.session_state.entry_price, format="%.5f")
st.session_state.rr_choice = st.selectbox("📐 Risk:Reward", ["1:1", "1:2", "1:3"], index=["1:1", "1:2", "1:3"].index(st.session_state.rr_choice))

# === Apply Values ===
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
# Additional enhancements to be added to your Streamlit app

# === Updated Chart Block with Auto-Export, Session Filter, and Backtest ===
with st.expander("📈 Historical Price Chart + Backtest"):
    period = st.selectbox("📅 Period", ["5d", "7d", "1mo", "3mo", "6mo", "12mo", "max"], index=5)
    interval = st.selectbox("⏱️ Interval", ["1h", "30m", "15m"])
    session_filter = st.selectbox("🕒 Session Filter", ["All", "London", "New York"], index=0)

    if st.button("\ud83d\udcc5 Fetch, Filter & Backtest"):
        df = yf.download(map_yf_symbol(selected_symbol), period=period, interval=interval)
        if df.empty:
            st.warning("No data returned from Yahoo Finance.")
        else:
            df.index = df.index.tz_localize(None)  # remove timezone
            df = df.reset_index()

            # Filter sessions
            df["Hour"] = pd.to_datetime(df["Datetime"]).dt.hour
            if session_filter == "London":
                df = df[df["Hour"].between(7, 16)]  # London hours (WAT 8–17)
            elif session_filter == "New York":
                df = df[df["Hour"].between(13, 21)]  # NY hours (WAT 14–22)

            # Save raw CSV
            csv = df.to_csv(index=False).encode("utf-8")
            filename = f"{selected_symbol}_{period}_{interval}_{session_filter}.csv"
            st.download_button("\u2b07\ufe0f Download Filtered CSV", data=csv, file_name=filename)

            # Plot chart
            df["MA9"] = df["Close"].rolling(9).mean()
            df["MA21"] = df["Close"].rolling(21).mean()
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df["Datetime"], open=df["Open"], high=df["High"],
                                         low=df["Low"], close=df["Close"], name="Price"))
            fig.add_trace(go.Scatter(x=df["Datetime"], y=df["MA9"], line=dict(color='blue'), name="MA9"))
            fig.add_trace(go.Scatter(x=df["Datetime"], y=df["MA21"], line=dict(color='red'), name="MA21"))
            st.plotly_chart(fig, use_container_width=True)

            # Run basic breakout backtest (example: close > MA21 => Buy signal)
            df.dropna(inplace=True)
            trades = []
            balance = 100000
            for i in range(1, len(df)):
                prev = df.iloc[i - 1]
                curr = df.iloc[i]
                if prev["Close"] < prev["MA21"] and curr["Close"] > curr["MA21"]:
                    entry = curr["Close"]
                    sl = entry - 0.0020  # 20 pips
                    tp = entry + 0.0030  # 30 pips
                    result = tp - entry
                    profit = 1500 if result > 0 else -1000
                    balance += profit
                    trades.append({"entry": entry, "exit": tp if profit > 0 else sl, "result": profit, "balance": balance})

            if trades:
                st.subheader("\ud83d\udcca Backtest Results")
                backtest_df = pd.DataFrame(trades)
                st.line_chart(backtest_df["balance"])
                st.write(backtest_df)
            else:
                st.info("No trades triggered in this dataset.")

# === Footer ===
st.markdown("---")
st.caption("© 2025 Torama. All rights reserved.")
