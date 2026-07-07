#!/usr/bin/env python3
"""
XAUUSD SMC Full Analysis
- Market Structure, BOS, CHoCH, FVG, Order Blocks, Liquidity
"""
import requests, sys
from datetime import datetime

API_KEY = "93ef121c0685411cbdd6c556bcfb5eee"
BASE = "https://api.twelvedata.com"

def fetch_candles(interval="1h", count=200):
    r = requests.get(f"{BASE}/time_series", params={
        "symbol":"XAU/USD","interval":interval,"outputsize":count,"apikey":API_KEY
    }, timeout=15).json()
    if "values" not in r:
        print(f"Error: {r.get('message','?')}"); return []
    return [{"datetime":v["datetime"],"open":float(v["open"]),"high":float(v["high"]),
             "low":float(v["low"]),"close":float(v["close"])} for v in reversed(r["values"])]

def fetch_price():
    r = requests.get(f"{BASE}/quote?symbol=XAU/USD&apikey={API_KEY}", timeout=10).json()
    return float(r["close"]), r

# ═══════ SWING POINTS ═══════
def find_swings(candles, n=3):
    sh, sl = [], []
    for i in range(n, len(candles)-n):
        h, l = candles[i]["high"], candles[i]["low"]
        if all(candles[i-j]["high"]<h for j in range(1,n+1)) and all(candles[i+j]["high"]<h for j in range(1,n+1)):
            sh.append({"idx":i,"price":h,"dt":candles[i]["datetime"]})
        if all(candles[i-j]["low"]>l for j in range(1,n+1)) and all(candles[i+j]["low"]>l for j in range(1,n+1)):
            sl.append({"idx":i,"price":l,"dt":candles[i]["datetime"]})
    return sh, sl

# ═══════ MARKET STRUCTURE ═══════
def label_structure(sh, sl):
    swings = [{"type":"H","price":s["price"],"idx":s["idx"],"dt":s["dt"]} for s in sh] + \
             [{"type":"L","price":s["price"],"idx":s["idx"],"dt":s["dt"]} for s in sl]
    swings.sort(key=lambda x:x["idx"])
    labeled = []
    prev_h_price = None
    prev_l_price = None
    for s in swings:
        if s["type"]=="H":
            if prev_h_price is None:
                lbl = "H"
            elif s["price"] > prev_h_price:
                lbl = "HH"
            elif s["price"] < prev_h_price:
                lbl = "LH"
            else:
                lbl = "EH"
            s["label"] = lbl
            prev_h_price = s["price"]
        else:
            if prev_l_price is None:
                lbl = "L"
            elif s["price"] > prev_l_price:
                lbl = "HL"
            elif s["price"] < prev_l_price:
                lbl = "LL"
            else:
                lbl = "EL"
            s["label"] = lbl
            prev_l_price = s["price"]
        labeled.append(s)
    # Trend
    recent_h = [s for s in labeled if s["type"]=="H" and s["label"] in ("HH","LH")][-3:]
    recent_l = [s for s in labeled if s["type"]=="L" and s["label"] in ("HL","LL")][-3:]
    hh=sum(1 for s in recent_h if s["label"]=="HH"); hl=sum(1 for s in recent_l if s["label"]=="HL")
    lh=sum(1 for s in recent_h if s["label"]=="LH"); ll=sum(1 for s in recent_l if s["label"]=="LL")
    if hh>=2 and hl>=2: trend="UPTREND"
    elif lh>=2 and ll>=2: trend="DOWNTREND"
    else: trend="RANGING"
    return labeled, trend

# ═══════ BOS & CHoCH ═══════
def detect_bos_choch(candles, labeled):
    events = []
    if len(candles)<5 or len(labeled)<4: return events
    last_close = candles[-1]["close"]
    highs = [s for s in labeled if s["type"]=="H" and s["label"] in ("HH","LH")]
    lows = [s for s in labeled if s["type"]=="L" and s["label"] in ("HL","LL")]
    if len(highs)<2 or len(lows)<2: return events

    uptrend = highs[-1]["label"]=="HH" and highs[-2]["label"]=="HH" and lows[-1]["label"]=="HL"
    downtrend = highs[-1]["label"]=="LH" and highs[-2]["label"]=="LH" and lows[-1]["label"]=="LL"

    if downtrend:
        for h in reversed(highs):
            if last_close > h["price"]:
                events.append({"type":"CHoCH","dir":"BULLISH","level":h["price"],"dt":h["dt"]}); break
    if uptrend:
        for l in reversed(lows):
            if last_close < l["price"]:
                events.append({"type":"CHoCH","dir":"BEARISH","level":l["price"],"dt":l["dt"]}); break
    if uptrend:
        for h in reversed(highs):
            if last_close > h["price"]:
                events.append({"type":"BOS","dir":"BULLISH","level":h["price"],"dt":h["dt"]}); break
    if downtrend:
        for l in reversed(lows):
            if last_close < l["price"]:
                events.append({"type":"BOS","dir":"BEARISH","level":l["price"],"dt":l["dt"]}); break
    return events[-5:]

