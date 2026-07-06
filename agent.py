"""
Core agentic loop:
  1. Kirim task + history ke LLM (dengan daftar tools)
  2. LLM balas: teks status dan/atau tool_calls
  3. Kalau ada tool_call risky & mode='confirm' -> tanya user dulu
  4. Eksekusi tool, hasil dimasukkan lagi ke history
  5. Ulangi sampai LLM panggil task_done() atau max_iters habis
"""
import json
import config
import tools
from providers import get_provider

SYSTEM_PROMPT = """Kamu adalah SOVEREIGN Agent, asisten sekaligus autonomous coding/ops agent yang jalan di HP Android (Termux).
Kamu bisa dua hal:
1. Ngobrol/diskusi biasa (brainstorming, jelasin konsep, nanya balik, ngasih pendapat) — kalau ini yang diminta, JANGAN paksa manggil tool, cukup jawab teks biasa.
2. Eksekusi task nyata pakai tool: bash_exec, install_package, read_file, write_file, list_dir, task_done — kalau user minta sesuatu dibuatkan/dijalankan/diperbaiki.

Kerja di dalam folder workspace. Kalau butuh library, install sendiri pakai install_package.
Kalau ada error, baca error-nya, perbaiki, coba lagi — jangan menyerah di percobaan pertama.
Kalau lagi ngerjain task dan sudah selesai + sudah dites/berfungsi, panggil tool task_done dengan ringkasan hasil.
Kalau user cuma ngobrol/nanya (bukan minta dibuatkan sesuatu), jangan panggil task_done, cukup jawab biasa.
Jawab dalam Bahasa Indonesia santai, to the point."""


class Agent:
    def __init__(self, provider_name=None, mode="confirm", notify=print, ask_confirm=None):
        self.provider = get_provider(provider_name)
        self.mode = mode
        self.notify = notify
        self.ask_confirm = ask_confirm or (lambda name, args: True)
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def reset(self):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def set_provider(self, provider_name):
        self.provider = get_provider(provider_name)
        self.provider_name = provider_name

    def set_mode(self, mode):
        if mode not in ("auto", "confirm"):
            raise ValueError("mode harus 'auto' atau 'confirm'")
        self.mode = mode

    def _step(self, max_iters):
        for _ in range(max_iters):
            try:
                resp = self.provider.chat(self.messages, tools.TOOLS_SCHEMA)
            except Exception as e:
                self.notify(f"[error] gagal manggil provider: {e}")
                return

            if resp["content"]:
                self.notify(resp["content"])

            if not resp["tool_calls"]:
                self.messages.append({"role": "assistant", "content": resp["content"]})
                return

            assistant_msg = {
                "role": "assistant",
                "content": resp["content"],
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                    }
                    for tc in resp["tool_calls"]
                ],
            }
            self.messages.append(assistant_msg)

            for tc in resp["tool_calls"]:
                name, args, call_id = tc["name"], tc["arguments"], tc["id"]

                if name == "task_done":
                    self.notify(f"✅ SELESAI: {args.get('summary', '(tanpa ringkasan)')}")
                    self.messages.append({"role": "tool", "tool_call_id": call_id, "content": "ok"})
                    return

                if name not in tools.DISPATCH:
                    result = f"[error] tool '{name}' tidak dikenal"
                else:
                    if self.mode == "confirm" and name in tools.RISKY_TOOLS:
                        allowed = self.ask_confirm(name, args)
                        result = "[ditolak user] eksekusi dibatalkan" if not allowed else tools.DISPATCH[name](args)
                    else:
                        result = tools.DISPATCH[name](args)

                    self.notify(f"🔧 {name}({args}) ->\n{result[:800]}")

                self.messages.append({"role": "tool", "tool_call_id": call_id, "content": str(result)})

        self.notify("[berhenti] max_iters tercapai, mungkin belum selesai total.")

    def chat(self, user_input: str, max_iters: int = None):
        max_iters = max_iters or config.MAX_ITERS
        self.messages.append({"role": "user", "content": user_input})
        self._step(max_iters)

    def run(self, task: str, max_iters: int = None):
        self.reset()
        self.chat(task, max_iters=max_iters)
