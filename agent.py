"""
Core agentic loop — SOVEREIGN Agent v2.5
  1. Kirim task + history ke LLM (dengan daftar tools)
  2. LLM balas: teks status dan/atau tool_calls
  3. Kalau ada tool_call risky & mode='confirm' -> tanya user dulu
  4. Eksekusi tool, hasil dimasukkan lagi ke history
  5. Ulangi sampai LLM panggil task_done() atau max_iters habis

FEATURES v2.5:
  - Smart History Compression (auto-summarize pesan lama)
  - Long-Term Memory (simpan fakta user ke file)
  - Error Learning (log error & antisipasi di next turn)
  - Cost Tracker (estimasi biaya per request)
  - Enhanced System Prompt (RAG-first, chain of thought)
"""
import os
import time
import json
import config
import tools
import health
from providers import get_provider

# ═══════════════════════════════════════════════════════
# MEMORY PATHS
# ═══════════════════════════════════════════════════════
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
USER_PROFILE_PATH = os.path.join(MEMORY_DIR, "user-profile.md")
os.makedirs(MEMORY_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════
# COST TABLE (USD per 1K tokens, approx)
# ═══════════════════════════════════════════════════════
COST_TABLE = {
    "llama-3.3-70b-versatile": {"input": 0.00059, "output": 0.00079},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.0015},
    "mimo": {"input": 0.0002, "output": 0.0006},
    "mimo-v2.5": {"input": 0.0002, "output": 0.0006},
}

# ═══════════════════════════════════════════════════════
# SYSTEM PROMPT v2.5 — Optimized
# ═══════════════════════════════════════════════════════
SYSTEM_PROMPT = """Kamu adalah SOVEREIGN Agent v2.5, asisten sekaligus autonomous coding/ops agent yang jalan di HP Android (Termux).

KAPABILITAS:
1. **Obrolan biasa** — brainstorming, jelasin konsep, ngasih pendapat. JANGAN paksa manggil tool.
2. **Eksekusi task** — pakai tools: bash_exec, install_package, read_file, write_file, patch_file, list_dir, fetch_url, web_search, search_knowledge, index_file, rebuild_index, rag_stats, health_check, task_done.

CARA KERJA:
- Kerja di dalam folder workspace.
- Kalau butuh library, install sendiri pakai install_package.
- Kalau ada error: baca error-nya, pahami, perbaiki, coba lagi. JANGAN menyerah di percobaan pertama.
- Kalau user cuma ngobrol, jangan panggil task_done.

⚠️ MANDATORY: TEST-BEFORE-DONE
Sebelum panggil task_done, WAJIB jalankan verifikasi:
- File Python: `python -m py_compile <file>` atau `python -c "import <module>"`
- File JS/TS: `node -c <file>`
- Shell script: `bash -n <file>`
- API/server: `curl localhost:<port>/health` atau run script-nya
- Script apapun: coba run dulu, pastikan gak error
Kalau verifikasi GAGAL → perbaiki dulu, jangan panggil task_done.
Hanya panggil task_done kalau verifikasi LULUS atau task memang cuma diskusi/tulisan.

STRATEGI RESEARCH (untuk pertanyaan/riset):
- **Step 1**: search_knowledge() — cek knowledge base RAG dulu
- **Step 2**: Kalau kurang, pakai read_file() atau fetch_url() 
- **Step 3**: Kalau masih kurang, pakai web_search() untuk info terkini
- **Step 4**: Kalau menemukan info baru, index_file() biar ke-save

SKILL LIBRARY:
- Kalau dapat task, cek dulu ada skill yang cocok: skill_search("keyword") atau skill_list()
- Kalau ada skill yang cocok: skill_load("nama skill") → ikuti langkah-langkahnya
- Kalau selesai task dan hasilnya bagus + bisa dipakai lagi: skill_save() buat next time
- Ini bikin kerja lebih cepat & konsisten, gak mikir dari nol tiap kali

CHAIN OF THOUGHT: Sebelum eksekusi, pahami → cek skill → rencanakan → eksekusi → verifikasi.
Jawab dalam Bahasa Indonesia santai, to the point."""

