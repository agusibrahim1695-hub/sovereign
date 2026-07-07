#!/usr/bin/env python3
"""PRICE MONITOR v5 - Notif ONLY saat event (entry/SL/TP)"""
import sys,time
sys.path.insert(0,".")
from smc_core import fp
from trade_journal import get_db
from trade_notify import notify, toast

CHECK_INTERVAL = 10

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

            # ENTRY hit - sekali
            if trade["entry_notified"] == 0:
                if d == "BUY" and price >= entry:
                    notify(f"ENTRY: {sym} {d}", f"Price {price:.3f} >= Entry {entry:.3f}", sound=True, vibrate=500, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET entry_notified=1 WHERE id=?", (tid,))
                    print(f"  >>> ENTRY: {sym} #{tid} @ {price:.3f}")
                elif d == "SELL" and price <= entry:
                    notify(f"ENTRY: {sym} {d}", f"Price {price:.3f} <= Entry {entry:.3f}", sound=True, vibrate=500, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET entry_notified=1 WHERE id=?", (tid,))
                    print(f"  >>> ENTRY: {sym} #{tid} @ {price:.3f}")

            # SL hit - sekali + auto close
            if trade["sl_notified"] == 0:
                sl_hit = (d == "BUY" and price <= sl) or (d == "SELL" and price >= sl)
                if sl_hit:
                    pnl = (price - entry) if d == "BUY" else (entry - price)
                    notify(f"SL HIT: {sym}", f"#{tid} {pnl:+.1f} pips", sound=True, vibrate=1000, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET sl_notified=1, status='CLOSED', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! SL: {sym} #{tid} | {pnl:+.1f}p")

            # TP1 hit - sekali + auto close
            if trade["tp_notified"] == 0:
                tp1_hit = (d == "BUY" and price >= tp1) or (d == "SELL" and price <= tp1)
                if tp1_hit:
                    pnl = (price - entry) if d == "BUY" else (entry - price)
                    notify(f"TP1 HIT: {sym}", f"#{tid} {pnl:+.1f} pips", sound=True, vibrate=1000, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET tp_notified=1, status='CLOSED', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! TP1: {sym} #{tid} | {pnl:+.1f}p")

            # TP2 hit - sekali + auto close
            if trade["tp_notified"] == 0:
                tp2_hit = (d == "BUY" and price >= tp2) or (d == "SELL" and price <= tp2)
                if tp2_hit:
                    pnl = (price - entry) if d == "BUY" else (entry - price)
                    notify(f"TP2 HIT: {sym}", f"#{tid} {pnl:+.1f} pips", sound=True, vibrate=1000, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET tp_notified=1, status='CLOSED', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! TP2: {sym} #{tid} | {pnl:+.1f}p")

    conn.commit()
    conn.close()

def run_monitor():
    print(f"\n{'='*50}")
    print(f"  MONITOR v5 - Event only (no live update)")
    print(f"  Checking every {CHECK_INTERVAL}s")
    print(f"{'='*50}\n")
    try:
        while True:
            check_prices()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n  Stopped")

if __name__ == "__main__":
    run_monitor()
