#!/usr/bin/env python3
"""
XAUUSD Real-time WebSocket Price Stream via Twelve Data
"""
import websocket
import json
import threading
import time
from datetime import datetime

API_KEY = "93ef121c0685411cbdd6c556bcfb5eee"
WS_URL = f"wss://ws.twelvedata.com/v1/quotes/price?apikey={API_KEY}"

# Track price for simple SMC info
prev_price = None
high_session = 0
low_session = float('inf')

def on_message(ws, message):
    global prev_price, high_session, low_session
    
    data = json.loads(message)
    
    if "price" in data:
        price = float(data["price"])
        now = datetime.now().strftime("%H:%M:%S")
        
        # Track high/low
        if price > high_session:
            high_session = price
        if price < low_session:
            low_session = price
        
        # Direction indicator
        if prev_price:
            if price > prev_price:
                icon = "🟢 ▲"
            elif price < prev_price:
                icon = "🔴 ▼"
            else:
                icon = "⚪ ─"
        else:
            icon = "🟡 ●"
        
        # Spread from session high/low
        from_high = price - high_session
        from_low = price - low_session
        
        print(f"\r{icon} [{now}] ${price:.2f}  |  High: ${high_session:.2f}  Low: ${low_session:.2f}  |  From High: {from_high:+.2f}  From Low: {from_low:+.2f}  ", end="", flush=True)
        
        prev_price = price

def on_error(ws, error):
    print(f"\n❌ Error: {error}")

def on_close(ws, close_status, close_msg):
    print("\n🔴 WebSocket closed. Reconnecting in 3s...")
    time.sleep(3)
    start_ws()

def on_open(ws):
    # Subscribe to XAUUSD real-time quotes
    sub_msg = {
        "action": "subscribe",
        "params": {
            "symbols": "XAU/USD"
        }
    }
    ws.send(json.dumps(sub_msg))
    print("🟢 Connected! Streaming XAU/USD real-time prices...")
    print("   Press Ctrl+C to stop\n")

def start_ws():
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

if __name__ == "__main__":
    print("=" * 55)
    print("  🔥 XAU/USD REAL-TIME WEBSOCKET STREAM")
    print("  Powered by Twelve Data API")
    print("=" * 55)
    start_ws()