# ═══════════════════════════════════════════════════════
# TOOL LABELS (tampilan ramah ke user)
# ═══════════════════════════════════════════════════════
TOOL_LABELS = {
    "bash_exec": "🔧 Menjalankan perintah",
    "install_package": "📦 Menginstall package",
    "write_file": "📝 Menulis file",
    "read_file": "📖 Membaca file",
    "patch_file": "🩹 Edit sebagian file",
    "list_dir": "📂 Melihat isi folder",
    "fetch_url": "🌐 Mengambil data dari web",
    "web_search": "🔍 Mencari di internet",
    "search_knowledge": "🧠 Cari knowledge base",
    "index_file": "📚 Index file ke RAG",
    "rebuild_index": "🔄 Rebuild index RAG",
    "rag_stats": "📊 Stats RAG",
}


def _tool_label(name, args):
    base = TOOL_LABELS.get(name, name)
    if name in ("write_file", "read_file", "patch_file", "index_file"):
        p = args.get("path", "")
        return f"{base}: {p}" if p else base
    if name == "install_package":
        pkg = args.get("package", "")
        return f"{base}: {pkg}" if pkg else base
    if name == "fetch_url":
        url = args.get("url", "")
        short = url[:60] + "..." if len(url) > 60 else url
        return f"{base}: {short}" if url else base
    if name == "web_search":
        q = args.get("query", "")
        return f"{base}: {q}" if q else base
    if name == "search_knowledge":
        q = args.get("query", "")
        return f"{base}: {q}" if q else base
    return base


# ═══════════════════════════════════════════════════════
# LONG-TERM MEMORY
# ═══════════════════════════════════════════════════════
def _load_user_profile():
    """Load long-term memory dari file."""
    if not os.path.exists(USER_PROFILE_PATH):
        return ""
    try:
        with open(USER_PROFILE_PATH, "r") as f:
            return f.read().strip()
    except Exception:
        return ""


def _save_user_profile(content):
    """Simpan long-term memory ke file."""
    try:
        with open(USER_PROFILE_PATH, "w") as f:
            f.write(content)
    except Exception as e:
        print(f"⚠️ gagal simpan user profile: {e}")


def _append_user_profile(fact):
    """Tambah 1 fakta baru ke user profile."""
    existing = _load_user_profile()
    if fact in existing:
        return  # sudah ada, jangan duplikat
    if existing:
        updated = existing + "\n- " + fact
    else:
        updated = "# User Profile\n\nFakta tentang user:\n- " + fact
    _save_user_profile(updated)


# ═══════════════════════════════════════════════════════
# ERROR MEMORY (via error_memory.py)
# ═══════════════════════════════════════════════════════
def _get_error_memory():
    """Lazy import error memory."""
    try:
        import error_memory
        return error_memory.get_error_memory()
    except Exception:
        return None


def _log_error_smart(error_msg, context="", solution_tried="", success=False):
    """Log error ke structured memory + ambil saran."""
    mem = _get_error_memory()
    if mem:
        mem.remember(error_msg, context, solution_tried, success)
        return mem.get_suggestion(error_msg)
    return None


def _check_action_warning(action_desc):
    """Cek apakah action ini punya risiko error berdasarkan memory."""
    mem = _get_error_memory()
    if mem:
        return mem.check_before_action(action_desc)
    return None


# ═══════════════════════════════════════════════════════
# ERROR LEARNING — via error_memory.py
# ═══════════════════════════════════════════════════════
# (sudah ada di _get_error_memory, _log_error_smart, _check_action_warning)


# ═══════════════════════════════════════════════════════
# COST TRACKER
# ═══════════════════════════════════════════════════════
def _estimate_cost(usage, model="llama-3.3-70b-versatile"):
    """Estimasi biaya dalam USD."""
    costs = COST_TABLE.get(model, COST_TABLE["llama-3.3-70b-versatile"])
    input_cost = (usage.get("input", 0) / 1000) * costs["input"]
    output_cost = (usage.get("output", 0) / 1000) * costs["output"]
    return input_cost + output_cost


