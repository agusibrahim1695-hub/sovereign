#!/usr/bin/env python3
"""
Menu setting SOVEREIGN Agent. Diakses lewat: SOVEREIGN setup
Baca & ubah isi .env secara interaktif, tanpa perlu buka nano manual.
"""
import os
import sys
import tty
import termios
import requests

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# (key, label, is_secret)
FIELDS = [
    ("DEFAULT_PROVIDER", "Provider default (groq/claude/openai/mimo)", False),
    ("DEFAULT_MODE", "Mode default (auto/confirm)", False),
    ("", "── Groq ──", None),
    ("GROQ_API_KEY", "Groq API Key", True),
    ("", "── Claude (Anthropic) ──", None),
    ("ANTHROPIC_API_KEY", "Claude API Key", True),
    ("", "── OpenAI ──", None),
    ("OPENAI_API_KEY", "OpenAI API Key", True),
    ("OPENAI_BASE_URL", "OpenAI Base URL", False),
    ("", "── MiMo ──", None),
    ("MIMO_API_KEY", "MiMo API Key", True),
    ("MIMO_BASE_URL", "MiMo Base URL", False),
    ("MIMO_MODEL", "MiMo Model name", False),
    ("", "── Web Search ──", None),
    ("SERPER_API_KEY", "Serper API Key", True),
    ("", "── Telegram ──", None),
    ("TELEGRAM_BOT_TOKEN", "Telegram Bot Token", True),
    ("TELEGRAM_ALLOWED_CHAT_ID", "Telegram Allowed Chat ID", False),
    ("", "── GitHub Sync ──", None),
    ("GITHUB_TOKEN", "GitHub Token", True),
    ("GITHUB_REPO", "GitHub Repo (format: username/repo)", False),
    ("GITHUB_BRANCH", "GitHub Branch", False),
    ("", "── Lain-lain ──", None),
    ("WORKSPACE_DIR", "Folder workspace", False),
    ("MAX_ITERS", "Max iterasi agent per task", False),
    ("BASH_TIMEOUT", "Timeout bash exec (detik)", False),
    ("", "── Custom Endpoint ──", None),
    ("CUSTOM_BASE_URL", "Custom Endpoint URL", False),
    ("CUSTOM_API_KEY", "Custom Endpoint API Key", True),
    ("CUSTOM_MODEL", "Custom Endpoint Model", False),
]

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"


def _load_lines():
    if not os.path.exists(ENV_PATH):
        return []
    with open(ENV_PATH, "r") as f:
        return f.read().splitlines()


def _get_dict(lines):
    d = {}
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        d[k.strip()] = v.strip()
    return d


def _set_value(lines, key, value):
    new_lines = []
    found = False
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k == key:
                new_lines.append(f"{key}={value}")
                found = True
                continue
        new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    return new_lines


def _save_lines(lines):
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")

def _getch():
    """Baca 1 tombol (termasuk panah atas/bawah) dari keyboard."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def _select_model(models):
    """Menu pilih model pakai panah atas/bawah + Enter."""
    idx = 0
    while True:
        print("\033[2J\033[H", end="")
        print(f"{CYAN}{BOLD}Pilih model (↑/↓ lalu Enter):{RESET}\n")
        for i, m in enumerate(models):
            if i == idx:
                print(f"  {GREEN}➤ {m}{RESET}")
            else:
                print(f"    {m}")
        key = _getch()
        if key == "\x1b[A":
            idx = (idx - 1) % len(models)
        elif key == "\x1b[B":
            idx = (idx + 1) % len(models)
        elif key in ("\r", "\n"):
            return models[idx]
        elif key == "\x03":
            raise KeyboardInterrupt


def _fetch_models(base_url, api_key):
    """Ambil daftar model dari endpoint OpenAI-compatible (GET /models)."""
    try:
        resp = requests.get(
            f"{base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return sorted(m["id"] for m in data.get("data", []))
    except Exception as e:
        print(f"{YELLOW}Gagal ambil daftar model otomatis: {e}{RESET}")
        return []


def _setup_custom_endpoint(lines):
    print(f"\n{CYAN}{BOLD}=== Setup Custom Endpoint (OpenAI-compatible) ==={RESET}\n")
    base_url = input("Endpoint API (contoh: https://api.contoh.com/v1): ").strip()
    if not base_url:
        print(f"{DIM}Dibatalkan.{RESET}")
        return lines

    api_key = input("API Key: ").strip()
    if not api_key:
        print(f"{DIM}Dibatalkan.{RESET}")
        return lines

    print(f"\n{DIM}Mengambil daftar model dari endpoint...{RESET}")
    models = _fetch_models(base_url, api_key)

    if not models:
        model = input("Gak ketemu otomatis. Ketik nama model manual: ").strip()
        if not model:
            print(f"{DIM}Dibatalkan.{RESET}")
            return lines
    else:
        model = _select_model(models)

    lines = _set_value(lines, "CUSTOM_BASE_URL", base_url)
    lines = _set_value(lines, "CUSTOM_API_KEY", api_key)
    lines = _set_value(lines, "CUSTOM_MODEL", model)
    lines = _set_value(lines, "DEFAULT_PROVIDER", "custom")
    _save_lines(lines)

    print(f"\n{GREEN}✓ Custom endpoint diatur & dijadikan provider default.{RESET}")
    print(f"  Endpoint : {base_url}")
    print(f"  Model    : {model}")
    input("\nTekan Enter buat lanjut...")
    return lines

def _mask(value):
    if not value:
        return f"{DIM}(belum diisi){RESET}"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}...{value[-4:]}"


def _print_menu(env):
    print(f"\n{CYAN}{BOLD}=== SOVEREIGN — Menu Setting ==={RESET}\n")
    idx = 1
    numbered = []
    for key, label, is_secret in FIELDS:
        if is_secret is None:
            print(f"{YELLOW}{label}{RESET}")
            continue
        current = env.get(key, "")
        shown = _mask(current) if is_secret else (current or f"{DIM}(belum diisi){RESET}")
        print(f"  {GREEN}{idx:2}{RESET}. {label:38} = {shown}")
        numbered.append(key)
        idx += 1
    print(f"\n  {GREEN} 0{RESET}. Keluar\n")
    return numbered

def run():
    lines = _load_lines()
    while True:
        env = _get_dict(lines)
        numbered = _print_menu(env)
        print(f"  {GREEN} C{RESET}. Setup Custom Endpoint (auto-detect model)\n")
        choice = input("Pilih nomor/huruf (0 buat keluar): ").strip()

        if choice == "0" or choice == "":
            print("Selesai. Perubahan tersimpan otomatis tiap kali diedit.")
            return

        if choice.lower() == "c":
            lines = _setup_custom_endpoint(lines)
            continue

        if not choice.isdigit() or not (1 <= int(choice) <= len(numbered)):
            print(f"{YELLOW}Nomor gak valid, coba lagi.{RESET}")
            continue

        key = numbered[int(choice) - 1]
        current = env.get(key, "")
        print(f"\nNilai sekarang: {current or '(kosong)'}")
        new_value = input(f"Nilai baru buat {key} (Enter buat batal): ").strip()

        if not new_value:
            print(f"{DIM}Dibatalkan, gak ada perubahan.{RESET}")
            continue

        lines = _set_value(lines, key, new_value)
        _save_lines(lines)
        print(f"{GREEN}✓ {key} berhasil diupdate & disimpan ke .env{RESET}")


if __name__ == "__main__":
    run()
