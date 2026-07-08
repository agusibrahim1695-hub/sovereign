"""
Tool definitions v2.5 — SOVEREIGN Agent
Semua tool jalan dengan cwd = WORKSPACE_DIR (sandbox).

CATATAN PENTING:
- read_file, write_file, patch_file, list_dir DISANDBOX ke WORKSPACE_DIR
- bash_exec TIDAK disandbox — full access (buat self-upgrade)
- search_knowledge, index_file, rebuild_index = RAG system
- CRITICAL FILES: write/patch wajib verifikasi syntax dulu
"""
import subprocess
import os
import json
import ast
import requests
import config

# ═══════════════════════════════════════════════
# CRITICAL FILES — wajib verifikasi sebelum write
# ═══════════════════════════════════════════════
# File-file yang kalau rusak, agent bisa mati total
CRITICAL_FILES = {
    "agent.py", "tools.py", "providers.py", "config.py", 
    "main.py", "rag_core.py", "skills.py", "error_memory.py",
}

# Folder yang isinya code (bukan data)
SOURCE_DIRS = {"sovereign", "workspace/sovereign", "."}


def _is_critical_file(path):
    """Cek apakah file ini termasuk critical (wajib verifikasi)."""
    basename = os.path.basename(path)
    if basename in CRITICAL_FILES:
        return True
    # Cek apakah path-nya di source code directory
    if path.endswith(".py") and any(d in path for d in SOURCE_DIRS):
        return True
    return False


def _verify_python_syntax(content, path=""):
    """Verifikasi syntax Python sebelum write. Return (ok, error_msg)."""
    try:
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError di {path or '(unknown)'}: baris {e.lineno}, {e.msg}"


def _verify_before_write(path, content):
    """
    Verifikasi konten sebelum write ke file penting.
    Return (allowed, error_msg). allowed=True kalau aman.
    """
    # Hanya verifikasi Python files
    if not path.endswith(".py"):
        return True, None
    
    # Hanya verifikasi critical files
    if not _is_critical_file(path):
        return True, None
    
    # Cek syntax
    ok, err = _verify_python_syntax(content, path)
    if not ok:
        return False, (
            f"🛑 WRITE DITOLAK — syntax error terdeteksi!\n"
            f"   File: {path}\n"
            f"   Error: {err}\n"
            f"   → Perbaiki syntax dulu baru boleh write."
        )
    
    return True, None


