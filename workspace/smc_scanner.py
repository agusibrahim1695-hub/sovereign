#!/usr/bin/env python3
"""MULTI-PAIR SMC SCANNER v5 - 6 Pair + Synthetic DXY + Strategy Entry"""
import sys,time,math
sys.path.insert(0,".")
from smc_core import fc,fp,tr,dob,dfvg,dliq,dbos,gzone,L1,L2,L3,L4,L5,vrd,API_KEYS
from trade_journal import log_trade
from trade_notify import alert_trade

PAIRS = [
    "XAU/USD","EUR/USD","GBP/USD",
    "USD/JPY","USD/CAD","USD/CHF",
]

# DXY weights (major components)
DXY_FORMULA = {
    "EUR/USD": {"weight": -0.576, "mult": 50.14348112},
    "GBP/USD": {"weight": -0.119},
    "USD/JPY": {"weight": 0.136},
    "USD/CAD": {"weight": 0.091},
    "USD/CHF": {"weight": 0.036},
}

def scan_pair(sym):
    daily=fc(sym,"1day",100);time.sleep(0.3)
    h4=fc(sym,"4h",200);time.sleep(0.3)
    h1=fc(sym,"1h",200);time.sleep(0.3)
    price,qt=fp(sym);time.sleep(0.3)
    if not price or not daily or not h1: return None
    dt,_,_=tr(daily)if daily else('NEUTRAL',[],[])
    h4t,_,_=tr(h4)if h4 else('NEUTRAL',[],[])
    h1t,h1sh,h1sl=tr(h1)
    obs=dob(h1);fvs=dfvg(h1);lq=dliq(h1sh,h1sl);bos=dbos(h1)
    zn,fib=gzone(price,h1sh,h1sl)
    ly=[L1(dt,h4t),L2(obs,fvs,lq,price),L3(h4t,h1t,bos),L4(h1),L5(zn,fib)]
    v,bu,be,tot=vrd(ly)
    chg=qt.get('percent_change','?')if qt else'?'
    buo=[o for o in obs if o['t']=='B']
    beo=[o for o in obs if o['t']=='S']
    buo_n=sorted(buo,key=lambda x:abs(price-(x['l']+x['h'])/2))[:1]if buo else[]
    beo_n=sorted(beo,key=lambda x:abs(price-(x['l']+x['h'])/2))[:1]if beo else[]
    # High/Low daily for SL/TP
    hi=qt.get('high',0)if qt else 0
    lo=qt.get('low',0)if qt else 0
    op=qt.get('open',0)if qt else 0
    return {
        'sym':sym,'price':price,'chg':chg,'layers':ly,'verdict':v,
        'bull':bu,'bear':be,'total':tot,'zone':zn,'fib':fib,
        'bull_ob':buo_n[0]if buo_n else None,
        'bear_ob':beo_n[0]if beo_n else None,
        'high':float(hi)if hi else 0,'low':float(lo)if lo else 0,'open':float(op)if op else 0,
    }

def calc_dxy(prices):
    """Hitung synthetic DXY dari harga-harga pair"""
    mult = DXY_FORMULA["EUR/USD"]["mult"]
    dxy = mult
    for sym, cfg in DXY_FORMULA.items():
        if sym in prices:
            dxy *= prices[sym] ** cfg["weight"]
    return round(dxy, 3)

def dxy_trend(daily_data):
    """Analisis trend DXY dari data synthetik"""
    if not daily_data or len(daily_data) < 5:
        return "NEUTRAL", "Data kurang"
    last = daily_data[-1]
    prev = daily_data[-5]
    chg = ((last - prev) / prev) * 100
    if chg > 0.5:
        return "BULLISH", f"DXY naik {chg:.2f}% (5 hari)"
    elif chg < -0.5:
        return "BEARISH", f"DXY turun {chg:.2f}% (5 hari)"
    return "NEUTRAL", f"DXY sideways ({chg:+.2f}%)"

def dxy_corr(dxy_dir, sym):
    """Korelasi DXY terhadap pair:
    - USD pairs: DXY naik = pair naik (positif)
    - EUR/GBP/XAU: DXY naik = pair turun (negatif)
    """
    neg_corr = ["EUR/USD", "GBP/USD", "XAU/USD"]
    if dxy_dir == "BULLISH":
        if sym in neg_corr:
            return "CONTRA", "Bearish (DXY↑ → pair↓)"
        else:
            return "CONFLUENT", "Bullish (DXY↑ → pair↑)"
    elif dxy_dir == "BEARISH":
        if sym in neg_corr:
            return "CONFLUENT", "Bullish (DXY↓ → pair↑)"
        else:
            return "CONTRA", "Bearish (DXY↓ → pair↓)"
    return "NEUTRAL", "Netral"

