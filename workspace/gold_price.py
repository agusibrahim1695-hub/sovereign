#!/usr/bin/env python3
"""
XAUUSD Real-time Price Checker via Twelve Data API
"""
import requests
import sys
import time
from datetime import datetime

API_KEY = "93ef121c0685411cbdd6c556bcfb5eee"
BASE_URL = "https://api.twelvedata.com"

def get_price():
    """Ambil harga real-time XAUUSD"""
    url = f"{BASE_URL}/quote?symbol=XAU/USD&apikey={API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        
        if "code" in data:
            print(f"❌ Error: {data.get('message', 'Unknown error')}")
            return None
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n{'='*45}")
        print(f"  💰 XAU/USD (GOLD) - {now}")
        print(f"{'='*45}")
        print(f"  Price   : ${data.get('close', 'N/A')}")
        print(f"  Open    : ${data.get('open', 'N/A')}")
        print(f"  High    : ${data.get('high', 'N/A')}")
        print(f"  Low     : ${data.get('low', 'N/A')}")
        print(f"  Change  : {data.get('change', 'N/A')} ({data.get('percent_change', 'N/A')}%)")
        print(f"  Volume  : {data.get('volume', 'N/A')}")
        print(f"{'='*45}\n")
        
        return float(data.get('close', 0))
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def monitor(interval=5):
    """Monitor harga setiap X detik"""
    print(f"📊 Monitoring XAUUSD (update setiap {interval} detik) - Ctrl+C untuk stop\n")
    try:
        while True:
            get_price()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n🛑 Stopped.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        sec = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        monitor(sec)
    else:
        get_price()
