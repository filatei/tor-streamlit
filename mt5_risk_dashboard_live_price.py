import streamlit as st
import pandas as pd
import plotly.graph_objs as go
import json
from datetime import datetime

# === Title ===
st.set_page_config(page_title="MT5 Risk Dashboard", layout="wide")
st.title("📊 MT5 Risk Dashboard - CSV Upload & Backtest")

# === File Upload ===
uploaded_file = st.file_uploader("📁 Upload CSV File", type=["csv"])

if uploaded_file:
    try:
        # Skip the first bad header row
        df = pd.read_csv(uploaded_file, skiprows=1)

        # Parse datetime column
        df["Datetime"] = pd.to_datetime(df["Datetime"])

        # === Chart Section ===
        st.subheader("📈 Price Chart with MA21")

        df["MA21"] = df["Close"].rolling(21).mean()
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)

        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df["Datetime"], open=df["Open"], high=df["High"],
                                     low=df["Low"], close=df["Close"], name="Price"))
        fig.add_trace(go.Scatter(x=df["Datetime"], y=df["MA21"], line=dict(color='red'), name="MA21"))
        st.plotly_chart(fig, use_container_width=True)

        # === Backtest Section ===
        st.subheader("🔁 Simple MA21 Breakout Backtest")
        trades = []
        balance = 100000

        for i in range(1, len(df)):
            try:
                prev_close = df.loc[i - 1, "Close"]
                prev_ma21 = df.loc[i - 1, "MA21"]
                curr_close = df.loc[i, "Close"]
                curr_ma21 = df.loc[i, "MA21"]

                if prev_close < prev_ma21 and curr_close > curr_ma21:
                    entry = curr_close
                    sl = entry - 0.0020
                    tp = entry + 0.0030
                    high = df.loc[i, "High"]
                    low = df.loc[i, "Low"]

                    exit_price = tp if high >= tp else (sl if low <= sl else curr_close)
                    profit = 1500 if exit_price >= tp else (-1000 if exit_price <= sl else 0)
                    balance += profit

                    trades.append({
                        "Datetime": df.loc[i, "Datetime"],
                        "Entry": entry,
                        "Exit": exit_price,
                        "Result ($)": profit,
                        "Balance": balance
                    })
            except Exception as e:
                st.warning(f"⚠️ Skipped row {i} due to: {e}")

        if trades:
            results_df = pd.DataFrame(trades)
            st.line_chart(results_df.set_index("Datetime")["Balance"])
            st.dataframe(results_df)
            st.success(f"✅ Total Trades: {len(results_df)}, Final Balance: ${balance:,.2f}")
        else:
            st.info("No breakout trades triggered in this dataset.")

    except Exception as e:
        st.error(f"❌ Failed to process uploaded file: {e}")
else:
    st.info("Please upload a CSV file to begin.")

# === Footer ===
st.markdown("---")
st.caption("© 2025 Torama. All rights reserved.")