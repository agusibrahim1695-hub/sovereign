#!/usr/bin/env python3
"""MULTI-PAIR SMC SCANNER v3 - Rate limit safe + Multi Key"""
import sys,time
sys.path.insert(0,".")
from smc_core import fc,fp,tr,dob,dfvg,dliq,dbos,gzone,L1,L2,L3,L4,L5,vrd,API_KEYS

PAIRS = [
    "XAU/USD","EUR/USD","GBP/USD",
    "USD/JPY","USD/CAD","USD/CHF",
]

def scan_pair(sym):
    # Fetch data with proper delay between each API call
    daily=fc(sym,"1day",100)
    time.sleep(3)
    h4=fc(sym,"4h",200)
    time.sleep(3)
    h1=fc(sym,"1h",200)
    time.sleep(3)
    price,qt=fp(sym)
    time.sleep(3)
    if not price: return None
    if not daily or not h1: return None
    dt,_,_=tr(daily)
    h4t,_,_=tr(h4)if h4 else("NEUTRAL",[],[])
    h1t,h1sh,h1sl=tr(h1)
    obs=dob(h1);fvs=dfvg(h1)
    lq=dliq(h1sh,h1sl);bos=dbos(h1)
    zn,fib=gzone(price,h1sh,h1sl)
    ly=[L1(dt,h4t),L2(obs,fvs,lq,price),L3(h4t,h1t,bos),L4(h1),L5(zn,fib)]
    v,bu,be,tot=vrd(ly)
    chg=qt.get("percent_change","?")if qt else"?"
    buo=[o for o in obs if o["t"]=="B"]
    beo=[o for o in obs if o["t"]=="S"]
    buo_n=sorted(buo,key=lambda x:abs(price-(x["l"]+x["h"])/2))[:1]if buo else[]
    beo_n=sorted(beo,key=lambda x:abs(price-(x["l"]+x["h"])/2))[:1]if beo else[]
    return {"sym":sym,"price":price,"chg":chg,"layers":ly,"verdict":v,"bull":bu,"bear":be,"total":tot,"zone":zn,"fib":fib,"bull_ob":buo_n[0]if buo_n else None,"bear_ob":beo_n[0]if beo_n else None}

def grade(s):
    if s>=5: return "S+"
    elif s>=4: return "A"
    elif s>=3: return "B"
    elif s>=2: return "C"
    return "D"

def run():
    print(f"\n{'='*60}")
    print(f"  MULTI-PAIR SMC SCANNER v3")
    print(f"  API Keys: {len(API_KEYS)} active | {len(PAIRS)} pairs")
    print(f"{'='*60}\n")

    results=[]
    for sym in PAIRS:
        sys.stdout.write(f"  {sym}...")
        sys.stdout.flush()
        try:
            r=scan_pair(sym)
            if r:
                results.append(r)
                g=grade(r["bull"])
                print(f" {r['verdict']} ({r['bull']}/{r['total']}) Grade:{g}")
            else:
                print(f" SKIP (rate limit/no data)")
        except Exception as e:
            print(f" ERR: {e}")

    results.sort(key=lambda x:x["bull"],reverse=True)

    print(f"\n{'='*60}")
    print(f"  RANKING")
    print(f"{'='*60}")
    print(f"  {'#':<4} {'Pair':<12} {'Price':<10} {'Grd':<5} {'Verdict':<14} {'Layers':<8} {'Zone'}")
    print(f"  {'-'*70}")
    for i,r in enumerate(results):
        g=grade(r["bull"])
        ic="▲"if"BUY"in r["verdict"]else("▼"if"SELL"in r["verdict"]else"─")
        flag=" ★"if r["bull"]>=4 else""
        print(f"  {i+1:<4} {r['sym']:<12} {r['price']:<10.3f} {g:<5} {ic} {r['verdict']:<12} {r['bull']}/{r['total']:<5} {r['zone']}{flag}")

    top=[r for r in results if r["bull"]>=3]
    if top:
        print(f"\n{'='*60}")
        print(f"  TOP PICKS - EKSEKUSI ENTRY")
        print(f"{'='*60}")
        nm=["Macro","Smart $","Technical","Sentiment","Zone"]
        ic_={"BULLISH":"▲","BEARISH":"▼","NEUTRAL":"─"}
        for r in top:
            g=grade(r["bull"])
            print(f"\n  {'─'*50}")
            print(f"  {r['sym']}  |  Grade:{g}  |  {r['verdict']}  |  ${r['price']:.3f}  |  Chg:{r['chg']}%")
            print(f"  {'─'*50}")
            for i,ly in enumerate(r["layers"]):
                lb=ly[0];vs="▲"if lb=="BULLISH"else("▼"if lb=="BEARISH"else"─")
                print(f"    {nm[i]:12s}: {vs} {ly[1]}")
            print()
            if r["bull_ob"]:
                o=r["bull_ob"];print(f"    OB Bull   : ${o['l']:.3f} - ${o['h']:.3f}")
            if r["bear_ob"]:
                o=r["bear_ob"];print(f"    OB Bear   : ${o['l']:.3f} - ${o['h']:.3f}")
            if "BUY" in r["verdict"] and r["bull_ob"]:
                o=r["bull_ob"]
                print(f"    ┌─ ENTRY  : ${o['l']:.3f} - ${o['h']:.3f}")
                print(f"    ├─ SL     : ${o['l']-0.15:.3f}")
                print(f"    ├─ TP1    : ${r['price']+0.30:.3f}")
                print(f"    └─ TP2    : ${r['price']+0.50:.3f}")
            elif "SELL" in r["verdict"] and r["bear_ob"]:
                o=r["bear_ob"]
                print(f"    ┌─ ENTRY  : ${o['l']:.3f} - ${o['h']:.3f}")
                print(f"    ├─ SL     : ${o['h']+0.15:.3f}")
                print(f"    ├─ TP1    : ${r['price']-0.30:.3f}")
                print(f"    └─ TP2    : ${r['price']-0.50:.3f}")
    else:
        print(f"\n  Tidak ada pair grade B+. Tunggu setup terbaik.")

    print(f"\n{'='*60}\n")

if __name__=="__main__":
    run()
