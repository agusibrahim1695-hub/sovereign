#!/usr/bin/env python3
"""MULTI-LAYER CONFLUENCE - Core Engine v3 (Multi-API Key)"""
import requests,itertools,time

API_KEYS = [
    "93ef121c0685411cbdd6c556bcfb5eee",
    "96f10037ed494dfb87b541b9848a628d",
    "77bb656a183e41349aeaaff3d178b9f7",
    "c5ba341585554d6893f2a1d5f25433e3",
]
_key_cycle = itertools.cycle(API_KEYS)
B = "https://api.twelvedata.com"
_last_call = 0

def _next_key():
    global _last_call
    # Rate limit: min 1.5s between calls
    elapsed = time.time() - _last_call
    if elapsed < 1.5:
        time.sleep(1.5 - elapsed)
    _last_call = time.time()
    return next(_key_cycle)

def fc(s,iv,n=200):
    try:
        r=requests.get(f"{B}/time_series",params={"symbol":s,"interval":iv,"outputsize":n,"apikey":_next_key()},timeout=15).json()
        if "values" not in r: return []
        return [{"dt":v["datetime"],"o":float(v["open"]),"h":float(v["high"]),"l":float(v["low"]),"c":float(v["close"])} for v in reversed(r["values"])]
    except: return []

def fp(s):
    try:
        r=requests.get(f"{B}/quote?symbol={s}&apikey={_next_key()}",timeout=10).json()
        if "close" not in r: return None,None
        return float(r["close"]),r
    except: return None,None

def sw(cs,n=3):
    sh,sl=[],[]
    for i in range(n,len(cs)-n):
        h,l=cs[i]["h"],cs[i]["l"]
        if all(cs[i-j]["h"]<h for j in range(1,n+1)) and all(cs[i+j]["h"]<h for j in range(1,n+1)):
            sh.append({"i":i,"p":h,"d":cs[i]["dt"]})
        if all(cs[i-j]["l"]>l for j in range(1,n+1)) and all(cs[i+j]["l"]>l for j in range(1,n+1)):
            sl.append({"i":i,"p":l,"d":cs[i]["dt"]})
    return sh,sl

def tr(cs):
    sh,sl=sw(cs)
    a=[{"t":"H","p":s["p"],"i":s["i"],"d":s["d"]} for s in sh]+[{"t":"L","p":s["p"],"i":s["i"],"d":s["d"]} for s in sl]
    a.sort(key=lambda x:x["i"])
    prev_h=None;prev_l=None;ls=[]
    for s in a:
        if s["t"]=="H":
            if prev_h is None: lb="H"
            elif s["p"]>prev_h: lb="HH"
            elif s["p"]<prev_h: lb="LH"
            else: lb="EH"
            prev_h=s["p"]
        else:
            if prev_l is None: lb="L"
            elif s["p"]>prev_l: lb="HL"
            elif s["p"]<prev_l: lb="LL"
            else: lb="EL"
            prev_l=s["p"]
        s["lb"]=lb;ls.append(s)
    hi=[s for s in ls if s["t"]=="H" and s["lb"] in("HH","LH")]
    lo=[s for s in ls if s["t"]=="L" and s["lb"] in("HL","LL")]
    rH=hi[-3:]if len(hi)>=3 else hi
    rL=lo[-3:]if len(lo)>=3 else lo
    hh=sum(1 for s in rH if s["lb"]=="HH")
    hl=sum(1 for s in rL if s["lb"]=="HL")
    lh=sum(1 for s in rH if s["lb"]=="LH")
    ll=sum(1 for s in rL if s["lb"]=="LL")
    if hh>=2 and hl>=2: return "BULLISH",sh,sl
    elif lh>=2 and ll>=2: return "BEARISH",sh,sl
    return "NEUTRAL",sh,sl

def dob(cs):
    ob=[]
    for i in range(2,len(cs)-1):
        c=cs[i];ft=cs[i+1:min(i+6,len(cs))]
        if not ft: continue
        if c["c"]<c["o"]:
            mv=max(f["h"]for f in ft)-c["l"]
            if mv/c["l"]*100>=0.05 and not any(cs[j]["l"]<=c["h"]and cs[j]["c"]<=c["l"]for j in range(i+6,len(cs))):
                ob.append({"t":"B","h":c["h"],"l":c["l"],"d":c["dt"]})
        if c["c"]>c["o"]:
            mv=c["h"]-min(f["l"]for f in ft)
            if mv/c["h"]*100>=0.05 and not any(cs[j]["h"]>=c["h"]and cs[j]["c"]>=c["l"]for j in range(i+6,len(cs))):
                ob.append({"t":"S","h":c["h"],"l":c["l"],"d":c["dt"]})
    return ob[-10:]

def dfvg(cs):
    fv=[]
    for i in range(1,len(cs)-1):
        c1,c2,c3=cs[i-1],cs[i],cs[i+1];mg=(c1["h"]+c1["l"])/2*0.0001
        if c1["h"]<c3["l"]:
            g=c3["l"]-c1["h"]
            if g>=mg and not any(cs[j]["l"]<=c3["l"]and cs[j]["h"]>=c1["h"]for j in range(i+2,len(cs))):
                fv.append({"t":"B","h":c3["l"],"l":c1["h"],"g":g,"d":c2["dt"]})
        if c1["l"]>c3["h"]:
            g=c1["l"]-c3["h"]
            if g>=mg and not any(cs[j]["h"]>=c3["h"]and cs[j]["l"]<=c1["l"]for j in range(i+2,len(cs))):
                fv.append({"t":"S","h":c1["l"],"l":c3["h"],"g":g,"d":c2["dt"]})
    return fv[-10:]

