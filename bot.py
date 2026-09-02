import os
import sys
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

# Setup Configuration from Environment Variables
API_KEY = os.getenv("UPSTOX_API_KEY")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
BASE_URL = "https://api.upstox.com/v2"
LOG_FILE = "paper_trade_log.csv"

# Liquid Watchlist
WATCHLIST = ["RELIANCE", "TATOMOTORS", "INFY", "SBIN", "HDFCBANK", "ICICIBANK", "AXISBANK", "ADANIENT"]

def get_headers():
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

def fetch_market_data(symbol):
    """Fetches clean data from Upstox API fixing URL formats and indexing rules"""
    instrument_key = f"NSE_EQ|{symbol}" 
    
    # 1. FIXED: Correct Upstox V2 URL syntax using explicit ranges (Last 30 Days)
    today_str = datetime.now().strftime("%Y-%m-%d")
    start_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    hist_url = f"{BASE_URL}/historical-candle/{instrument_key}/day/{today_str}/{start_str}"
    
    try:
        response = requests.get(hist_url, headers=get_headers())
        if response.status_code != 200:
            print(f"⚠️ API Error for {symbol}: Status {response.status_code}")
            return None
            
        res = response.json()
        if "data" not in res or not res["data"]["candles"]:
            print(f"⚠️ No data format found for {symbol}")
            return None
            
        # Parse Upstox JSON structure safely
        candles = res["data"]["candles"]
        df_hist = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "vol", "oi"])
        
        # Upstox delivers elements reversed (newest first). Let's calculate safely:
        df_hist['range'] = df_hist['high'] - df_hist['low']
        atr_14 = df_hist['range'].iloc[1:15].mean()  # 14 days excluding today
        
        yesterday_high = df_hist['high'].iloc[1]
        yesterday_low = df_hist['low'].iloc[1]
        
        # 2. Extract today's ongoing session benchmarks 
        today_open = df_hist['open'].iloc[0]
        today_high = df_hist['high'].iloc[0]
        today_low = df_hist['low'].iloc[0]
        current_price = df_hist['close'].iloc[0]
        
        return {
            "symbol": symbol,
            "current": current_price,
            "open": today_open,
            "high": today_high,
            "low": today_low,
            "y_high": yesterday_high,
            "y_low": yesterday_low,
            "atr": atr_14
        }
    except Exception as e:
        print(f"❌ Network processing exception for {symbol}: {e}")
        return None

def log_trade_to_csv(date, symbol, side, entry_price):
    """Saves triggers into the CSV track layout file"""
    new_row = {
        "Date": date,
        "Symbol": symbol,
        "Side": side,
        "Entry_Price": entry_price,
        "Exit_Price": "",
        "P&L_Points": "",
        "Status": "OPEN"
    }
    
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        if not ((df['Date'] == date) & (df['Symbol'] == symbol)).any():
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])
        
    df.to_csv(LOG_FILE, index=False)
    print(f"📌 SUCCESS: Logged {side} position for {symbol} at {entry_price}")

def scan_and_execute():
   def scan_and_execute():
    print("🚀 Starting Clean Dual-Engine Morning Scan...")
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    for symbol in WATCHLIST:
        metrics = fetch_market_data(symbol)
        if not metrics: 
            continue
            
        day_range = metrics["high"] - metrics["low"]
        
        # --- PRODUCTION RELAXED STRATEGY CONDITIONS ---
        long_target = metrics["open"] * 1.01     # Up exactly 1.0% from morning Open
        short_target = metrics["open"] * 0.99    # Down exactly 1.0% from morning Open
        atr_req = metrics["atr"] * 0.5           # 0.5x ATR Range expansion achieved
        
        # Engine A: Breakout (Long)
        if (metrics["current"] > long_target) and (day_range > atr_req):
            log_trade_to_csv(today_date, symbol, "BUY", metrics["current"])
            
        # Engine B: Breakdown (Short)
        elif (metrics["current"] < short_target) and (day_range > atr_req):
            log_trade_to_csv(today_date, symbol, "SELL", metrics["current"])

if __name__ == "__main__":
    run_type = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if run_type == "scan":
        scan_and_execute()
    elif run_type == "squareoff":
        # Turning on evening execution loop now that pipeline is verified
        from bot import square_off_and_close
        square_off_and_close()
