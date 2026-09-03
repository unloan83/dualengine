import os
import sys
import gzip
import json
import requests
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta

API_KEY = os.getenv("UPSTOX_API_KEY")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
BASE_URL = "https://api.upstox.com/v2"
LOG_FILE = "paper_trade_log.csv"

MIN_TARGET_PCT = 7.0
MAX_TARGET_PCT = 12.0

def get_headers():
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

def get_pure_upstox_fo_watchlist():
    """
    📌 FIXED JSON INTEGRATION: Leverages Upstox's official active JSON endpoint layout.
    Unpacks raw byte dictionaries to extract underlyings without CSV dependency mismatches.
    """
    print("📥 Downloading official active JSON instrument mapping from Upstox...")
    # Using the clean, segment-specific active JSON stream to avoid heavy parsing weights
    url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            raise Exception(f"Upstox instrument server returned status {response.status_code}")
            
        # Decompress the gzipped raw binary stream data cleanly
        decompressed_data = gzip.decompress(response.content)
        
        # Load the raw text layout array directly into structural dictionaries
        json_data = json.loads(decompressed_data.decode('utf-8'))
        df = pd.DataFrame(json_data)
        
        # 📌 Upstox JSON structure filters:
        # segment == 'NSE_FO' handles derivatives, and instrument_type == 'FUTSTK' keeps focus on stocks
        df_fo = df[(df['segment'] == 'NSE_FO') & (df['instrument_type'] == 'FUTSTK')]
        
        # Extract unique underlying symbols (e.g., getting 'TATAMOTORS' from weekly derivative tokens)
        fo_stocks = df_fo['underlying_symbol'].dropna().unique().tolist()
        
        if not fo_stocks:
            raise Exception("Upstox master dataset returned zero active stock derivatives matches.")
            
        print(f"🎯 Pure Upstox Integration: Identified {len(fo_stocks)} live high-velocity F&O symbols.")
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

def log_trade_to_csv(date, symbol, side, entry_price, current_velocity=1.0, current_atr=0.5):
    new_row = {
        "Date": date, "Symbol": symbol, "Side": side, "Entry_Price": entry_price,
        "Exit_Price": "-", "P&L_Points": "-", "Status": "OPEN",
        "Used_Velocity": f"{current_velocity}%", "Used_ATR_Mult": f"{current_atr}x"
    }
    
    if os.path.exists(LOG_FILE):
        try:
            df = pd.read_csv(LOG_FILE)
            if 'Used_Velocity' not in df.columns: df['Used_Velocity'] = "1.0%"
            if 'Used_ATR_Mult' not in df.columns: df['Used_ATR_Mult'] = "0.5x"
                
            is_duplicate = ((df['Date'] == date) & (df['Symbol'] == symbol) & 
                            (df['Used_Velocity'] == f"{current_velocity}%") & 
                            (df['Used_ATR_Mult'] == f"{current_atr}x")).any()
            if not is_duplicate:
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        except:
            df = pd.DataFrame([new_row])
    else:
        df = pd.DataFrame([new_row])
        
    df.to_csv(LOG_FILE, index=False)
    print(f"📌 position logged: {side} {symbol} at ₹{entry_price}")

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
        
        # Engine A: Breakout (Long)
        if (metrics["current"] > long_target) and (day_range > atr_req):
            log_trade_to_csv(today_date, symbol, "BUY", metrics["current"], velocity_pct, atr_mult)
            
        # Engine B: Breakdown (Short)
        elif (metrics["current"] < short_target) and (day_range > atr_req):
            log_trade_to_csv(today_date, symbol, "SELL", metrics["current"], velocity_pct, atr_mult)

def square_off_and_close():
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
        
        if side == "BUY":
            max_move_pct = ((metrics["high"] - entry) / entry) * 100
            exit_price = metrics["high"] if max_move_pct >= MIN_TARGET_PCT else metrics["current"]
            pnl = exit_price - entry
        else: # SELL
            max_move_pct = ((entry - metrics["low"]) / entry) * 100
            exit_price = metrics["low"] if max_move_pct >= MIN_TARGET_PCT else metrics["current"]
            pnl = entry - exit_price
            
        df.at[index, 'Exit_Price'] = round(exit_price, 2)
        df.at[index, 'P&L_Points'] = round(pnl, 2)
        df.at[index, 'Status'] = 'CLOSED_TARGET' if max_move_pct >= MIN_TARGET_PCT else 'CLOSED_EOD'
        
    df.to_csv(LOG_FILE, index=False)

if __name__ == "__main__":
    run_type = sys.argv if len(sys.argv) > 1 else "scan"
    
    env_velocity = os.getenv("INPUT_VELOCITY", "1.0")
    env_atr_mult = os.getenv("INPUT_ATR_MULT", "0.5")
    
    velocity = float(env_velocity) if env_velocity.strip() != "" else 1.0
    atr_multiplier = float(env_atr_mult) if env_atr_mult.strip() != "" else 0.5
    
    if run_type == "scan":
        scan_and_execute(velocity, atr_multiplier)
    elif run_type == "squareoff":
        square_off_and_close()