# ═══════ FAIR VALUE GAP ═══════
def detect_fvg(candles):
    fvgs = []
    for i in range(1, len(candles)-1):
        c1, c2, c3 = candles[i-1], candles[i], candles[i+1]
        avg = (c1["high"]+c1["low"])/2
        mg = avg * 0.0001
        if c1["high"] < c3["low"]:
            gap = c3["low"] - c1["high"]
            if gap >= mg:
                filled = any(candles[j]["low"]<=c3["low"] and candles[j]["high"]>=c1["high"] for j in range(i+2,len(candles)))
                fvgs.append({"type":"BULLISH","top":c3["low"],"bot":c1["high"],"gap":gap,"dt":c2["datetime"],"filled":filled})
        if c1["low"] > c3["high"]:
            gap = c1["low"] - c3["high"]
            if gap >= mg:
                filled = any(candles[j]["high"]>=c3["high"] and candles[j]["low"]<=c1["low"] for j in range(i+2,len(candles)))
                fvgs.append({"type":"BEARISH","top":c1["low"],"bot":c3["high"],"gap":gap,"dt":c2["datetime"],"filled":filled})
    return [f for f in fvgs if not f["filled"]][-10:]

# ═══════ ORDER BLOCKS ═══════
def detect_ob(candles):
    obs = []
    for i in range(2, len(candles)-1):
        if candles[i]["close"] < candles[i]["open"]:
            future = [candles[j] for j in range(i+1, min(i+6, len(candles)))]
            if future:
                max_move = max(c["high"] for c in future) - candles[i]["low"]
                if max_move / candles[i]["low"] * 100 >= 0.1:
                    filled = any(candles[j]["low"]<=candles[i]["high"] and candles[j]["close"]<=candles[i]["low"] for j in range(i+6,len(candles)))
                    obs.append({"type":"BULLISH","top":candles[i]["high"],"bot":candles[i]["low"],"dt":candles[i]["datetime"],"filled":filled})
        if candles[i]["close"] > candles[i]["open"]:
            future = [candles[j] for j in range(i+1, min(i+6, len(candles)))]
            if future:
                max_move = candles[i]["high"] - min(c["low"] for c in future)
                if max_move / candles[i]["high"] * 100 >= 0.1:
                    filled = any(candles[j]["high"]>=candles[i]["high"] and candles[j]["close"]>=candles[i]["low"] for j in range(i+6,len(candles)))
                    obs.append({"type":"BEARISH","top":candles[i]["high"],"bot":candles[i]["low"],"dt":candles[i]["datetime"],"filled":filled})
    return [o for o in obs if not o["filled"]][-10:]

# ═══════ LIQUIDITY ═══════
def detect_liquidity(sh, sl):
    liqs = []
    for i in range(len(sh)):
        for j in range(i+1, len(sh)):
            diff_pct = abs(sh[i]["price"]-sh[j]["price"])/sh[i]["price"]*100
            if diff_pct < 0.15:
                avg = (sh[i]["price"]+sh[j]["price"])/2
                liqs.append({"type":"EQH","level":avg,"info":"Buy-side liquidity"})
    for i in range(len(sl)):
        for j in range(i+1, len(sl)):
            diff_pct = abs(sl[i]["price"]-sl[j]["price"])/sl[i]["price"]*100
            if diff_pct < 0.15:
                avg = (sl[i]["price"]+sl[j]["price"])/2
                liqs.append({"type":"EQL","level":avg,"info":"Sell-side liquidity"})
    for s in sh[-5:]:
        liqs.append({"type":"BSL","level":s["price"],"info":"Buy-side @ swing high"})
    for s in sl[-5:]:
        liqs.append({"type":"SSL","level":s["price"],"info":"Sell-side @ swing low"})
    return liqs

