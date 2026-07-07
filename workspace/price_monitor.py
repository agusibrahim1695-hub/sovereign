#!/usr/bin/env python3
"""PRICE MONITOR - Watch open trades, alert on entry/SL/TP hit"""
import sys,time,threading
sys.path.insert(0,".")
from smc_core import fp
from trade_journal import get_db, close_trade, print_stats
from trade_notify import notify, toast, alert_tp

CHECK_INTERVAL = 10  # detik

def get_open_trades():
    conn = get_db()
    rows = conn.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()
    conn.close()
    return rows

def check_prices():
    trades = get_open_trades()
    if not trades:
        print(f"  [{time.strftime('%H:%M:%S')}] No open trades")
        return

    print(f"  [{time.strftime('%H:%M:%S')}] Checking {len(trades)} open trades...")
    checked = set()
    for t in trades:
        sym = t["pair"]
        if sym in checked:
            continue
        checked.add(sym)
        price, _ = fp(sym)
        if not price:
            continue

        for trade in trades:
            if trade["pair"] != sym:
                continue
            tid = trade["id"]
            direction = trade["direction"]
            entry = trade["entry"]
            sl = trade["sl"]
            tp1 = trade["tp1"]
            tp2 = trade["tp2"]
            entry_range = 0.002 if entry < 5 else 0.2  # adjust pip threshold

            # Check ENTRY zone
            if abs(price - entry) < entry_range and direction == "BUY":
                notify(f"ENTRY HIT - {sym}", f"Price: {price:.3f} ~= Entry: {entry:.3f}")
                toast(f"ENTRY: {sym} @ {price:.3f}")

            # Check SL hit
            if direction == "BUY" and price <= sl:
                pnl = price - entry
                close_trade(tid, price, "SL_HIT")
                alert_tp(tid, sym, pnl)
                print(f"  !!! SL HIT: {sym} #{tid} | PnL: {pnl:+.1f} pips")
                time.sleep(0.3)
                close_trade(tid, price, "SL_HIT")

            elif direction == "SELL" and price >= sl:
                pnl = entry - price
                alert_tp(tid, sym, pnl)
                print(f"  !!! SL HIT: {sym} #{tid} | PnL: {pnl:+.1f} pips")
                time.sleep(0.3)
                close_trade(tid, price, "SL_HIT")

            # Check TP1 hit
            if direction == "BUY" and price >= tp1:
                pnl = price - entry
                alert_tp(tid, sym, pnl)
                print(f"  !!! TP1 HIT: {sym} #{tid} | PnL: {pnl:+.1f} pips")
                time.sleep(0.3)
                close_trade(tid, price, "TP1_HIT")

            elif direction == "SELL" and price <= tp1:
                pnl = entry - price
                alert_tp(tid, sym, pnl)
                print(f"  !!! TP1 HIT: {sym} #{tid} | PnL: {pnl:+.1f} pips")
                time.sleep(0.3)
                close_trade(tid, price, "TP1_HIT")

            # Check TP2 hit
            if direction == "BUY" and price >= tp2:
                pnl = price - entry
                alert_tp(tid, sym, pnl)
                print(f"  !!! TP2 HIT: {sym} #{tid} | PnL: {pnl:+.1f} pips")
                time.sleep(0.3)
                close_trade(tid, price, "TP2_HIT")

            elif direction == "SELL" and price <= tp2:
                pnl = entry - price
                alert_tp(tid, sym, pnl)
                print(f"  !!! TP2 HIT: {sym} #{tid} | PnL: {pnl:+.1f} pips")
                time.sleep(0.3)
                close_trade(tid, price, "TP2_HIT")

        print(f"  {sym}: {price:.3f}")

def run_monitor():
    print(f"\n{'='*50}")
    print(f"  PRICE MONITOR STARTED")
    print(f"  Checking every {CHECK_INTERVAL}s")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*50}\n")
    notify("Monitor Started", f"Watching trades every {CHECK_INTERVAL}s")
    try:
        while True:
            check_prices()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n  Monitor stopped")
        notify("Monitor Stopped", "Price monitor stopped")

if __name__ == "__main__":
    run_monitor()