def _verify_before_patch(path, new_content):
    """
    Verifikasi hasil patch (read file dulu, replace, lalu cek syntax).
    Return (allowed, error_msg).
    """
    if not path.endswith(".py"):
        return True, None
    
    if not _is_critical_file(path):
        return True, None
    
    # Baca file lama, apply patch, cek syntax hasilnya
    try:
        full = _safe_path(path)
        if os.path.exists(full):
            with open(full, "r") as f:
                old_content = f.read()
            # Simulasi: ganti old_str dengan new_str
            # (patch belum terjadi, jadi kita cek konten baru)
            ok, err = _verify_python_syntax(new_content, path)
            if not ok:
                return False, (
                    f"🛑 PATCH DITOLAK — syntax error terdeteksi!\n"
                    f"   File: {path}\n"
                    f"   Error: {err}\n"
                    f"   → Perbaiki syntax dulu baru boleh patch."
                )
    except Exception:
        pass  # Kalau gagal baca, allow (biar error asli yang muncul)
    
    return True, None

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "bash_exec",
            "description": "Jalankan perintah shell di Termux/Linux (cwd = workspace).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Perintah shell yang mau dijalankan"},
                    "timeout": {"type": "integer", "description": "Timeout detik, default 120, max 600"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "install_package",
            "description": "Install package via pip/npm/apt(pkg).",
            "parameters": {
                "type": "object",
                "properties": {
                    "manager": {"type": "string", "enum": ["pip", "npm", "pkg"]},
                    "package": {"type": "string"},
                },
                "required": ["manager", "package"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Tulis/overwrite SELURUH isi file. Pakai ini untuk file baru. Untuk edit sebagian file yang sudah ada, pakai patch_file (lebih cepat & hemat).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relatif ke workspace"},
                    "content": {"type": "string", "description": "Seluruh isi file"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Ganti sebagian teks di file yang sudah ada (find & replace persis satu kali). Jauh lebih cepat daripada write_file untuk file besar. old_str harus unik & persis sama termasuk spasi/indentasi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path file yang mau di-edit"},
                    "old_str": {"type": "string", "description": "Teks lama yang mau diganti, harus persis & unik di file"},
                    "new_str": {"type": "string", "description": "Teks baru pengganti"},
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Baca isi file. Untuk file besar, pakai start_line+num_lines biar gak perlu baca ulang dari awal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "description": "Baris awal (1-indexed), opsional"},
                    "num_lines": {"type": "integer", "description": "Jumlah baris dibaca dari start_line, default 200"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List isi folder di dalam workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Ambil isi halaman web (scraping) dan ekstrak teksnya.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL lengkap termasuk https://"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Cari informasi terkini di internet via Google Search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Kata kunci pencarian"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search knowledge base (RAG) - cari informasi dari file yang sudah di-index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query yang mau dicari"},
                    "top_n": {"type": "integer", "description": "Jumlah hasil, default 5"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "index_file",
            "description": "Index 1 file ke knowledge base RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path file"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rebuild_index",
            "description": "Rebuild seluruh knowledge base dari awal.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_stats",
            "description": "Statistik knowledge base RAG.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_save",
            "description": "Simpan skill/template baru ke Skill Library. Pakai ini kalau baru selesai ngerjain task yang bisa dipakai lagi nanti.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nama skill (singkat, jelas)"},
                    "description": {"type": "string", "description": "Deskripsi singkat"},
                    "keywords": {"type": "array", "items": {"type": "string"}, "description": "Kata kunci buat recall"},
                    "steps": {"type": "array", "items": {"type": "string"}, "description": "Langkah-langkah"},
                    "code_template": {"type": "string", "description": "Code template (opsional)"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags (opsional)"},
                },
                "required": ["name", "description", "keywords", "steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_load",
            "description": "Load skill dari library buat dipakai sebagai panduan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nama atau ID skill"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_search",
            "description": "Cari skill di library berdasarkan keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query pencarian"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_list",
            "description": "List semua skill di library.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_done",
            "description": "Panggil ini SEKALI saat task sudah selesai sepenuhnya.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Ringkasan apa yang sudah dikerjakan & hasil akhirnya"},
                },
                "required": ["summary"],
            },
        },
    },
]

RISKY_TOOLS = {"bash_exec", "install_package", "write_file"}
READ_FILE_LIMIT = 8000


def _safe_path(rel_path: str) -> str:
    base = os.path.abspath(config.WORKSPACE_DIR)
    full = os.path.abspath(os.path.join(base, rel_path))
    if not (full == base or full.startswith(base + os.sep)):
        raise ValueError("Path di luar workspace, ditolak demi keamanan.")
    return full


# ═══════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════

def bash_exec(command: str, timeout: int = None) -> str:
    timeout = timeout or config.BASH_TIMEOUT
    timeout = min(timeout, 600)
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=config.WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = result.stdout[-4000:]
        err = result.stderr[-2000:]
        return f"[exit={result.returncode}]\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    except subprocess.TimeoutExpired:
        return f"[error] command timeout ({timeout}s)"
    except Exception as e:
        return f"[error] {e}"


def install_package(manager: str, package: str) -> str:
    cmds = {
        "pip": f"pip install --break-system-packages {package}",
        "npm": f"npm install -g {package}",
        "pkg": f"pkg install -y {package}",
    }
    cmd = cmds.get(manager)
    if not cmd:
        return f"[error] manager '{manager}' tidak dikenal"
    return bash_exec(cmd)


def write_file(path: str, content: str) -> str:
    # 🔒 AUTO-VERIFY: cek syntax sebelum write ke file penting
    allowed, err = _verify_before_write(path, content)
    if not allowed:
        return f"[error] {err}"
    
    try:
        full = _safe_path(path)
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return f"[ok] file ditulis: {path} ({len(content)} bytes)"
    except Exception as e:
        return f"[error] {e}"