def strategy_entry(r, dxy_dir, dxy_corr_type):
    """Generate detailed entry strategy berdasarkan confluence"""
    sym = r['sym']
    price = r['price']
    bull = r['bull']
    bear = r['bear']
    verdict = r['verdict']
    h = r['high']
    lo = r['low']
    o = r['open']
    r_range = h - lo if h and lo else 0

    # Pair-specific pip values
    pips = {"XAU/USD": 1.0, "USD/JPY": 0.01, "EUR/USD": 0.0001, "GBP/USD": 0.0001, "USD/CAD": 0.0001, "USD/CHF": 0.0001}
    pip = pips.get(sym, 0.0001)

    # SL & TP berdasarkan range
    sl_pips = max(r_range * 0.5, 30 * pip)  # minimal 30 pip
    tp1_pips = sl_pips * 1.5
    tp2_pips = sl_pips * 2.5

    direction = None
    entry = None
    sl = None
    tp1 = None
    tp2 = None
    risk = ""

    if "BUY" in verdict and (dxy_corr_type == "CONFLUENT" or dxy_corr_type == "NEUTRAL"):
        direction = "BUY"
        if r['bull_ob']:
            entry = f"{r['bull_ob']['l']:.5f} - {r['bull_ob']['h']:.5f}"
            sl = r['bull_ob']['l'] - sl_pips
        else:
            entry = f"{price:.5f}"
            sl = price - sl_pips
        tp1 = price + tp1_pips
        tp2 = price + tp2_pips
        risk = f"RR 1:{tp1_pips/sl_pips:.1f}" if sl_pips > 0 else ""

    elif "SELL" in verdict and (dxy_corr_type == "CONFLUENT" or dxy_corr_type == "NEUTRAL"):
        direction = "SELL"
        if r['bear_ob']:
            entry = f"{r['bear_ob']['l']:.5f} - {r['bear_ob']['h']:.5f}"
            sl = r['bear_ob']['h'] + sl_pips
        else:
            entry = f"{price:.5f}"
            sl = price + sl_pips
        tp1 = price - tp1_pips
        tp2 = price - tp2_pips
        risk = f"RR 1:{tp1_pips/sl_pips:.1f}" if sl_pips > 0 else ""

    # Bonus confluence score
    conf_score = bull
    if dxy_corr_type == "CONFLUENT":
        conf_score += 1
        risk += " +DXY✓"
    elif dxy_corr_type == "CONTRA":
        conf_score -= 1
        risk += " -DXY✗"

    return {
        'direction': direction or "WAIT",
        'entry': entry or f"{price:.5f}",
        'sl': f"{sl:.5f}" if sl else "?",
        'tp1': f"{tp1:.5f}" if tp1 else "?",
        'tp2': f"{tp2:.5f}" if tp2 else "?",
        'rr': round(tp1_pips/sl_pips, 1) if sl_pips > 0 else 0,
        'risk': risk,
        'conf_score': conf_score,
        'dxy_corr': dxy_corr_type,
    }

def grade(s):
    if s>=5: return 'S+'
    elif s>=4: return 'A'
    elif s>=3: return 'B'
    elif s>=2: return 'C'
    return 'D'

