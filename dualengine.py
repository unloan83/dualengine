import os
import sys
import bot

if __name__ == "__main__":
    run_type = sys.argv[1] if len(sys.argv) > 1 else "scan"
    
    velocity = float(os.getenv("INPUT_VELOCITY", 1.0))
    atr_multiplier = float(os.getenv("INPUT_ATR_MULT", 0.5))
    
    if run_type in ["scan", "monitor"]:
        bot.scan_and_execute(velocity, atr_multiplier)
    else:
        print(f"Skipping auto-squareoff for pipeline testing check. (mode: {run_type})")
