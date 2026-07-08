#!/usr/bin/env python3
"""
SOVEREIGN Agent v2.5 — CLI Entry Point
Jalankan: python main.py
"""
import sys
import os

# Pastikan bisa import module di directory yang sama
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import Agent


def main():
    print("=" * 50)
    print("  🧠 SOVEREIGN Agent v2.5")
    print("  Autonomous Coding/Ops Agent")
    print("=" * 50)
    print()
    print("Perintah:")
    print("  /reset    - Mulai obrolan baru")
    print("  /stop     - Hentikan agent yang sedang jalan")
    print("  /mode     - Toggle auto/confirm mode")
    print("  /provider - Ganti provider (groq/claude/openai/mimo)")
    print("  /cost     - Lihat total cost")
    print("  /quit     - Keluar")
    print()

    agent = Agent(
        mode="auto",
        notify=print,
    )

    print(f"📡 Provider: {agent.provider_name} ({agent.provider.model})")
    print(f"🔧 Mode: {agent.mode}")
    print(f"📊 Context: {agent.provider.context_window // 1000}K tokens")
    print()

    while True:
        try:
            user_input = input("🧑 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Bye!")
            break

        if not user_input:
            continue

        # Handle slash commands
        if user_input.lower() == "/quit":
            print("👋 Bye!")
            break
        elif user_input.lower() == "/reset":
            agent.reset()
            print("🔄 Obrolan di-reset. Mulai fresh!")
            continue
        elif user_input.lower() == "/stop":
            agent.request_stop()
            continue
        elif user_input.lower() == "/mode":
            new_mode = "confirm" if agent.mode == "auto" else "auto"
            agent.set_mode(new_mode)
            print(f"🔧 Mode: {new_mode}")
            continue
        elif user_input.lower() == "/provider":
            print("Pilih provider: groq, claude, openai, mimo")
            try:
                choice = input("Provider: ").strip().lower()
                if choice:
                    agent.set_provider(choice)
                    print(f"📡 Provider: {agent.provider_name} ({agent.provider.model})")
            except (EOFError, KeyboardInterrupt):
                pass
            continue
        elif user_input.lower() == "/cost":
            print(f"💰 Total cost: ${agent.total_cost:.5f}")
            print(f"📊 Total tokens: {agent.session_tokens}")
            continue

        # Normal chat
        print()
        agent.chat(user_input)
        print()


if __name__ == "__main__":
    main()
