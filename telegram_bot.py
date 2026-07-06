#!/usr/bin/env python3
"""
Telegram interface buat agent. Chat ke bot lo:

  buatkan script python cek harga BTC dari API publik
  /auto buatkan script python cek harga BTC dari API publik   -> mode full-auto
  /provider claude buatkan ...                                 -> pilih provider sekali jalan

Kalau ada step risky & mode confirm, bot bakal nanya balik "y/n" di chat -> lo balas aja.
Jalanin: python telegram_bot.py
"""
import threading
import time
import requests
import config
from agent import Agent

API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
ALLOWED_CHAT_ID = str(config.TELEGRAM_ALLOWED_CHAT_ID)

# state konfirmasi per chat: {chat_id: {"event": Event, "answer": bool}}
pending = {}
pending_lock = threading.Lock()


def send_message(chat_id, text):
    for chunk_start in range(0, max(len(text), 1), 3500):
        chunk = text[chunk_start : chunk_start + 3500] or text
        try:
            requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": chunk}, timeout=20)
        except Exception as e:
            print(f"[telegram] gagal kirim pesan: {e}")
        if not text:
            break


def ask_confirm_telegram(chat_id):
    def _ask(name, args):
        ev = threading.Event()
        with pending_lock:
            pending[chat_id] = {"event": ev, "answer": False}
        send_message(chat_id, f"⚠️ AI mau jalanin tool RISKY:\n{name}({args})\n\nBalas 'y' untuk izinkan, 'n' untuk tolak.")
        got = ev.wait(timeout=300)  # tunggu max 5 menit
        with pending_lock:
            answer = pending.get(chat_id, {}).get("answer", False)
            pending.pop(chat_id, None)
        if not got:
            send_message(chat_id, "⏱️ timeout, dianggap ditolak.")
            return False
        return answer

    return _ask


def run_agent_task(chat_id, task, mode, provider_name):
    agent = Agent(
        provider_name=provider_name,
        mode=mode,
        notify=lambda t: send_message(chat_id, t),
        ask_confirm=ask_confirm_telegram(chat_id),
    )
    send_message(chat_id, f"🚀 Mulai (mode={mode}, provider={provider_name or 'default'})\nTask: {task}")
    try:
        agent.run(task)
    except Exception as e:
        send_message(chat_id, f"[error] agent crash: {e}")


def handle_message(chat_id, text):
    text = text.strip()

    # kalau lagi nunggu jawaban konfirmasi buat chat ini
    with pending_lock:
        waiting = chat_id in pending
    if waiting and text.lower() in ("y", "n", "ya", "tidak"):
        answer = text.lower() in ("y", "ya")
        with pending_lock:
            if chat_id in pending:
                pending[chat_id]["answer"] = answer
                pending[chat_id]["event"].set()
        return

    if text.lower() in ("/start", "/help"):
        send_message(
            chat_id,
            "SOVEREIGN Agent siap.\n\n"
            "Ketik langsung task-nya (default mode = confirm, bakal nanya sebelum eksekusi risky).\n"
            "Prefix opsional:\n"
            "/auto <task>        -> full otomatis tanpa tanya\n"
            "/provider claude <task> / groq / openai\n",
        )
        return

    mode = "confirm"
    provider_name = None

    if text.startswith("/auto"):
        mode = "auto"
        text = text[len("/auto") :].strip()

    if text.startswith("/provider"):
        parts = text.split(maxsplit=2)
        if len(parts) >= 3:
            provider_name = parts[1]
            text = parts[2]

    if not text:
        send_message(chat_id, "Task-nya kosong, ketik perintahnya bro.")
        return

    threading.Thread(target=run_agent_task, args=(chat_id, text, mode, provider_name), daemon=True).start()


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN belum di-set di .env")
        return
    print("🤖 SOVEREIGN Telegram bot jalan... (Ctrl+C untuk stop)")
    offset = 0
    while True:
        try:
            resp = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=40)
            data = resp.json()
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg or "text" not in msg:
                    continue
                chat_id = str(msg["chat"]["id"])
                if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
                    send_message(chat_id, "Chat ini tidak diizinkan pakai bot ini.")
                    continue
                handle_message(chat_id, msg["text"])
        except Exception as e:
            print(f"[telegram] polling error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
