#!/usr/bin/env python3
"""TRADE NOTIFICATION - Termux Auto Alert"""
import subprocess

def notify(title, content, sound=True, vibrate=500, nid=None):
    """Kirim notifikasi ke Termux. pakai --id biar update, bukan baru"""
    cmd = ["termux-notification", "--title", title, "--content", content]
    if nid: cmd.extend(["--id", str(nid)])
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

def clear_notification(nid):
    """Hapus notifikasi by ID"""
    try: subprocess.run(["termux-notification-remove", str(nid)], capture_output=True, timeout=5)
    except: pass

def alert_trade(pair, direction, entry, sl, tp1, tp2, rr, grade):
    """Alert trade baru - cuma 1 notif"""
    nid = f"smc_{pair}"
    title = f"{pair} {direction} [Grade:{grade}]"
    content = f"Entry: {entry} | SL: {sl} | TP: {tp1} | RR: 1:{rr}"
    notify(title, content, sound=True, vibrate=500, nid=nid)

def alert_tp(trade_id, pair, pnl_pips):
    """Alert SL/TP hit - auto close"""
    nid = f"smc_{pair}"
    emoji = "WIN" if pnl_pips > 0 else "LOSS"
    title = f"{emoji} - {pair} #{trade_id}"
    content = f"PnL: {pnl_pips:+.1f} pips"
    notify(title, content, sound=True, vibrate=1000, nid=nid)
    clear_notification(f"monitor_{pair}")

def alert_scan_result(pair, direction, grade, score):
    """Alert scan selesai"""
    nid = f"scan_{pair}"
    title = f"Scan: {pair} {direction}"
    content = f"Grade:{grade} | Score:{score}/5"
    notify(title, content, sound=False, vibrate=200, nid=nid)

def alert_monitor_started(interval):
    """Monitor started - 1 notif"""
    notify("Monitor Started", f"Watching every {interval}s", sound=False, vibrate=200, nid="monitor_status")
