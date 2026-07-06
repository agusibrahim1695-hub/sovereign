"""
Tool definitions. Semua tool jalan dengan cwd = WORKSPACE_DIR (sandbox),
supaya AI gak ngerusak file di luar folder kerja.
"""
import subprocess
import os
import config

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "bash_exec",
            "description": "Jalankan perintah shell di Termux/Linux (cwd = workspace). Pakai untuk clone repo, jalanin script, cek proses, dll.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Perintah shell yang mau dijalankan"}
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
            "description": "Tulis/overwrite file di dalam workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relatif ke workspace"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Baca isi file di dalam workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
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
                "properties": {"path": {"type": "string", "default": "."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Ambil isi halaman web (scraping) dan ekstrak teksnya (bukan HTML mentah). Buat baca artikel, dokumentasi API, harga, dll dari internet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL lengkap termasuk https://"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_done",
            "description": "Panggil ini SEKALI saja saat task sudah selesai sepenuhnya, untuk mengakhiri loop dan kasih laporan ke user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Ringkasan apa yang sudah dikerjakan & hasil akhirnya"}
                },
                "required": ["summary"],
            },
        },
    },
]

RISKY_TOOLS = {"bash_exec", "install_package", "write_file"}


def _safe_path(rel_path: str) -> str:
    full = os.path.abspath(os.path.join(config.WORKSPACE_DIR, rel_path))
    if not full.startswith(os.path.abspath(config.WORKSPACE_DIR)):
        raise ValueError("Path di luar workspace, ditolak demi keamanan.")
    return full


def fetch_url(url: str) -> str:
    try:
        import requests
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


def bash_exec(command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=config.WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=config.BASH_TIMEOUT,
        )
        out = result.stdout[-4000:]
        err = result.stderr[-2000:]
        return f"[exit={result.returncode}]\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    except subprocess.TimeoutExpired:
        return "[error] command timeout"
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
    try:
        full = _safe_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return f"[ok] file ditulis: {path} ({len(content)} bytes)"
    except Exception as e:
        return f"[error] {e}"


def read_file(path: str) -> str:
    try:
        full = _safe_path(path)
        with open(full, "r") as f:
            return f.read()[:8000]
    except Exception as e:
        return f"[error] {e}"


def list_dir(path: str = ".") -> str:
    try:
        full = _safe_path(path)
        return "\n".join(os.listdir(full))
    except Exception as e:
        return f"[error] {e}"


DISPATCH = {
    "bash_exec": lambda args: bash_exec(args["command"]),
    "install_package": lambda args: install_package(args["manager"], args["package"]),
    "write_file": lambda args: write_file(args["path"], args["content"]),
    "read_file": lambda args: read_file(args["path"]),
    "list_dir": lambda args: list_dir(args.get("path", ".")),
    "fetch_url": lambda args: fetch_url(args["url"]),
}
