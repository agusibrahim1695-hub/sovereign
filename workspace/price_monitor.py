#!/usr/bin/env python3
"""PRICE MONITOR v6 - Entry/SL/TP hit + VOID trade"""
import sys,time
sys.path.insert(0,".")
from smc_core import fp
from trade_journal import get_db
from trade_notify import notify

CHECK_INTERVAL = 10
VOID_THRESHOLD_PIPS = 50  # Jauh dari entry = void

def get_pip_size(pair):
    if "JPY" in pair: return 0.01
    if "XAU" in pair: return 1.0
    return 0.0001

def check_prices():
    conn = get_db()
    trades = conn.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()
    if not trades:
        conn.close()
        return

    checked = set()
    for t in trades:
        sym = t["pair"]
        if sym in checked: continue
        checked.add(sym)
        price, _ = fp(sym)
        if not price: continue

        for trade in trades:
            if trade["pair"] != sym: continue
            tid = trade["id"]
            d = trade["direction"]
            entry = trade["entry"]
            sl = trade["sl"]
            tp1 = trade["tp1"]
            tp2 = trade["tp2"]
            pip = get_pip_size(sym)

            # JAUH dari entry = VOID (trade expired)
            if trade["sl_notified"] == 0 and trade["tp_notified"] == 0:
                void_pip = VOID_THRESHOLD_PIPS * pip
                if d == "BUY" and price > entry + void_pip:
                    notify(f"VOID: {sym}", f"#{tid} Price {price:.3f} too far above entry {entry:.3f}", sound=True, vibrate=500, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET sl_notified=1, status='VOID', void_reason='price_too_far_above' WHERE id=?", (tid,))
                    print(f"  !!! VOID: {sym} #{tid} | Price {price:.3f} >> Entry {entry:.3f}")
                elif d == "SELL" and price < entry - void_pip:
                    notify(f"VOID: {sym}", f"#{tid} Price {price:.3f} too far below entry {entry:.3f}", sound=True, vibrate=500, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET sl_notified=1, status='VOID', void_reason='price_too_far_below' WHERE id=?", (tid,))
                    print(f"  !!! VOID: {sym} #{tid} | Price {price:.3f} << Entry {entry:.3f}")

            # ENTRY hit
            if trade["entry_notified"] == 0:
                if d == "BUY" and price >= entry:
                    notify(f"ENTRY: {sym} {d}", f"Price {price:.3f} >= Entry {entry:.3f}", sound=True, vibrate=500, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET entry_notified=1 WHERE id=?", (tid,))
                    print(f"  >>> ENTRY: {sym} #{tid} @ {price:.3f}")
                elif d == "SELL" and price <= entry:
                    notify(f"ENTRY: {sym} {d}", f"Price {price:.3f} <= Entry {entry:.3f}", sound=True, vibrate=500, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET entry_notified=1 WHERE id=?", (tid,))
                    print(f"  >>> ENTRY: {sym} #{tid} @ {price:.3f}")

            # SL hit
            if trade["sl_notified"] == 0:
                sl_hit = (d == "BUY" and price <= sl) or (d == "SELL" and price >= sl)
                if sl_hit:
                    pnl = (price - entry) if d == "BUY" else (entry - price)
                    notify(f"SL HIT: {sym}", f"#{tid} {pnl:+.1f} pips", sound=True, vibrate=1000, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET sl_notified=1, status='SL_HIT', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! SL: {sym} #{tid} | {pnl:+.1f}p")

            # TP1 hit
            if trade["tp_notified"] == 0:
                tp1_hit = (d == "BUY" and price >= tp1) or (d == "SELL" and price <= tp1)
                if tp1_hit:
                    pnl = (price - entry) if d == "BUY" else (entry - price)
                    notify(f"TP1 HIT: {sym}", f"#{tid} {pnl:+.1f} pips", sound=True, vibrate=1000, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET tp_notified=1, status='TP1_HIT', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! TP1: {sym} #{tid} | {pnl:+.1f}p")

            # TP2 hit
            if trade["tp_notified"] == 0:
                tp2_hit = (d == "BUY" and price >= tp2) or (d == "SELL" and price <= tp2)
                if tp2_hit:
                    pnl = (price - entry) if d == "BUY" else (entry - price)
                    notify(f"TP2 HIT: {sym}", f"#{tid} {pnl:+.1f} pips", sound=True, vibrate=1000, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET tp_notified=1, status='TP2_HIT', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! TP2: {sym} #{tid} | {pnl:+.1f}p")

    conn.commit()
    conn.close()

def run_monitor():
    print(f"\n{'='*50}")
    print(f"  MONITOR v6 (entry/SL/TP + VOID)")
    print(f"  Checking every {CHECK_INTERVAL}s")
    print(f"  VOID threshold: {VOID_THRESHOLD_PIPS} pips")
    print(f"{'='*50}\n")
    try:
        while True:
            check_prices()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n  Stopped")

if __name__ == "__main__":
    run_monitor()
