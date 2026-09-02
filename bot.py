import os
import sys
import json
import requests
import pandas as pd
from datetime import datetime

# 1. Setup Configuration from Environment Variables
API_KEY = os.getenv("UPSTOX_API_KEY")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
BASE_URL = "https://upstox.com"
LOG_FILE = "paper_trade_log.csv"

# Liquid F&O Watchlist
WATCHLIST = ["RELIANCE", "TATOMOTORS", "INFY", "SBIN", "HDFCBANK", "ICICIBANK", "AXISBANK", "ADANIENT"]

def get_headers():
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

def get_today_ist_date():
    # Dynamic date matching for historical candle retrieval
    return datetime.now().strftime("%Y-%m-%d")

def fetch_market_data(symbol):
    """Fetches daily and live data to calculate engine metrics"""
    instrument_key = f"NSE_EQ|{symbol}" 
    today_date = get_today_ist_date()
    
    # Fetch historical daily candles (lookback for 14-day ATR & Yesterday's bounds)
    hist_url = f"{BASE_URL}/historical-candle/{instrument_key}/day/{today_date}"
    res = requests.get(hist_url, headers=get_headers()).json()
    
    if "data" not in res or not res["data"]["candles"]:
        return None
        
    df_hist = pd.DataFrame(res["data"]["candles"], columns=["time", "open", "high", "low", "close", "vol", "oi"])
    
    # Calculate 14-day ATR (High - Low average)
    df_hist['range'] = df_hist['high'] - df_hist['low']
    atr_14 = df_hist['range'].head(14).mean()
    
    yesterday_high = df_hist['high'].iloc[1]
    yesterday_low = df_hist['low'].iloc[1]
    
    # Fetch live market quote
    quote_url = f"{BASE_URL}/market-quote/quotes?instrument_key={instrument_key}"
    quote_res = requests.get(quote_url, headers=get_headers()).json()
    
    today_data = quote_res["data"][instrument_key]
    current_price = today_data["last_price"]
    today_open = today_data["ohlc"]["open"]
    today_high = today_data["ohlc"]["high"]
    today_low = today_data["ohlc"]["low"]
    
    return {
        "symbol": symbol,
        "instrument_key": instrument_key,
        "current": current_price,
        "open": today_open,
        "high": today_high,
        "low": today_low,
        "y_high": yesterday_high,
        "y_low": yesterday_low,
        "atr": atr_14
    }

def log_trade_to_csv(date, symbol, side, entry_price):
    """Saves new morning triggers to the CSV file"""
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
        # Avoid duplicate entries for the same stock on the same day
        if not ((df['Date'] == date) & (df['Symbol'] == symbol)).any():
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])
        
    df.to_csv(LOG_FILE, index=False)
    print(f"📌 Logged OPEN position: {side} {symbol} at {entry_price}")

def scan_and_execute():
    print("🚀 Starting Dual-Engine Morning Scan...")
    today_date = get_today_ist_date()
    
    for symbol in WATCHLIST:
        try:
            metrics = fetch_market_data(symbol)
            if not metrics: continue
            
            day_range = metrics["high"] - metrics["low"]
            
            # Engine A: Breakout (Long)
            if (metrics["current"] > metrics["y_high"]) and \
               (metrics["current"] > metrics["open"] * 1.03) and \
               (day_range > metrics["atr"] * 1.5):
                log_trade_to_csv(today_date, symbol, "BUY", metrics["current"])
                
            # Engine B: Breakdown (Short)
            elif (metrics["current"] < metrics["y_low"]) and \
                 (metrics["current"] < metrics["open"] * 0.97) and \
                 (day_range > metrics["atr"] * 1.5):
                log_trade_to_csv(today_date, symbol, "SELL", metrics["current"])
                
        except Exception as e:
            print(f"❌ Error scanning {symbol}: {e}")

def square_off_and_close():
    print("📉 Starting Evening Auto Square-Off Execution...")
    today_date = get_today_ist_date()
    
    if not os.path.exists(LOG_FILE):
        print("ℹ️ No active log file found. No positions to close today.")
        return
        
    df = pd.read_csv(LOG_FILE)
    
    # Process only open trades belonging to today
    mask = (df['Date'] == today_date) & (df['Status'] == 'OPEN')
    if not mask.any():
        print("ℹ️ No open positions found for today.")
        return
        
    for index, row in df[mask].iterrows():
        symbol = row['Symbol']
        side = row['Side']
        entry = float(row['Entry_Price'])
        
        try:
            # Fetch the final wrap-up market close price
            metrics = fetch_market_data(symbol)
            if not metrics: continue
            
            exit_price = metrics["current"]
            
            # Calculate net daytime point capture
            if side == "BUY":
                pnl = exit_price - entry
            else: # SELL
                pnl = entry - exit_price
                
            df.at[index, 'Exit_Price'] = exit_price
            df.at[index, 'P&L_Points'] = round(pnl, 2)
            df.at[index, 'Status'] = 'CLOSED'
            
            print(f"✅ Closed {symbol} | Entry: {entry} | Exit: {exit_price} | P&L: {round(pnl, 2)} pts")
            
        except Exception as e:
            print(f"❌ Error squaring off {symbol}: {e}")
            
    df.to_csv(LOG_FILE, index=False)

if __name__ == "__main__":
    run_type = sys.argv[1] if len(sys.argv) > 1 else "scan"
    
    if run_type == "scan":
        scan_and_execute()
    elif run_type == "squareoff":
        square_off_and_close()
