#!/usr/bin/env python3
"""TRADE NOTIFICATION - Termux Auto Alert"""
import subprocess

def notify(title, content, sound=True, vibrate=500):
    """Kirim notifikasi ke Termux"""
    cmd = ["termux-notification", "--title", title, "--content", content]
    if sound: cmd.append("--sound")
    if vibrate: cmd.extend(["--vibrate", str(vibrate)])
    try: subprocess.run(cmd, capture_output=True, timeout=5)
    except: pass

def toast(msg):
    """Pop-up di layar"""
    try: subprocess.run(["termux-toast", msg], capture_output=True, timeout=5)
    except: pass

def vibrate(ms=300):
    """Getar HP"""
    try: subprocess.run(["termux-vibrate", "-d", str(ms)], capture_output=True, timeout=5)
    except: pass

def alert_trade(pair, direction, entry, sl, tp1, tp2, rr, grade):
    """Full alert untuk trade baru"""
    emoji = "+" if direction == "BUY" else "-"
    title = f"{pair} {direction} [Grade:{grade}]"
    content = f"Entry: {entry} | SL: {sl} | TP: {tp1} | RR: 1:{rr}"
    notify(title, content, sound=True, vibrate=500)
    toast(f"{pair} {direction} @ {entry}")

def alert_tp(trade_id, pair, pnl_pips):
    """Alert saat TP hit"""
    emoji = "WIN" if pnl_pips > 0 else "LOSS"
    title = f"{emoji} - {pair} #{trade_id}"
    content = f"PnL: {pnl_pips:+.1f} pips"
    notify(title, content, sound=True, vibrate=1000)
    toast(f"{pair} {pnl_pips:+.1f} pips")

def alert_scan_result(pair, direction, grade, score):
    """Alert scan selesai"""
    title = f"Scan: {pair} {direction}"
    content = f"Grade:{grade} | Score:{score}/5"
    notify(title, content, sound=False, vibrate=200)