def patch_file(path: str, old_str: str, new_str: str) -> str:
    """Find & replace persis satu kali. Lebih cepat dari write_file untuk file besar."""
    try:
        full = _safe_path(path)
        if not os.path.exists(full):
            return f"[error] file tidak ditemukan: {path}"
        with open(full, "r") as f:
            content = f.read()
        count = content.count(old_str)
        if count == 0:
            return f"[error] teks lama tidak ditemukan di {path}. Pastikan spasi/indentasi persis sama."
        if count > 1:
            return f"[error] teks lama ditemukan {count} kali di {path}. Buat lebih unik supaya cuma 1 match."
        new_content = content.replace(old_str, new_str, 1)
        
        # 🔒 AUTO-VERIFY: cek syntax patch result ke file penting
        allowed, err = _verify_before_patch(path, new_content)
        if not allowed:
            return f"[error] {err}"
        
        with open(full, "w") as f:
            f.write(new_content)
        return f"[ok] file dipatch: {path}"
    except Exception as e:
        return f"[error] {e}"


def read_file(path: str, start_line: int = None, num_lines: int = 200) -> str:
    try:
        full = _safe_path(path)
        if not os.path.exists(full):
            return f"[error] file tidak ditemukan: {path}"
        with open(full, "r") as f:
            all_lines = f.readlines()
        total = len(all_lines)
        if start_line is not None:
            start = max(0, start_line - 1)  # convert to 0-indexed
            end = start + num_lines
            selected = all_lines[start:end]
            header = f"[baris {start+1}-{min(end, total)} dari {total} total baris]\n"
        else:
            # Auto-truncate kalau file terlalu besar
            if total > 200:
                selected = all_lines[:200]
                header = f"[200/{total} baris pertama]\n"
            else:
                selected = all_lines
                header = ""
        content = "".join(selected)
        if len(content) > READ_FILE_LIMIT:
            content = content[:READ_FILE_LIMIT] + f"\n[...dipotong, max {READ_FILE_LIMIT} karakter]"
        return header + content
    except Exception as e:
        return f"[error] {e}"


def list_dir(path: str = ".") -> str:
    try:
        base = os.path.abspath(config.WORKSPACE_DIR)
        target = os.path.abspath(os.path.join(base, path))
        if not (target == base or target.startswith(base + os.sep)):
            return "[error] path di luar workspace"
        entries = sorted(os.listdir(target))
        lines = []
        for e in entries:
            full_path = os.path.join(target, e)
            if os.path.isdir(full_path):
                lines.append(f"📁 {e}/")
            else:
                size = os.path.getsize(full_path)
                if size > 1_000_000:
                    size_str = f"{size / 1_000_000:.1f}MB"
                elif size > 1_000:
                    size_str = f"{size / 1_000:.1f}KB"
                else:
                    size_str = f"{size}B"
                lines.append(f"📄 {e} ({size_str})")
        if not lines:
            return "(folder kosong)"
        return "\n".join(lines)
    except Exception as e:
        return f"[error] {e}"


def fetch_url(url: str) -> str:
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (SOVEREIGN Agent)"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ", strip=True).split())
        return text[:6000]
    except ImportError:
        return "[error] library 'beautifulsoup4' belum terpasang. Jalanin: pip install beautifulsoup4 --break-system-packages"
    except Exception as e:
        return f"[error] gagal fetch url: {e}"


def web_search(query: str) -> str:
    if not config.SERPER_API_KEY:
        return "[error] SERPER_API_KEY belum diisi di .env"
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": config.SERPER_API_KEY,
                "Content-Type": "application/json",
            },
            json={"q": query},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        lines = []
        answer_box = data.get("answerBox")
        if answer_box:
            snippet = answer_box.get("answer") or answer_box.get("snippet")
            if snippet:
                lines.append(f"[Jawaban langsung] {snippet}")
        for item in data.get("organic", [])[:6]:
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            lines.append(f"- {title}\n  {snippet}\n  {link}")
        if not lines:
            return "[info] tidak ada hasil ditemukan"
        return "\n".join(lines)
    except Exception as e:
        return f"[error] gagal web_search: {e}"


# ═══════════════════════════════════════════════
# RAG TOOLS (disediakan dari rag_core.py)
# ═══════════════════════════════════════════════

def _get_rag():
    """Lazy import RAG system."""
    try:
        import rag_core
        return rag_core.get_rag()
    except Exception:
        return None


