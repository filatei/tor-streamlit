import streamlit as st
from symbol_loader import load_symbols

symbols = load_symbols()
symbol_names = [s["symbol"] for s in symbols]
selected_symbol = st.selectbox("🧭 Select Trading Symbol", options=symbol_names, index=symbol_names.index("EURUSD"))

# Match selected pip precision
pip_precision = next((s["pip_precision"] for s in symbols if s["symbol"] == selected_symbol), 0.0001)