# ═══════ MAIN ═══════
def run_analysis():
    print("Fetching data...")
    candles = fetch_candles("1h", 200)
    if not candles: return

    price, quote = fetch_price()
    sh, sl = find_swings(candles, 3)
    labeled, trend = label_structure(sh, sl)
    bos_choch = detect_bos_choch(candles, labeled)
    fvgs = detect_fvg(candles)
    obs = detect_ob(candles)
    liqs = detect_liquidity(sh, sl)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*55}")
    print(f"  XAU/USD SMC ANALYSIS - {now}")
    print(f"{'='*55}")

    print(f"\n  Price: ${price:.2f}")
    chg = quote.get('percent_change','?')
    print(f"  Open: ${quote.get('open','?')}  High: ${quote.get('high','?')}  Low: ${quote.get('low','?')}")
    print(f"  Change: {chg}%")

    print(f"\n{'-'*55}")
    print(f"  MARKET STRUCTURE: {trend}")
    print(f"{'-'*55}")
    recent = labeled[-8:]
    for s in recent:
        icon = "H" if s["type"]=="H" else "L"
        if s["label"] in ("HH","HL"): mark = "[+]"
        elif s["label"] in ("LH","LL"): mark = "[-]"
        else: mark = "[=]"
        print(f"  {icon} {s['label']:3s} ${s['price']:.2f}  {mark}  [{s['dt']}]")

    print(f"\n{'-'*55}")
    print(f"  BREAKS (BOS / CHoCH)")
    print(f"{'-'*55}")
    if bos_choch:
        for e in bos_choch:
            d = "^" if e["dir"]=="BULLISH" else "v"
            print(f"  {e['type']:5s} {e['dir']:8s} {d} @ ${e['level']:.2f}  [{e['dt']}]")
    else:
        print("  Tidak ada BOS/CHoCH terdeteksi")

    print(f"\n{'-'*55}")
    print(f"  FAIR VALUE GAPS (Unfilled)")
    print(f"{'-'*55}")
    if fvgs:
        for f in fvgs:
            d = "^" if f["type"]=="BULLISH" else "v"
            print(f"  {f['type']:8s} {d} ${f['bot']:.2f} - ${f['top']:.2f}  (gap: ${f['gap']:.2f})  [{f['dt']}]")
    else:
        print("  Tidak ada FVG unfilled")

    print(f"\n{'-'*55}")
    print(f"  ORDER BLOCKS (Unfilled)")
    print(f"{'-'*55}")
    if obs:
        for o in obs:
            d = "^" if o["type"]=="BULLISH" else "v"
            print(f"  {o['type']:8s} {d} ${o['bot']:.2f} - ${o['top']:.2f}  [{o['dt']}]")
    else:
        print("  Tidak ada OB unfilled")

    print(f"\n{'-'*55}")
    print(f"  LIQUIDITY LEVELS")
    print(f"{'-'*55}")
    eqs = [l for l in liqs if l["type"] in ("EQH","EQL")]
    pools = [l for l in liqs if l["type"] not in ("EQH","EQL")]
    if eqs:
        print("  Equal Levels:")
        for l in eqs:
            print(f"    {l['type']} @ ${l['level']:.2f}")
    if pools:
        print("  Liquidity Pools (recent):")
        for l in pools[-6:]:
            print(f"    {l['type']} @ ${l['level']:.2f}")

    # Trading Idea
    print(f"\n{'='*55}")
    print(f"  TRADING IDEA")
    print(f"{'='*55}")
    bull_zones = []
    bear_zones = []
    for o in obs:
        if o["type"]=="BULLISH": bull_zones.append(("OB", o["bot"], o["top"]))
        else: bear_zones.append(("OB", o["bot"], o["top"]))
    for f in fvgs:
        if f["type"]=="BULLISH": bull_zones.append(("FVG", f["bot"], f["top"]))
        else: bear_zones.append(("FVG", f["bot"], f["top"]))

    bull_zones.sort(key=lambda x: abs(price - (x[1]+x[2])/2))
    bear_zones.sort(key=lambda x: abs(price - (x[1]+x[2])/2))

    if trend=="UPTREND" and bull_zones:
        z = bull_zones[0]
        print(f"  BUY setup: Tunggu pullback ke {z[0]} zone")
        print(f"  Entry: ${z[1]:.2f} - ${z[2]:.2f}")
        print(f"  SL: ${z[1]-5:.2f}")
        print(f"  TP: liquidity level di atas")
    elif trend=="DOWNTREND" and bear_zones:
        z = bear_zones[0]
        print(f"  SELL setup: Tunggu retrace ke {z[0]} zone")
        print(f"  Entry: ${z[1]:.2f} - ${z[2]:.2f}")
        print(f"  SL: ${z[2]+5:.2f}")
        print(f"  TP: liquidity level di bawah")
    else:
        print("  Tunggu konfirmasi tren atau setup lebih jelas")

    print(f"\n{'='*55}\n")

if __name__ == "__main__":
    run_analysis()