def search_knowledge(query: str, top_n: int = 5) -> str:
    rag = _get_rag()
    if not rag:
        return "[info] RAG system belum tersedia"
    try:
        results = rag.search(query, top_n=top_n)
        if not results:
            return "[info] tidak ditemukan di knowledge base"
        lines = []
        for r in results:
            score = r.get("score", 0)
            text = r.get("text", "")[:300]
            source = r.get("source", "unknown")
            lines.append(f"[{score:.2f}] ({source})\n{text}\n")
        return "\n---\n".join(lines)
    except Exception as e:
        return f"[error] search_knowledge: {e}"


def index_file(path: str) -> str:
    rag = _get_rag()
    if not rag:
        return "[info] RAG system belum tersedia"
    try:
        full = _safe_path(path)
        result = rag.index_file(full)
        return result
    except Exception as e:
        return f"[error] index_file: {e}"


def rebuild_index() -> str:
    rag = _get_rag()
    if not rag:
        return "[info] RAG system belum tersedia"
    try:
        return rag.rebuild_index()
    except Exception as e:
        return f"[error] rebuild_index: {e}"


def rag_stats() -> str:
    rag = _get_rag()
    if not rag:
        return "[info] RAG system belum tersedia"
    try:
        return rag.stats()
    except Exception as e:
        return f"[error] rag_stats: {e}"


def task_done(summary: str) -> str:
    return f"[task_done] {summary}"


# ═══════════════════════════════════════════════
# DISPATCH TABLE
# ═══════════════════════════════════════════════

def _dispatch_bash(args): return bash_exec(args["command"], args.get("timeout"))
def _dispatch_install(args): return install_package(args["manager"], args["package"])
def _dispatch_write(args): return write_file(args["path"], args["content"])
def _dispatch_patch(args): return patch_file(args["path"], args["old_str"], args["new_str"])
def _dispatch_read(args): return read_file(args["path"], args.get("start_line"), args.get("num_lines", 200))
def _dispatch_list(args): return list_dir(args.get("path", "."))
def _dispatch_fetch(args): return fetch_url(args["url"])
def _dispatch_search(args): return web_search(args["query"])
def _dispatch_rag_search(args): return search_knowledge(args["query"], args.get("top_n", 5))
def _dispatch_rag_index(args): return index_file(args["path"])
def _dispatch_rag_rebuild(args): return rebuild_index()
def _dispatch_rag_stats(args): return rag_stats()


# ═══════════════════════════════════════════════
# SKILL LIBRARY TOOLS
# ═══════════════════════════════════════════════

def _get_skill_lib():
    try:
        import skills
        return skills.get_skill_library()
    except Exception:
        return None


def skill_save(name, description, keywords, steps, code_template="", tags=None):
    lib = _get_skill_lib()
    if not lib:
        return "[error] skill library tidak tersedia"
    return lib.save(name, description, keywords, steps, code_template, tags)


def skill_load(name):
    lib = _get_skill_lib()
    if not lib:
        return "[error] skill library tidak tersedia"
    return lib.load(name)


def skill_search(query):
    lib = _get_skill_lib()
    if not lib:
        return "[error] skill library tidak tersedia"
    return lib.search(query)


def skill_list():
    lib = _get_skill_lib()
    if not lib:
        return "[error] skill library tidak tersedia"
    return lib.list_all()


def _dispatch_skill_save(args):
    return skill_save(
        args["name"],
        args["description"],
        args["keywords"],
        args["steps"],
        args.get("code_template", ""),
        args.get("tags"),
    )

def _dispatch_skill_load(args): return skill_load(args["name"])
def _dispatch_skill_search(args): return skill_search(args["query"])
def _dispatch_skill_list(args): return skill_list()
def _dispatch_done(args): return task_done(args["summary"])

DISPATCH = {
    "bash_exec": _dispatch_bash,
    "install_package": _dispatch_install,
    "write_file": _dispatch_write,
    "patch_file": _dispatch_patch,
    "read_file": _dispatch_read,
    "list_dir": _dispatch_list,
    "fetch_url": _dispatch_fetch,
    "web_search": _dispatch_search,
    "search_knowledge": _dispatch_rag_search,
    "index_file": _dispatch_rag_index,
    "rebuild_index": _dispatch_rag_rebuild,
    "rag_stats": _dispatch_rag_stats,
    "skill_save": _dispatch_skill_save,
    "skill_load": _dispatch_skill_load,
    "skill_search": _dispatch_skill_search,
    "skill_list": _dispatch_skill_list,
    "task_done": _dispatch_done,
}
