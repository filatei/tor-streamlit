import yfinance as yf
data = yf.Ticker("CL=F")
print(data.history(period="1d"))