#!/usr/bin/env python3
"""PRICE MONITOR v3 - Notify with --id (UPDATE, not new)"""
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
        print(f"  [{time.strftime('%H:%M:%S')}] No open trades")
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
            pip_thresh = 0.002 if entry < 10 else 0.15

            # Log console only (gak notif)
            if trade["entry_notified"] == 0:
                if abs(price - entry) < pip_thresh:
                    # Update notif yang udah ada (bukan baru)
                    notify(f"ACTIVE: {sym} {d}", f"Entry: {entry:.3f} | Now: {price:.3f} | SL: {sl:.3f} | TP: {tp1:.3f}", sound=True, vibrate=500, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET entry_notified=1 WHERE id=?", (tid,))
                    print(f"  >>> ENTRY HIT: {sym} #{tid} @ {price:.3f}")

            # SL hit
            if trade["sl_notified"] == 0:
                sl_hit = (d == "BUY" and price <= sl) or (d == "SELL" and price >= sl)
                if sl_hit:
                    pnl = (price - entry) if d == "BUY" else (entry - price)
                    notify(f"SL HIT: {sym}", f"#{tid} {pnl:+.1f} pips", sound=True, vibrate=1000, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET sl_notified=1, status='CLOSED', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! SL HIT: {sym} #{tid} | {pnl:+.1f} pips")

            # TP1 hit
            if trade["tp_notified"] == 0:
                tp1_hit = (d == "BUY" and price >= tp1) or (d == "SELL" and price <= tp1)
                if tp1_hit:
                    pnl = (price - entry) if d == "BUY" else (entry - price)
                    notify(f"TP1 HIT: {sym}", f"#{tid} {pnl:+.1f} pips", sound=True, vibrate=1000, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET tp_notified=1, status='CLOSED', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! TP1 HIT: {sym} #{tid} | {pnl:+.1f} pips")

            # TP2 hit
            if trade["tp_notified"] == 0:
                tp2_hit = (d == "BUY" and price >= tp2) or (d == "SELL" and price <= tp2)
                if tp2_hit:
                    pnl = (price - entry) if d == "BUY" else (entry - price)
                    notify(f"TP2 HIT: {sym}", f"#{tid} {pnl:+.1f} pips", sound=True, vibrate=1000, nid=f"smc_{sym}")
                    conn.execute("UPDATE trades SET tp_notified=1, status='CLOSED', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! TP2 HIT: {sym} #{tid} | {pnl:+.1f} pips")

        print(f"  {sym}: {price:.3f}")
    conn.commit()
    conn.close()

def run_monitor():
    print(f"\n{'='*50}")
    print(f"  PRICE MONITOR v3 (notify with --id)")
    print(f"  Checking every {CHECK_INTERVAL}s")
    print(f"{'='*50}\n")
    try:
        while True:
            check_prices()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n  Monitor stopped")

if __name__ == "__main__":
    run_monitor()
