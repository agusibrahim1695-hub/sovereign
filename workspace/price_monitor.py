#!/usr/bin/env python3
"""PRICE MONITOR v4 - Live price notif UPDATE + SL/TP alert"""
import sys,time
sys.path.insert(0,".")
from smc_core import fp
from trade_journal import get_db
from trade_notify import notify

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

            # Hitung PnL sementara
            if d == "BUY":
                pnl = price - entry
            else:
                pnl = entry - price
            pnl_pct = (pnl / entry) * 100

            # Update LIVE notif (selalu, pakai --id biar ganti)
            pnl_icon = "+" if pnl >= 0 else ""
            if d == "BUY":
                dist_tp = f"TP: {((tp1-price)/price*100):.2f}%"
                dist_sl = f"SL: {((price-sl)/price*100):.2f}%"
            else:
                dist_tp = f"TP: {((price-tp1)/price*100):.2f}%"
                dist_sl = f"SL: {((sl-price)/price*100):.2f}%"

            content = f"Now: {price:.3f} | PnL: {pnl_icon}{pnl:.1f}p ({pnl_pct:+.2f}%) | {dist_tp} | {dist_sl}"
            title = f"{sym} {d} | TP:{tp1:.3f} SL:{sl:.3f}"
            notify(title, content, sound=False, vibrate=0, nid=f"live_{sym}")

            # Check SL hit
            if trade["sl_notified"] == 0:
                sl_hit = (d == "BUY" and price <= sl) or (d == "SELL" and price >= sl)
                if sl_hit:
                    notify(f"!!! SL HIT: {sym}", f"#{tid} {pnl:+.1f} pips | CLOSED", sound=True, vibrate=1000, nid=f"alert_{sym}")
                    conn.execute("UPDATE trades SET sl_notified=1, status='CLOSED', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! SL HIT: {sym} #{tid} | {pnl:+.1f} pips")

            # Check TP1 hit
            if trade["tp_notified"] == 0:
                tp1_hit = (d == "BUY" and price >= tp1) or (d == "SELL" and price <= tp1)
                if tp1_hit:
                    notify(f"!!! TP1 HIT: {sym}", f"#{tid} {pnl:+.1f} pips | CLOSED", sound=True, vibrate=1000, nid=f"alert_{sym}")
                    conn.execute("UPDATE trades SET tp_notified=1, status='CLOSED', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! TP1 HIT: {sym} #{tid} | {pnl:+.1f} pips")

            # Check TP2 hit
            if trade["tp_notified"] == 0:
                tp2_hit = (d == "BUY" and price >= tp2) or (d == "SELL" and price <= tp2)
                if tp2_hit:
                    notify(f"!!! TP2 HIT: {sym}", f"#{tid} {pnl:+.1f} pips | CLOSED", sound=True, vibrate=1000, nid=f"alert_{sym}")
                    conn.execute("UPDATE trades SET tp_notified=1, status='CLOSED', exit_price=?, pnl_pips=? WHERE id=?", (price, round(pnl,3), tid))
                    print(f"  !!! TP2 HIT: {sym} #{tid} | {pnl:+.1f} pips")

            print(f"  {sym}: {price:.3f} | PnL: {pnl:+.1f}p ({pnl_pct:+.2f}%)")

    conn.commit()
    conn.close()

def run_monitor():
    print(f"\n{'='*50}")
    print(f"  LIVE PRICE MONITOR v4")
    print(f"  Update every {CHECK_INTERVAL}s")
    print(f"{'='*50}\n")
    try:
        while True:
            check_prices()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n  Monitor stopped")

if __name__ == "__main__":
    run_monitor()
