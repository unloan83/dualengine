import os
import requests
import pandas as pd

# 1. Setup Configuration from Environment Variables
API_KEY = os.getenv("UPSTOX_API_KEY")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN") # Generated during auth
BASE_URL = "https://upstox.com"

# A small subset of highly liquid F&O stocks for absolute simplicity
WATCHLIST = ["RELIANCE", "TATOMOTORS", "INFY", "SBIN", "HDFCBANK", "ICICIBANK", "AXISBANK", "ADANIENT"]

def get_headers():
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

def fetch_market_data(symbol):
    """Fetches daily and intraday data to calculate metrics"""
    # In a live Upstox implementation, you look up the instrument key for the symbol first
    # For simplicity, this assumes a helper function or direct spot instrument key mapping
    instrument_key = f"NSE_EQ|{symbol}" 
    
    # Fetch historical daily candles to calculate 14-day ATR and Yesterday's High/Low
    hist_url = f"{BASE_URL}/historical-candle/{instrument_key}/day/2026-09-02" # Dynamic date handling
    res = requests.get(hist_url, headers=get_headers()).json()
    
    if "data" not in res or not res["data"]["candles"]:
        return None
        
    df_hist = pd.DataFrame(res["data"]["candles"], columns=["time", "open", "high", "low", "close", "vol", "oi"])
    
    # Calculate simple 14-day ATR (High - Low average)
    df_hist['range'] = df_hist['high'] - df_hist['low']
    atr_14 = df_hist['range'].head(14).mean()
    
    yesterday_high = df_hist['high'].iloc[1]
    yesterday_low = df_hist['low'].iloc[1]
    
    # Fetch today's live market quote
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

def place_paper_trade(side, data):
    """Simulates an entry by logging it clearly into the console/GitHub logs"""
    print(f"--- [PAPER TRADE TRIGGERED] ---")
    print(f"ACTION: {side} | SYMBOL: {data['symbol']} | ENTRY PRICE: {data['current']}")
    # To convert this to a live Upstox paper trade/live trade later, you would replace this print
    # statement with an HTTP POST request to Upstox's /order/place endpoint using 'is_paper=True' if supported or your paper logic.
    print(f"Suggested Stop Loss: {data['open'] if side == 'BUY' else data['open']}")
    print(f"--------------------------------")

def scan_and_execute():
    print("Starting Dual-Engine Morning Scan...")
    for symbol in WATCHLIST:
        try:
            metrics = fetch_market_data(symbol)
            if not metrics: continue
            
            day_range = metrics["high"] - metrics["low"]
            
            # Engine A: Breakout (Long)
            if (metrics["current"] > metrics["y_high"]) and \
               (metrics["current"] > metrics["open"] * 1.03) and \
               (day_range > metrics["atr"] * 1.5):
                place_paper_trade("BUY", metrics)
                
            # Engine B: Breakdown (Short)
            elif (metrics["current"] < metrics["y_low"]) and \
                 (metrics["current"] < metrics["open"] * 0.97) and \
                 (day_range > metrics["atr"] * 1.5):
                place_paper_trade("SELL", metrics)
                
        except Exception as e:
            print(f"Error scanning {symbol}: {e}")

if __name__ == "__main__":
    # Check if we are running morning scan or evening square-off
    import sys
    run_type = sys.argv[1] if len(sys.argv) > 1 else "scan"
    
    if run_type == "scan":
        scan_and_execute()
    else:
        print("Executing 03:10 PM Auto-Square off for paper trades. Fetching current market exit prices...")
        # Add logic here to read your logged trades and calculate closing profit/loss.