# ═══════════════════════════════════════════════════════
# AGENT CLASS
# ═══════════════════════════════════════════════════════
class Agent:
    def __init__(self, provider_name=None, mode="confirm", notify=print, ask_confirm=None,
                 session_name=None, auto_trim_ratio=0.65):
        self.provider_name = provider_name or config.DEFAULT_PROVIDER
        self.provider = get_provider(provider_name)
        self.mode = mode
        self.notify = notify
        self.ask_confirm = ask_confirm or (lambda name, args: True)
        self.session_name = session_name
        self.auto_trim_ratio = auto_trim_ratio
        self.stop_requested = False
        self.messages = []
        self.session_tokens = 0
        self.total_cost = 0.0
        self.last_usage = {"input": 0, "output": 0, "total": 0}
        self.last_elapsed = 0.0

        # Init system prompt + long-term memory
        self._init_system_prompt()

        # Startup health check — silent auto-fix
        try:
            import health as _h
            _h.full_health_check(auto_fix=True)
        except Exception:
            pass  # Don't crash agent if health check fails

        if session_name:
            self.load_session(session_name)

    def _init_system_prompt(self):
        """Build system prompt dengan long-term memory & error context."""
        parts = [SYSTEM_PROMPT]

        # Tambah long-term memory
        profile = _load_user_profile()
        if profile:
            parts.append(f"\n\nLONG-TERM MEMORY:\n{profile}")

        # Tambah error memory warnings (biar agent aware error yang sering terjadi)
        mem = _get_error_memory()
        if mem:
            warnings = mem.get_context_warnings()
            if warnings:
                parts.append(
                    "\n\n⚠️ ERROR MEMORY — hindari error berikut:\n" 
                    + "\n".join(warnings)
                )

        self.messages = [{"role": "system", "content": "\n".join(parts)}]

    def reset(self):
        """Mulai obrolan/task baru, buang history lama tapi tetep pake memory."""
        self._init_system_prompt()
        self.session_tokens = 0
        self.total_cost = 0.0

    def request_stop(self):
        """User minta stop."""
        self.stop_requested = True
        self.notify("🛑 Stop requested...")

    def set_provider(self, provider_name):
        self.provider = get_provider(provider_name)
        self.provider_name = provider_name

    def set_mode(self, mode):
        if mode not in ("auto", "confirm"):
            raise ValueError("mode harus 'auto' atau 'confirm'")
        self.mode = mode

    # ─────────────────────────────────────
    # TOKEN & COST ESTIMATION
    # ─────────────────────────────────────
    def _estimate_tokens(self, messages):
        total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        return total_chars // 4

    def _notify_stats(self):
        """Notifikasi ringkas: token usage + estimated cost."""
        cost = _estimate_cost(self.last_usage, self.provider.model)
        self.total_cost += cost
        inp = self.last_usage.get("input", 0)
        out = self.last_usage.get("output", 0)
        elapsed = self.last_elapsed
        self.notify(
            f"📊 {inp}+{out} tokens | ~${cost:.5f} | {elapsed:.1f}s | "
            f"total: ${self.total_cost:.5f}"
        )

    def self_health(self):
        """Jalankan health check & auto-fix. Returns report string."""
        result = health.full_health_check(auto_fix=True)
        report = health.format_report(result)
        self.notify(report)
        return report

    # ─────────────────────────────────────
    # SMART HISTORY COMPRESSION
    # ─────────────────────────────────────
    def _compress_history(self, keep_recent=10):
        """Compress pesan lama jadi ringkasan singkat."""
        system = self.messages[0]
        rest = self.messages[1:]

        if len(rest) <= keep_recent + 4:
            return  # belum perlu compress

        to_compress = rest[:-keep_recent]
        keep = rest[-keep_recent:]

        # Buat ringkasan dari pesan yang mau di-compress
        summary_parts = []
        for msg in to_compress:
            role = msg.get("role", "")
            if role == "user":
                content = msg.get("content", "")[:100]
                summary_parts.append(f"User: {content}")
            elif role == "assistant" and not msg.get("tool_calls"):
                content = msg.get("content", "")[:150]
                if content:
                    summary_parts.append(f"AI: {content}")
            elif role == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    name = tc.get("function", {}).get("name", "")
                    summary_parts.append(f"[tool: {name}]")

        if not summary_parts:
            self.messages = [system] + keep
            return

        summary = "[HISTORI RINGKASAN]\n" + "\n".join(summary_parts[-15:])
        compressed = [
            system,
            {"role": "user", "content": f"[Sistem: Berikut ringkasan percakapan sebelumnya]\n{summary}"},
            {"role": "assistant", "content": "Oke, gue udah tangkap konteksnya. Lanjut!"},
        ]

        self.messages = compressed + keep
        self.notify("🗜️ history dikompress (pesan lama di-ringkasan)")

    def _trim_history(self):
        """Trim history kalau udah kelebihan context window."""
        limit = int(self.provider.context_window * self.auto_trim_ratio)
        tokens = self._estimate_tokens(self.messages)

        if tokens <= limit:
            return

        # Coba compress dulu
        self._compress_history(keep_recent=8)
        tokens = self._estimate_tokens(self.messages)

        if tokens <= limit:
            return

        # Kalau masih kelebihan, pangkas dari yang paling lama
        system = self.messages[0]
        rest = self.messages[1:]
        while rest and self._estimate_tokens([system] + rest) > limit:
            msg = rest.pop(0)
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                n_calls = len(msg["tool_calls"])
                for _ in range(n_calls):
                    if rest and rest[0].get("role") == "tool":
                        rest.pop(0)

        self.messages = [system] + rest
        self.notify("✂️ history dipangkas (terlalu besar untuk context window)")

    # ─────────────────────────────────────
    # TEST-BEFORE-DONE VERIFICATION
    # ─────────────────────────────────────
    _VERIFY_KEYWORDS = [
        "py_compile", "py.test", "pytest", "unittest",
        "node -c", "node --check",
        "bash -n",
        "curl", "wget",
        "python -c", "python3 -c",
        "import ",
        "test_", "_test.",
        "lint", "check", "verify",
        "mypy", "ruff", "flake8", "black",
    ]

    _DISCUSS_KEYWORDS = [
        "ngobrol", "diskusi", "jelasin", "penjelasan", "opini",
        "brainstorm", "saran", "rekomendasi", "ringkasan",
        "tanya jawab", "curhat", "diskusi",
    ]

    def _has_verification(self):
        """Cek apakah ada verifikasi/test di recent tool calls."""
        recent = self.messages[-15:]
        for msg in recent:
            if msg.get("role") != "assistant":
                continue
            if not msg.get("tool_calls"):
                continue
            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                name = func.get("name", "")
                args_str = func.get("arguments", "{}")
                if isinstance(args_str, str):
                    try:
                        args = json.loads(args_str)
                    except Exception:
                        continue
                else:
                    args = args_str

                if name == "bash_exec":
                    cmd = args.get("command", "").lower()
                    for kw in self._VERIFY_KEYWORDS:
                        if kw in cmd:
                            return True
                if name == "read_file":
                    return True
        return False

    def _check_task_done(self, args):
        """Cek apakah task_done boleh dipanggil. Return (allowed, reason)."""
        summary = args.get("summary", "").lower()
        for kw in self._DISCUSS_KEYWORDS:
            if kw in summary:
                return True, "discuss_only"
        if self._has_verification():
            return True, "verified"
        return False, "no_verification"

    # ─────────────────────────────────────
    # SESSION SAVE/LOAD
    # ─────────────────────────────────────
    def save_session(self, name=None):
        name = name or self.session_name
        if not name:
            return
        path = os.path.join(config.SESSIONS_DIR, f"{name}.json")
        try:
            # Simpan history aja, system prompt akan di-rebuild saat load
            save_data = [m for m in self.messages if m.get("role") != "system"]
            with open(path, "w") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.notify(f"⚠️ gagal simpan session: {e}")

    def load_session(self, name):
        path = os.path.join(config.SESSIONS_DIR, f"{name}.json")
        if not os.path.exists(path):
            self.session_name = name
            return
        try:
            with open(path, "r") as f:
                saved_messages = json.load(f)
            # Rebuild system prompt + append history lama
            self._init_system_prompt()
            self.messages.extend(saved_messages)
            self.session_name = name
            self.notify(f"📂 session '{name}' dimuat ({len(saved_messages)} pesan).")
        except Exception as e:
            self.notify(f"⚠️ gagal load session: {e}")

    # ─────────────────────────────────────
    # AGENTIC LOOP
    # ─────────────────────────────────────
    def _step(self, max_iters):
        """Loop internal: proses messages sampai AI berhenti atau task_done."""
        for iteration in range(max_iters):
            if self.stop_requested:
                self.notify("🛑 Dihentikan oleh user.")
                self.stop_requested = False
                return

            self._trim_history()
            try:
                start = time.time()
                resp = self.provider.chat(self.messages, tools.TOOLS_SCHEMA)
                self.last_elapsed = time.time() - start
            except Exception as e:
                self.notify(f"❌ Error manggil provider: {e}")
                _log_error_smart(str(e), f"provider:{self.provider_name}")
                return

            usage = resp.get("usage") or {}
            self.last_usage = usage
            self.session_tokens += usage.get("total", 0)

            if resp["content"]:
                self.notify(resp["content"])

            # Tampilkan stats
            self._notify_stats()

            if not resp["tool_calls"]:
                self.messages.append({"role": "assistant", "content": resp["content"]})
                return

            # Build assistant message dengan tool_calls
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

            done = False
            for tc in resp["tool_calls"]:
                if self.stop_requested:
                    self.notify("🛑 Dihentikan oleh user.")
                    done = True
                    break

                name, args, call_id = tc["name"], tc["arguments"], tc["id"]

                if name == "task_done":
                    # ⚠️ TEST-BEFORE-DONE ENFORCEMENT
                    allowed, reason = self._check_task_done(args)
                    if not allowed:
                        summary = args.get("summary", "(tanpa ringkasan)")
                        self.notify(
                            f"⚠️ task_done DITOLAK — belum ada verifikasi!\n"
                            f"   Ringkasan: {summary}\n"
                            f"   → Jalankan test/verifikasi dulu, lalu panggil task_done lagi."
                        )
                        # Inject feedback ke history biar AI tau kenapa ditolak
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": (
                                "[DENIED] task_done ditolak karena belum ada verifikasi. "
                                "Sebelum klaim selesai, WAJIB jalankan verifikasi dulu: "
                                "- File Python: python -m py_compile <file> atau python -c 'import ...'\n"
                                "- File JS: node -c <file>\n"
                                "- Shell: bash -n <file>\n"
                                "- API/Server: curl localhost:<port>/health\n"
                                "- Atau minimal baca file hasilnya (read_file) buat mastiin isinya bener.\n"
                                "Setelah verifikasi LULUS, baru panggil task_done lagi."
                            ),
                        })
                        continue  # Jangan set done=True, lanjut loop

                    summary = args.get("summary", "(tanpa ringkasan)")
                    verify_icon = "✅" if reason == "verified" else "💬"
                    self.notify(f"{verify_icon} SELESAI: {summary}")
                    self.messages.append({"role": "tool", "tool_call_id": call_id, "content": "ok"})
                    done = True
                    continue

                # Handle memory commands
                if name == "bash_exec":
                    cmd = args.get("command", "")
                    if cmd.strip() == "/stop":
                        self.request_stop()
                        done = True
                        break

                label = _tool_label(name, args)

                if name not in tools.DISPATCH:
                    result = f"[error] tool '{name}' tidak dikenal"
                    self.notify(f"⚠️ {label} gagal (tool tidak dikenal)")
                else:
                    self.notify(f"⏳ {label}...")
                    try:
                        if self.mode == "confirm" and name in tools.RISKY_TOOLS:
                            allowed = self.ask_confirm(name, args)
                            if not allowed:
                                result = "[ditolak user] eksekusi dibatalkan"
                                self.notify(f"🚫 {label} dibatalkan")
                            else:
                                result = tools.DISPATCH[name](args)
                        else:
                            result = tools.DISPATCH[name](args)
                    except Exception as e:
                        result = f"[error] {e}"
                        self.notify(f"⚠️ {label} error: {e}")
                        suggestion = _log_error_smart(str(e), name)
                        if suggestion:
                            self.notify(suggestion)

                # Log error kalau result error
                result_str = str(result)
                if result_str.startswith("[error]"):
                    suggestion = _log_error_smart(result_str, name)
                    if suggestion:
                        self.notify(suggestion)

                self.messages.append({"role": "tool", "tool_call_id": call_id, "content": result_str})

            if done:
                return

        self.notify("⏰ max_iters tercapai, mungkin belum selesai total.")

    # ─────────────────────────────────────
    # SKILL AUTO-INJECT
    # ─────────────────────────────────────
    def _check_relevant_skills(self, task_description):
        """Cek apakah ada skill yang relevan, return context string atau None."""
        try:
            import skills
            lib = skills.get_skill_library()
            return lib.get_relevant_skills(task_description)
        except Exception:
            return None

    def chat(self, user_input: str, max_iters: int = None):
        """Mode diskusi: history persisten, dipanggil berkali-kali."""
        if self.stop_requested:
            self.stop_requested = False

        max_iters = max_iters or config.MAX_ITERS

        # Auto-inject relevant skills
        skill_context = self._check_relevant_skills(user_input)
        if skill_context:
            self.messages.append({"role": "user", "content": user_input})
            # Tambah skill context setelah user message
            self.messages.append({
                "role": "system",
                "content": f"[SISTEM] {skill_context}"
            })
        else:
            self.messages.append({"role": "user", "content": user_input})

        self._step(max_iters)
        self.save_session()

    def run(self, task: str, max_iters: int = None):
        """Mode one-shot: reset dulu baru jalanin satu task."""
        self.reset()
        self.chat(task, max_iters=max_iters)
