import os
import sys
import gzip
import requests
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta

API_KEY = os.getenv("UPSTOX_API_KEY")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
BASE_URL = "https://upstox.com"
LOG_FILE = "paper_trade_log.csv"

# Minimum and Maximum limits for your target range
MIN_TARGET_PCT = 7.0
MAX_TARGET_PCT = 12.0

def get_headers():
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

def get_pure_upstox_fo_watchlist():
    print("📥 Downloading official master instrument file from Upstox...")
    url = "https://upstox.com"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            raise Exception(f"Upstox instrument server returned status {response.status_code}")
        gzip_file = gzip.GzipFile(fileobj=BytesIO(response.content))
        df = pd.read_csv(gzip_file)
        df_fo = df[(df['exchange'] == 'NSE_FO') & (df['instrument_type'] == 'FUTSTK')]
        fo_stocks = df_fo['underlying_symbol'].dropna().unique().tolist()
        if not fo_stocks:
            raise Exception("Upstox master file returned an empty F&O dataset.")
        print(f"🎯 Pure Upstox Integration: Identified {len(fo_stocks)} live F&O stock assets.")
        return fo_stocks
    except Exception as e:
        print(f"❌ CRITICAL SYSTEM ERROR: Unable to dynamically verify active symbols: {e}")
        sys.exit(1)

def fetch_market_data(symbol):
    instrument_key = f"NSE_EQ|{symbol}" 
    today_str = datetime.now().strftime("%Y-%m-%d")
    start_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    hist_url = f"{BASE_URL}/historical-candle/{instrument_key}/day/{today_str}/{start_str}"
    
    try:
        response = requests.get(hist_url, headers=get_headers(), timeout=5)
        if response.status_code != 200: return None
        res = response.json()
        if "data" not in res or not res["data"]["candles"]: return None
            
        candles = res["data"]["candles"]
        df_hist = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "vol", "oi"])
        df_hist = df_hist.iloc[::-1].reset_index(drop=True)
        
        df_hist['range'] = df_hist['high'] - df_hist['low']
        atr_14 = df_hist['range'].iloc[-15:-1].mean()
        
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

def log_trade_to_csv(date, symbol, side, entry_price, current_velocity, current_atr):
    new_row = {
        "Date": date, "Symbol": symbol, "Side": side, "Entry_Price": entry_price,
        "Exit_Price": "-", "P&L_Points": "-", "Status": "OPEN",
        "Used_Velocity": f"{current_velocity}%", "Used_ATR_Mult": f"{current_atr}x"
    }
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        is_duplicate = ((df['Date'] == date) & (df['Symbol'] == symbol) & 
                        (df['Used_Velocity'] == f"{current_velocity}%") & 
                        (df['Used_ATR_Mult'] == f"{current_atr}x")).any()
        if not is_duplicate:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])
    df.to_csv(LOG_FILE, index=False)
    print(f"📌 Position logged: {side} {symbol} at ₹{entry_price}")

def scan_and_execute(velocity_pct, atr_mult):
    print(f"🚀 Initializing Live F&O Scan: Velocity={velocity_pct}%, ATR Mult={atr_mult}x")
    today_date = datetime.now().strftime("%Y-%m-%d")
    dynamic_watchlist = get_pure_upstox_fo_watchlist()
    
    for symbol in dynamic_watchlist:
        metrics = fetch_market_data(symbol)
        if not metrics: continue
            
        day_range = metrics["high"] - metrics["low"]
        long_target = metrics["open"] * (1 + (velocity_pct / 100))
        short_target = metrics["open"] * (1 - (velocity_pct / 100))
        atr_req = metrics["atr"] * atr_mult
        
        if (metrics["current"] > long_target) and (day_range > atr_req):
            log_trade_to_csv(today_date, symbol, "BUY", metrics["current"], velocity_pct, atr_mult)
        elif (metrics["current"] < short_target) and (day_range > atr_req):
            log_trade_to_csv(today_date, symbol, "SELL", metrics["current"], velocity_pct, atr_mult)

def square_off_and_close():
    """📌 NEW EXCLUDED RE-VALUATION: Tracks if the stock achieved your 7%-12% target range 
    during its maximum intraday peak, locking profits at Day's High / Day's Low.
    """
    print("📉 Executing High-Velocity Target Processing Loop...")
    today_date = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(LOG_FILE): return
    
    df = pd.read_csv(LOG_FILE)
    mask = (df['Date'] == today_date) & (df['Status'] == 'OPEN')
    if not mask.any(): return
        
    for index, row in df[mask].iterrows():
        symbol = row['Symbol']
        side = row['Side']
        entry = float(row['Entry_Price'])
        
        metrics = fetch_market_data(symbol)
        if not metrics: continue
        
        # Calculate maximum possible peak performance reached during the session
        if side == "BUY":
            max_move_pct = ((metrics["high"] - entry) / entry) * 100
            # If peak move met the 7% threshold, exit at Day's High. Else exit at current price.
            exit_price = metrics["high"] if max_move_pct >= MIN_TARGET_PCT else metrics["current"]
            pnl = exit_price - entry
        else: # SELL
            max_move_pct = ((entry - metrics["low"]) / entry) * 100
            # If peak drop met the 7% threshold, exit at Day's Low. Else exit at current price.
            exit_price = metrics["low"] if max_move_pct >= MIN_TARGET_PCT else metrics["current"]
            pnl = entry - exit_price
            
        df.at[index, 'Exit_Price'] = round(exit_price, 2)
        df.at[index, 'P&L_Points'] = round(pnl, 2)
        df.at[index, 'Status'] = 'CLOSED_TARGET' if max_move_pct >= MIN_TARGET_PCT else 'CLOSED_EOD'
        
        print(f"✅ Processed {symbol} | Peak Move: {round(max_move_pct, 2)}% | Exit Price: {exit_price}")
        
    df.to_csv(LOG_FILE, index=False)

if __name__ == "__main__":
    run_type = sys.argv[1] if len(sys.argv) > 1 else "scan"
    velocity = float(os.getenv("INPUT_VELOCITY", 1.0))
    atr_multiplier = float(os.getenv("INPUT_ATR_MULT", 0.5))
    
    if run_type == "scan":
        scan_and_execute(velocity, atr_multiplier)
    elif run_type == "squareoff":
        square_off_and_close()
