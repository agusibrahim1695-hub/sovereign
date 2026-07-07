#!/usr/bin/env python3
"""TRADE JOURNAL - SQLite Auto-Log"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_journal.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            pair TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry REAL NOT NULL,
            sl REAL NOT NULL,
            tp1 REAL NOT NULL,
            tp2 REAL NOT NULL,
            rr REAL,
            conviction INTEGER,
            grade TEXT,
            macro TEXT,
            smart_money TEXT,
            technical TEXT,
            sentiment TEXT,
            zone TEXT,
            verdict TEXT,
            status TEXT DEFAULT 'OPEN',
            exit_price REAL,
            exit_time TEXT,
            pnl_pips REAL,
            pnl_percent REAL,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_trade(pair, direction, entry, sl, tp1, tp2, rr, conviction, grade, layers, verdict, notes=""):
    """Auto-save trade entry ke journal"""
    conn = get_db()
    conn.execute("""
        INSERT INTO trades (
            timestamp, pair, direction, entry, sl, tp1, tp2, rr,
            conviction, grade, macro, smart_money, technical, sentiment,
            zone, verdict, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        pair, direction, entry, sl, tp1, tp2, rr,
        conviction, grade,
        layers[0] if len(layers) > 0 else "",
        layers[1] if len(layers) > 1 else "",
        layers[2] if len(layers) > 2 else "",
        layers[3] if len(layers) > 3 else "",
        layers[4] if len(layers) > 4 else "",
        verdict, notes
    ))
    conn.commit()
    trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return trade_id

def close_trade(trade_id, exit_price, status="CLOSED"):
    """Update trade status"""
    conn = get_db()
    trade = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
    if trade:
        if trade["direction"] == "BUY":
            pnl_pips = exit_price - trade["entry"]
        else:
            pnl_pips = trade["entry"] - exit_price

        pnl_percent = (pnl_pips / trade["entry"]) * 100

        conn.execute("""
            UPDATE trades SET status=?, exit_price=?, exit_time=?, pnl_pips=?, pnl_percent=?
            WHERE id=?
        """, (status, exit_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              round(pnl_pips, 3), round(pnl_percent, 4), trade_id))
        conn.commit()
    conn.close()

def get_open_trades():
    conn = get_db()
    rows = conn.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY timestamp DESC").fetchall()
    conn.close()
    return rows

def get_history(limit=20):
    conn = get_db()
    rows = conn.execute(f"SELECT * FROM trades ORDER BY timestamp DESC LIMIT {limit}").fetchall()
    conn.close()
    return rows

def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM trades WHERE status='CLOSED'").fetchone()["c"]
    wins = conn.execute("SELECT COUNT(*) as c FROM trades WHERE status='CLOSED' AND pnl_pips>0").fetchone()["c"]
    losses = conn.execute("SELECT COUNT(*) as c FROM trades WHERE status='CLOSED' AND pnl_pips<=0").fetchone()["c"]
    total_pnl = conn.execute("SELECT COALESCE(SUM(pnl_pips),0) as s FROM trades WHERE status='CLOSED'").fetchone()["s"]
    avg_win = conn.execute("SELECT COALESCE(AVG(pnl_pips),0) as a FROM trades WHERE status='CLOSED' AND pnl_pips>0").fetchone()["a"]
    avg_loss = conn.execute("SELECT COALESCE(AVG(pnl_pips),0) as a FROM trades WHERE status='CLOSED' AND pnl_pips<=0").fetchone()["a"]
    conn.close()
    win_rate = (wins/total*100) if total > 0 else 0
    return {
        "total": total, "wins": wins, "losses": losses,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 3),
        "avg_win": round(avg_win, 3),
        "avg_loss": round(avg_loss, 3)
    }

def print_journal():
    init_db()
    trades = get_history(10)
    print(f"\n{'='*60}")
    print(f"  TRADE JOURNAL (10 Terakhir)")
    print(f"{'='*60}")
    if not trades:
        print("  Belum ada trade tercatat")
    print(f"  {'#':<4} {'Date':<18} {'Pair':<10} {'Dir':<6} {'Entry':<10} {'Status':<8} {'PnL':<10}")
    print(f"  {'-'*70}")
    for t in trades:
        status_icon = "OPEN" if t["status"] == "OPEN" else ("WIN" if t["pnl_pips"] and t["pnl_pips"] > 0 else "LOSS")
        pnl = f"{t['pnl_pips']:+.1f}p" if t["pnl_pips"] else "-"
        print(f"  {t['id']:<4} {t['timestamp']:<18} {t['pair']:<10} {t['direction']:<6} {t['entry']:<10.3f} {status_icon:<8} {pnl:<10}")

def print_stats():
    init_db()
    s = get_stats()
    print(f"\n{'='*60}")
    print(f"  TRADE STATS")
    print(f"{'='*60}")
    print(f"  Total Trades : {s['total']}")
    print(f"  Wins         : {s['wins']}")
    print(f"  Losses       : {s['losses']}")
    print(f"  Win Rate     : {s['win_rate']}%")
    print(f"  Total PnL    : {s['total_pnl']:+.1f} pips")
    print(f"  Avg Win      : {s['avg_win']:+.1f} pips")
    print(f"  Avg Loss     : {s['avg_loss']:+.1f} pips")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    init_db()
    print("Journal DB initialized!")
    print_journal()
    print_stats()
