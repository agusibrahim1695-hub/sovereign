#!/usr/bin/env python3
"""
Portal SOVEREIGN Agent — chat interaktif, history persisten dalam satu sesi.
"""
import argparse
import config
import sync
from agent import Agent

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


def print_help(agent):
    print(
        f"""
Status sekarang -> provider: {getattr(agent, "provider_name", None) or config.DEFAULT_PROVIDER} | mode: {agent.mode}

Command:
  /help                -> bantuan ini
  /reset               -> mulai obrolan baru (buang history)
  /provider <nama>     -> ganti provider: groq / claude / openai / mimo
  /mode auto           -> full otomatis, gak nanya konfirmasi
  /mode confirm        -> tanya dulu sebelum tool risky (bash/install/write)
  /exit                -> keluar

Selain itu, ketik bebas aja -- ngobrol, brainstorming, atau nyuruh bikinin/jalanin sesuatu.
"""
    )


def main():
    parser = argparse.ArgumentParser(description="SOVEREIGN Agent Portal")
    parser.add_argument("--provider", default=None, help="groq | claude | openai | mimo")
    parser.add_argument("--auto", action="store_true", help="mulai dengan mode full-auto")
    args = parser.parse_args()
    mode = "auto" if args.auto else "confirm"

    agent = Agent(
        provider_name=args.provider,
        mode=mode,
        notify=lambda t: print(f"\n🤖 {t}\n"),
        ask_confirm=ask_confirm_cli,
    )
    agent.provider_name = args.provider or config.DEFAULT_PROVIDER

    print(BANNER)
    print(f"provider: {agent.provider_name} | mode: {mode}  (/help untuk daftar command)\n")

    while True:
        try:
            user_input = input("Lo   : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSOVEREIGN off. Sampai ketemu lagi, bro.")
            break

        if not user_input:
            continue

        if user_input == "/exit":
            print("SOVEREIGN off. Sampai ketemu lagi, bro.")
            break

        if user_input == "/help":
            print_help(agent)
            continue

        if user_input == "/reset":
            agent.reset()
            print("[obrolan direset]\n")
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


if __name__ == "__main__":
    main()
