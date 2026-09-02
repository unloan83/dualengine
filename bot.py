import os
import sys
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

API_KEY = os.getenv("UPSTOX_API_KEY")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
BASE_URL = "https://api.upstox.com/v2"
LOG_FILE = "paper_trade_log.csv"

WATCHLIST = ["RELIANCE", "TATOMOTORS", "INFY", "SBIN", "HDFCBANK", "ICICIBANK", "AXISBANK", "ADANIENT"]

def get_headers():
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

def fetch_market_data(symbol):
    instrument_key = f"NSE_EQ|{symbol}" 
    
    # 📌 CORRECT FORMAT: /historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}
    today_str = datetime.now().strftime("%Y-%m-%d")
    start_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    hist_url = f"{BASE_URL}/historical-candle/{instrument_key}/day/{today_str}/{start_str}"
    
    try:
        response = requests.get(hist_url, headers=get_headers())
        if response.status_code != 200:
            return None
            
        res = response.json()
        if "data" not in res or not res["data"]["candles"]:
            return None
            
        candles = res["data"]["candles"]
        # Upstox returns data sorted newest first. Let's build a clean dataframe
        df_hist = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "vol", "oi"])
        
        # Sort oldest to newest to handle tracking indexing smoothly
        df_hist = df_hist.iloc[::-1].reset_index(drop=True)
        
        df_hist['range'] = df_hist['high'] - df_hist['low']
        atr_14 = df_hist['range'].iloc[-15:-1].mean() # Average of previous 14 days
        
        return {
            "symbol": symbol,
            "current": df_hist['close'].iloc[-1],
            "open": df_hist['open'].iloc[-1],
            "high": df_hist['high'].iloc[-1],
            "low": df_hist['low'].iloc[-1],
            "atr": atr_14
        }
    except:
        return None

def log_trade_to_csv(date, symbol, side, entry_price):
    new_row = {
        "Date": date,
        "Symbol": symbol,
        "Side": side,
        "Entry_Price": entry_price,
        "Exit_Price": "-",
        "P&L_Points": "-",
        "Status": "OPEN"
    }
    
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        # Prevent duplication entries
        if not ((df['Date'] == date) & (df['Symbol'] == symbol)).any():
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])
        
    df.to_csv(LOG_FILE, index=False)
    print(f"📌 Logged entry for {symbol}")

def scan_and_execute(velocity_pct, atr_mult):
    print(f"🚀 Initializing scan: Velocity={velocity_pct}%, ATR Mult={atr_mult}x")
    today_date = datetime.now().strftime("%Y-%m-%d")
    triggered_any = False
    
    for symbol in WATCHLIST:
        metrics = fetch_market_data(symbol)
        if not metrics: 
            continue
            
        day_range = metrics["high"] - metrics["low"]
        long_target = metrics["open"] * (1 + (velocity_pct / 100))
        short_target = metrics["open"] * (1 - (velocity_pct / 100))
        atr_req = metrics["atr"] * atr_mult
        
        if (metrics["current"] > long_target) and (day_range > atr_req):
            log_trade_to_csv(today_date, symbol, "BUY", metrics["current"])
            triggered_any = True
        elif (metrics["current"] < short_target) and (day_range > atr_req):
            log_trade_to_csv(today_date, symbol, "SELL", metrics["current"])
            triggered_any = True

    # Force a test entry if no live signals triggered so that Vercel has data to render!
    if not triggered_any:
        log_trade_to_csv(today_date, "RELIANCE", "BUY_TEST", 2450.00)

if __name__ == "__main__":
    run_type = sys.argv[1] if len(sys.argv) > 1 else "scan"
    
    velocity = float(os.getenv("INPUT_VELOCITY", 1.0))
    atr_multiplier = float(os.getenv("INPUT_ATR_MULT", 0.5))
    
    if run_type == "scan":
        scan_and_execute(velocity, atr_multiplier)
