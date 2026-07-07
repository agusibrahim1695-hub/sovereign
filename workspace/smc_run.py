#!/usr/bin/env python3
"""MULTI-LAYER CONFLUENCE - Runner & Report v2"""
import sys
from smc_core import fc,fp,tr,dob,dfvg,dliq,dbos,gzone,L1,L2,L3,L4,L5,vrd
from datetime import datetime

def run(sym="USD/JPY"):
    print(f"\nFetching {sym} data...")
    daily=fc(sym,"1day",100);h4=fc(sym,"4h",200);h1=fc(sym,"1h",200)
    price,qt=fp(sym)
    if not price: print("Error: harga tidak tersedia");return

    dt,_,_=tr(daily)if daily else("NEUTRAL",[],[])
    h4t,_,_=tr(h4)if h4 else("NEUTRAL",[],[])
    h1t,h1sh,h1sl=tr(h1)if h1 else("NEUTRAL",[],[])
    obs=dob(h1)if h1 else[];fvs=dfvg(h1)if h1 else[]
    lq=dliq(h1sh,h1sl);bos=dbos(h1)if h1 else[]
    zn,fib=gzone(price,h1sh,h1sl)

    ly=[L1(dt,h4t),L2(obs,fvs,lq,price),L3(h4t,h1t,bos),L4(h1),L5(zn,fib)]
    v,bu,be,tot=vrd(ly)
    now=datetime.now().strftime("%Y-%m-%d %H:%M")
    ic={"BULLISH":"▲","BEARISH":"▼","NEUTRAL":"─"}
    nm=["Macro","Smart $","Technical","Sentiment","Zone"]
    chg=qt.get("percent_change","?")if qt else"?"

    # Header
    print(f"\n{'='*55}")
    print(f"  MULTI-LAYER CONFLUENCE - {sym}")
    print(f"  {now}")
    print(f"{'='*55}")
    print(f"  Price    : {price:.3f}  |  Change: {chg}%")
    print(f"{'='*55}")

    # 5 Layers
    print(f"\n  CONFLUENCE LAYERS:")
    print(f"  {'-'*50}")
    for i in range(len(ly)):
        lb=ly[i][0]
        vs="▲ Bullish"if lb=="BULLISH"else("▼ Bearish"if lb=="BEARISH"else"─ Neutral")
        print(f"  {nm[i]:12s} : {ic[lb]} {vs:12s} {ly[i][1]}")

    # Verdict
    print(f"\n  {'='*50}")
    if "BUY" in v: vc="🟢"
    elif "SELL" in v: vc="🔴"
    else: vc="⚪"
    print(f"  {vc} VERDICT: {v} ({bu}/{tot} bullish)")
    print(f"  {'='*50}")

    # Key Levels
    buo=[o for o in obs if o["t"]=="B"]
    beo=[o for o in obs if o["t"]=="S"]
    buf=[f for f in fvs if f["t"]=="B"]
    bef=[f for f in fvs if f["t"]=="S"]

    # Nearest OB & FVG only
    buo_near=sorted([o for o in buo], key=lambda x:abs(price-(x["l"]+x["h"])/2))[:2]
    beo_near=sorted([o for o in beo], key=lambda x:abs(price-(x["l"]+x["h"])/2))[:2]
    buf_near=sorted([f for f in buf], key=lambda x:abs(price-(x["l"]+x["h"])/2))[:2]
    bef_near=sorted([f for f in bef], key=lambda x:abs(price-(x["l"]+x["h"])/2))[:2]

    print(f"\n  KEY LEVELS:")
    print(f"  {'-'*50}")
    if buo_near:
        print(f"  Support / Bullish OB :")
        for o in buo_near: print(f"    ${o['l']:.3f} - ${o['h']:.3f}")
    if beo_near:
        print(f"  Resistance / Bearish OB :")
        for o in beo_near: print(f"    ${o['l']:.3f} - ${o['h']:.3f}")
    if buf_near:
        print(f"  Bullish FVG :")
        for f in buf_near: print(f"    ${f['l']:.3f} - ${f['h']:.3f} (gap:${f['g']:.3f})")
    if bef_near:
        print(f"  Bearish FVG :")
        for f in bef_near: print(f"    ${f['l']:.3f} - ${f['h']:.3f} (gap:${f['g']:.3f})")

    # Liquidity - closest 5 only
    ssl=[l for l in lq if l["t"]=="SSL"]
    bsl=[l for l in lq if l["t"]=="BSL"]
    ssl_near=sorted(ssl,key=lambda x:abs(x["p"]-price))[:3]
    bsl_near=sorted(bsl,key=lambda x:abs(x["p"]-price))[:3]

    if ssl_near or bsl_near:
        print(f"\n  LIQUIDITY:")
        print(f"  {'-'*50}")
        if ssl_near:
            print(f"  SSL (Sell-side):")
            for l in ssl_near: print(f"    ${l['p']:.3f}")
        if bsl_near:
            print(f"  BSL (Buy-side):")
            for l in bsl_near: print(f"    ${l['p']:.3f}")

    # Zone
    print(f"\n  ZONE: {zn} (fib: {fib:.1%})")

    # Trade Plan
    print(f"\n  {'='*50}")
    print(f"  TRADE PLAN")
    print(f"  {'='*50}")
    if "BUY" in v:
        zo=buo_near[0]if buo_near else None
        zf=buf_near[0]if buf_near else None
        if zo: entry=f"{zo['l']:.3f} - {zo['h']:.3f}";sl=f"{zo['l']-0.15:.3f}"
        elif zf: entry=f"{zf['l']:.3f} - {zf['h']:.3f}";sl=f"{zf['l']-0.15:.3f}"
        else: entry=f"{price:.3f}";sl=f"{price-0.30:.3f}"
        tgt1=f"{price+0.30:.3f}";tgt2=f"{price+0.50:.3f}"
        print(f"  Direction : BUY")
        print(f"  Entry     : {entry}")
        print(f"  Stop Loss : {sl}")
        print(f"  TP1       : {tgt1}")
        print(f"  TP2       : {tgt2}")
    elif "SELL" in v:
        zo=beo_near[0]if beo_near else None
        zf=bef_near[0]if bef_near else None
        if zo: entry=f"{zo['l']:.3f} - {zo['h']:.3f}";sl=f"{zo['h']+0.15:.3f}"
        elif zf: entry=f"{zf['l']:.3f} - {zf['h']:.3f}";sl=f"{zf['h']+0.15:.3f}"
        else: entry=f"{price:.3f}";sl=f"{price+0.30:.3f}"
        tgt1=f"{price-0.30:.3f}";tgt2=f"{price-0.50:.3f}"
        print(f"  Direction : SELL")
        print(f"  Entry     : {entry}")
        print(f"  Stop Loss : {sl}")
        print(f"  TP1       : {tgt1}")
        print(f"  TP2       : {tgt2}")
    else:
        print(f"  Tidak ada setup saat ini")
        print(f"  Tunggu konfirmasi layer berikutnya")
    print(f"\n{'='*55}\n")

if __name__=="__main__":
    sym=sys.argv[1]if len(sys.argv)>1 else"USD/JPY"
    run(sym)
