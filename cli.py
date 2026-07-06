#!/usr/bin/env python3
"""
Pakai langsung di Termux:

  python cli.py "buatkan bot telegram simple echo" --auto
  python cli.py "install ta-lib dan bikin script hitung RSI" --provider claude
  python cli.py "clone repo X dan jalankan" --confirm   (default)

Mode default = confirm (aman). Pakai --auto kalau mau full otomatis tanpa ditanya.
"""
import argparse
from agent import Agent


def ask_confirm_cli(name, args):
    print(f"\n⚠️  AI mau jalanin tool RISKY: {name}({args})")
    ans = input("Izinkan? [y/n]: ").strip().lower()
    return ans == "y"


def main():
    parser = argparse.ArgumentParser(description="SOVEREIGN Agent CLI")
    parser.add_argument("task", help="Perintah/task untuk agent")
    parser.add_argument("--provider", default=None, help="groq | claude | openai")
    parser.add_argument("--auto", action="store_true", help="Mode full-auto, skip semua konfirmasi")
    parser.add_argument("--confirm", action="store_true", help="Mode confirm (default)")
    parser.add_argument("--max-iters", type=int, default=None)
    args = parser.parse_args()

    mode = "auto" if args.auto else "confirm"

    agent = Agent(
        provider_name=args.provider,
        mode=mode,
        notify=lambda t: print(f"\n{t}"),
        ask_confirm=ask_confirm_cli,
    )
    print(f"🚀 Mulai task (mode={mode}, provider={args.provider or 'default'}): {args.task}\n")
    agent.run(args.task, max_iters=args.max_iters)


if __name__ == "__main__":
    main()