def dliq(sh,sl):
    li=[]
    for i in range(len(sh)):
        for j in range(i+1,len(sh)):
            if abs(sh[i]["p"]-sh[j]["p"])/sh[i]["p"]*100<0.15:
                li.append({"t":"EQH","p":(sh[i]["p"]+sh[j]["p"])/2})
    for i in range(len(sl)):
        for j in range(i+1,len(sl)):
            if abs(sl[i]["p"]-sl[j]["p"])/sl[i]["p"]*100<0.15:
                li.append({"t":"EQL","p":(sl[i]["p"]+sl[j]["p"])/2})
    for s in sh[-5:]: li.append({"t":"BSL","p":s["p"]})
    for s in sl[-5:]: li.append({"t":"SSL","p":s["p"]})
    return li

def gzone(p,sh,sl):
    if not sh or not sl: return "UNKNOWN",0
    hi=max(s["p"]for s in sh[-5:]);lo=min(s["p"]for s in sl[-5:]);rng=hi-lo
    if rng==0: return "UNKNOWN",0
    f=(p-lo)/rng
    if f<0.3: return "DEEP DISCOUNT",f
    elif f<0.5: return "DISCOUNT",f
    elif f<0.7: return "PREMIUM",f
    return "DEEP PREMIUM",f

def dbos(cs):
    ev=[];lc=cs[-1]["c"];sh,sl=sw(cs)
    for h in reversed(sh[-3:]):
        if lc>h["p"]: ev.append({"t":"BOS","d":"BULL","p":h["p"]});break
    for l in reversed(sl[-3:]):
        if lc<l["p"]: ev.append({"t":"BOS","d":"BEAR","p":l["p"]});break
    return ev

def L1(dt,wt):
    if dt=="BULLISH"and wt=="BULLISH": return "BULLISH","Macro kuat bullish"
    elif dt=="BEARISH"and wt=="BEARISH": return "BEARISH","Macro kuat bearish"
    elif dt=="BULLISH": return "BULLISH","Daily bullish"
    elif dt=="BEARISH": return "BEARISH","Daily bearish"
    return "NEUTRAL","Macro netral"

def L2(ob,fv,lq,p):
    sc=0;nt=[]
    for o in ob:
        if o["t"]=="B"and o["l"]<=p<=o["h"]+0.1: sc+=2;nt.append("Di Bullish OB")
        if o["t"]=="S"and o["l"]-0.1<=p<=o["h"]: sc-=2;nt.append("Di Bearish OB")
    for f in fv:
        if f["t"]=="B"and f["l"]<=p<=f["h"]+0.1: sc+=1;nt.append("Di Bullish FVG")
        if f["t"]=="S"and f["l"]-0.1<=p<=f["h"]: sc-=1;nt.append("Di Bearish FVG")
    for l in lq:
        if l["t"]=="SSL"and p<=l["p"]+0.05: sc+=2;nt.append("SSL swept")
    if sc>=2: return "BULLISH","; ".join(nt)if nt else"Accumulation"
    elif sc<=-2: return "BEARISH","; ".join(nt)if nt else"Distribution"
    return "NEUTRAL","; ".join(nt)if nt else"Netral"

def L3(h4t,h1t,bos):
    b,s=0,0
    if h4t=="BULLISH": b+=2
    elif h4t=="BEARISH": s+=2
    if h1t=="BULLISH": b+=1
    elif h1t=="BEARISH": s+=1
    for e in bos:
        if e["d"]=="BULL": b+=1
        elif e["d"]=="BEAR": s+=1
    if b>s+1: return "BULLISH",f"H4:{h4t} H1:{h1t}"
    elif s>b+1: return "BEARISH",f"H4:{h4t} H1:{h1t}"
    return "NEUTRAL",f"H4:{h4t} H1:{h1t}"

def L4(cs):
    if len(cs)<5: return "NEUTRAL","Data kurang"
    l5=cs[-5:];bu=sum(1 for c in l5 if c["c"]>c["o"]);be=sum(1 for c in l5 if c["c"]<c["o"])
    last=cs[-1];bd=abs(last["c"]-last["o"]);tt=last["h"]-last["l"];rt=bd/tt if tt>0 else 0
    l3=cs[-3:];cb=sum(1 for c in l3 if c["c"]>c["o"]);cr=sum(1 for c in l3 if c["c"]<c["o"])
    sc=0;nt=[]
    if bu>=4: sc+=1;nt.append(f"{bu}/5 bull")
    elif be>=4: sc-=1;nt.append(f"{be}/5 bear")
    if rt>0.7:
        if last["c"]>last["o"]: sc+=1;nt.append("Strong bull body")
        else: sc-=1;nt.append("Strong bear body")
    if cb==3: sc+=1;nt.append("3x consecutive bull")
    elif cr==3: sc-=1;nt.append("3x consecutive bear")
    if sc>=1: return "BULLISH","; ".join(nt)
    elif sc<=-1: return "BEARISH","; ".join(nt)
    return "NEUTRAL","Mixed"

def L5(zn,f):
    if "DISCOUNT" in zn: return "BULLISH",f"{zn}(fib:{f:.1%})"
    elif "PREMIUM" in zn: return "BEARISH",f"{zn}(fib:{f:.1%})"
    return "NEUTRAL",zn

def vrd(ly):
    bu=sum(1 for l in ly if l[0]=="BULLISH");be=sum(1 for l in ly if l[0]=="BEARISH");t=len(ly)
    if bu>=4: v="STRONG BUY"
    elif bu>=3: v="BUY"
    elif be>=4: v="STRONG SELL"
    elif be>=3: v="SELL"
    else: v="WAIT"
    return v,bu,be,t