def run():
    print(f"\n{'='*60}")
    print(f"  SMC SCANNER v5 - 6 PAIR + SYNTHETIC DXY")
    print(f"  API Keys: {len(API_KEYS)} | Pairs: {len(PAIRS)}")
    print(f"{'='*60}\n")

    # ═══ SCAN ALL PAIRS ═══
    results = []
    prices_for_dxy = {}
    daily_data_dxy = []

    for sym in PAIRS:
        sys.stdout.write(f'  {sym}...')
        sys.stdout.flush()
        try:
            r = scan_pair(sym)
            if r:
                results.append(r)
                g = grade(r['bull'])
                print(f" {r['verdict']} ({r['bull']}/{r['total']}) Grade:{g}")
                # Collect for DXY calc
                prices_for_dxy[sym] = r['price']
            else:
                print(f' SKIP')
        except Exception as e:
            print(f' ERR: {e}')

    # ═══ CALC SYNTHETIC DXY ═══
    print(f"\n  Calculating synthetic DXY...")
    dxy_price = calc_dxy(prices_for_dxy) if len(prices_for_dxy) >= 4 else 0

    # ═══ RANKING + DXY CORRELATION ═══
    for r in results:
        corr_type, corr_note = dxy_trend_summary(dxy_price), ""
        if r['sym'] in DXY_FORMULA:
            ct, cn = dxy_corr("BULLISH" if dxy_price > 100 else "BEARISH", r['sym'])
            r['dxy_corr'] = ct
            r['dxy_note'] = cn
        else:
            r['dxy_corr'] = "N/A"
            r['dxy_note'] = "No correlation"
        strat = strategy_entry(r, "BULLISH" if dxy_price > 100 else "BEARISH", r['dxy_corr'])
        r['strategy'] = strat

    # Sort by confluence score
    results.sort(key=lambda x: x['strategy']['conf_score'], reverse=True)

    # ═══ OUTPUT ═══
    now_str = time.strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*60}")
    print(f"  DXY SYNTHETIC: {dxy_price} | Trend: {'BULLISH' if dxy_price > 100 else 'BEARISH'}")
    print(f"{'='*60}")
    print(f"\n  {'#':<4} {'Pair':<12} {'Price':<10} {'Grade':<6} {'Verdict':<14} {'Score':<7} {'DXY':<10}")
    print(f"  {'-'*65}")
    for i, r in enumerate(results):
        g = grade(r['bull'])
        ic = '▲' if 'BUY' in r['strategy']['direction'] else ('▼' if 'SELL' in r['strategy']['direction'] else '─')
        flag = ' ★' if r['strategy']['conf_score'] >= 4 else ''
        print(f"  {i+1:<4} {r['sym']:<12} {r['price']:<10.3f} {g:<6} {ic} {r['strategy']['direction']:<12} {r['strategy']['conf_score']:<7} {r['dxy_corr']}{flag}")

    # ═══ TOP PICKS WITH STRATEGY ═══
    top = [r for r in results if r['strategy']['conf_score'] >= 3]
    if top:
        nm = ['Macro', 'Smart $', 'Technical', 'Sentiment', 'Zone']
        print(f"\n{'='*60}")
        print(f"  🏆 TOP PICKS - STRATEGY ENTRY")
        print(f"{'='*60}")
        for r in top:
            g = grade(r['bull'])
            s = r['strategy']
            print(f"\n  {'━'*55}")
            print(f"  {r['sym']} | Grade:{g} | {s['direction']} | ${r['price']:.3f}")
            print(f"  DXY Corr: {r['dxy_corr']} ({r['dxy_note']})")
            print(f"  Conf Score: {s['conf_score']}/6 {s['risk']}")
            print(f"  {'━'*55}")

            for i, ly in enumerate(r['layers']):
                lb = ly[0]
                vs = '▲' if lb == 'BULLISH' else ('▼' if lb == 'BEARISH' else '─')
                print(f"    {nm[i]:12s}: {vs} {ly[1]}")

            if r['bull_ob']:
                o = r['bull_ob']
                print(f"    OB Bull   : ${o['l']:.3f} - ${o['h']:.3f}")
            if r['bear_ob']:
                o = r['bear_ob']
                print(f"    OB Bear   : ${o['l']:.3f} - ${o['h']:.3f}")

            print(f"\n    STRATEGY:")
            print(f"    Direction : {s['direction']}")
            print(f"    Entry     : {s['entry']}")
            print(f"    SL        : {s['sl']}")
            print(f"    TP1       : {s['tp1']}")
            print(f"    TP2       : {s['tp2']}")
            print(f"    RR        : 1:{s['rr']}")
            print(f"    Score     : {s['conf_score']}/5")

            # AUTO LOG + NOTIF
            if s['direction'] in ['BUY','SELL']:
                try:
                    layers_data = [l[1] for l in r['layers']]
                    entry_val = float(s['entry'].split('-')[0].strip())
                    trade_id = log_trade(
                        pair=r['sym'], direction=s['direction'],
                        entry=entry_val, sl=float(s['sl']),
                        tp1=float(s['tp1']), tp2=float(s['tp2']),
                        rr=float(s['rr']), conviction=s['conf_score'],
                        grade=grade(r['bull']),
                        layers=layers_data,
                        verdict=f"{s['direction']} ({r['bull']}/{r['total']})"
                    )
                    print(f"    LOGGED: Trade #{trade_id}")
                    alert_trade(r['sym'], s['direction'], s['entry'], s['sl'], s['tp1'], s['tp2'], s['rr'], grade(r['bull']))
                except Exception as e:
                    print(f"    LOG ERR: {e}")
    else:
        print(f"\n  Tidak ada setup. Tunggu confluence lebih kuat.")

    print(f"\n{'='*60}\n")

def dxy_trend_summary(dxy_price):
    return "BULLISH" if dxy_price > 100 else "BEARISH"

if __name__ == "__main__":
    run()
