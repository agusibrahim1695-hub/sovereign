#!/usr/bin/env python3
"""
Portal SOVEREIGN Agent — chat interaktif dengan MEMORI PERSISTEN.
Obrolan otomatis kesimpen tiap abis chat, otomatis keload lagi pas dibuka ulang.
Bisa punya beberapa sesi/proyek terpisah pakai /save dan /load.
"""
import argparse
import json
import os
import config
import sync
from agent import Agent

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)
LAST_SESSION = os.path.join(SESSION_DIR, "_last.json")

BANNER = r"""
   _____ ______      ________ _____  ______ _____ _____ _   _
  / ____|  _ \ \    / /  ____|  __ \|  ____|_   _/ ____| \ | |
 | (___ | |_) \ \  / /| |__  | |__) | |__    | || |  __|  \| |
  \___ \|  _ < \ \/ / |  __| |  _  /|  __|   | || | |_ | . ` |
  ____) | |_) | \  /  | |____| | \ \| |____ _| || |__| | |\  |
 |_____/|____/   \/   |______|_|  \_\______|_____\_____|_| \_|

         Autonomous Agent Portal — ketik bebas, gue kerjain.
"""


def ask_confirm_cli(name, args):
    print(f"\n⚠️  AI mau jalanin tool RISKY: {name}({args})")
    ans = input("Izinkan? [y/n]: ").strip().lower()
    return ans == "y"


def session_path(name):
    safe = "".join(c for c in name if c.isalnum() or c in "-_")
    return os.path.join(SESSION_DIR, f"{safe}.json")


def save_session(path, agent):
    try:
        with open(path, "w") as f:
            json.dump(agent.messages, f)
        sync.push_sessions()
    except Exception as e:
        print(f"[warning] gagal simpan sesi: {e}")


def load_session(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def list_sessions():
    files = [f[:-5] for f in os.listdir(SESSION_DIR) if f.endswith(".json") and not f.startswith("_")]
    return files


def print_help(agent):
    print(
        f"""
Status -> provider: {getattr(agent, "provider_name", None) or config.DEFAULT_PROVIDER} | mode: {agent.mode}

Command:
  /help                -> bantuan ini
  /reset               -> mulai obrolan baru (buang history sesi ini)
  /save <nama>         -> simpan sesi sekarang sebagai proyek bernama <nama>
  /load <nama>         -> buka proyek <nama> (history-nya kesambung lagi)
  /sessions            -> lihat daftar proyek yang pernah disimpan
  /provider <nama>     -> ganti provider: groq / claude / openai / mimo
  /mode auto|confirm   -> ganti mode eksekusi tool
  /exit                -> keluar (obrolan otomatis kesimpen, lanjut lagi pas dibuka ulang)

Ketik bebas aja buat ngobrol atau nyuruh bikinin/jalanin sesuatu.
"""
    )


def main():
    parser = argparse.ArgumentParser(description="SOVEREIGN Agent Portal")
    parser.add_argument("--provider", default=None, help="groq | claude | openai | mimo")
    parser.add_argument("--auto", action="store_true", help="mulai dengan mode full-auto")
    parser.add_argument("--confirm", action="store_true", help="mulai dengan mode confirm (override .env)")
    parser.add_argument("--fresh", action="store_true", help="mulai obrolan baru, jangan lanjutin sesi terakhir")
    args = parser.parse_args()
    if args.auto:
        mode = "auto"
    elif args.confirm:
        mode = "confirm"
    else:
        mode = config.DEFAULT_MODE

    agent = Agent(
        provider_name=args.provider,
        mode=mode,
        notify=lambda t: print(f"\n🤖 {t}\n"),
        ask_confirm=ask_confirm_cli,
    )
    agent.provider_name = args.provider or config.DEFAULT_PROVIDER

    print(BANNER)
    sync.pull_sessions()

    resumed = False
    if not args.fresh:
        loaded = load_session(LAST_SESSION)
        if loaded:
            agent.messages = loaded
            resumed = True

    print(f"provider: {agent.provider_name} | mode: {mode}  (/help untuk daftar command)")
    if resumed:
        n_user = sum(1 for m in agent.messages if m["role"] == "user")
        print(f"📂 Lanjut sesi sebelumnya ({n_user} pesan). Pakai --fresh atau /reset buat mulai baru.\n")
    else:
        print("Sesi baru dimulai.\n")

    while True:
        try:
            user_input = input("Lo   : ").strip()
        except (EOFError, KeyboardInterrupt):
            save_session(LAST_SESSION, agent)
            print("\nSOVEREIGN off, obrolan kesimpen. Sampai ketemu lagi, bro.")
            break

        if not user_input:
            continue

        if user_input == "/exit":
            save_session(LAST_SESSION, agent)
            print("SOVEREIGN off, obrolan kesimpen. Sampai ketemu lagi, bro.")
            break

        if user_input == "/help":
            print_help(agent)
            continue

        if user_input == "/reset":
            agent.reset()
            save_session(LAST_SESSION, agent)
            print("[obrolan direset]\n")
            continue

        if user_input == "/sessions":
            sess = list_sessions()
            print("Proyek tersimpan:\n  " + ("\n  ".join(sess) if sess else "(belum ada)") + "\n")
            continue

        if user_input.startswith("/save"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                print("Pakai: /save nama_proyek")
                continue
            save_session(session_path(parts[1].strip()), agent)
            print(f"[disimpan sebagai proyek: {parts[1].strip()}]\n")
            continue

        if user_input.startswith("/load"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                print("Pakai: /load nama_proyek")
                continue
            loaded = load_session(session_path(parts[1].strip()))
            if loaded is None:
                print(f"[error] proyek '{parts[1].strip()}' gak ketemu. Cek /sessions")
            else:
                agent.messages = loaded
                n_user = sum(1 for m in agent.messages if m["role"] == "user")
                print(f"[proyek '{parts[1].strip()}' diload, {n_user} pesan]\n")
            continue

        if user_input.startswith("/provider"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                print("Pakai: /provider groq|claude|openai|mimo")
                continue
            try:
                agent.set_provider(parts[1].strip())
                print(f"[provider diganti ke: {parts[1].strip()}]\n")
            except Exception as e:
                print(f"[error] {e}")
            continue

        if user_input.startswith("/mode"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2 or parts[1].strip() not in ("auto", "confirm"):
                print("Pakai: /mode auto  atau  /mode confirm")
                continue
            agent.set_mode(parts[1].strip())
            print(f"[mode diganti ke: {parts[1].strip()}]\n")
            continue

        agent.chat(user_input)
        save_session(LAST_SESSION, agent)


if __name__ == "__main__":
    main()
