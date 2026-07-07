"""
Sync folder sessions/ ke GitHub private repo (gratis, unlimited buat repo private).
Jadi memori gak cuma nyimpen di HP -- kalau HP ilang/reset, history tetep aman di cloud.

Setup: isi GITHUB_TOKEN, GITHUB_REPO (format: username/reponame), GITHUB_BRANCH di .env.
Kalau belum diisi, fungsi di sini otomatis no-op (gak ngapa-ngapain, gak error).
"""
import os
import subprocess
import config

REPO_DIR = os.path.dirname(os.path.abspath(__file__))


def _configured():
    return bool(config.GITHUB_TOKEN and config.GITHUB_REPO)


def _git(*args):
    return subprocess.run(
        ["git", *args], cwd=REPO_DIR, capture_output=True, text=True, timeout=30
    )


def _remote_url():
    return f"https://{config.GITHUB_TOKEN}@github.com/{config.GITHUB_REPO}.git"


def _ensure_remote():
    result = _git("remote")
    if "origin" not in result.stdout.split():
        _git("remote", "add", "origin", _remote_url())
    else:
        _git("remote", "set-url", "origin", _remote_url())


def push_sessions(quiet=True):
    """Simpan sessions/ terbaru ke GitHub. Dipanggil tiap abis save lokal."""
    if not _configured():
        return
    try:
        _ensure_remote()
        _git("add", "sessions")
        _git("commit", "-m", "sync sessions", "--allow-empty")
        r = _git("push", "-u", "origin", f"HEAD:{config.GITHUB_BRANCH}")
        if not quiet and r.returncode != 0:
            print(f"[sync] push gagal: {r.stderr[-300:]}")
    except Exception as e:
        if not quiet:
            print(f"[sync] error: {e}")


def pull_sessions(quiet=True):
    """Ambil sessions/ terbaru dari GitHub. Dipanggil pas buka portal."""
    if not _configured():
        return
    try:
        _ensure_remote()
        r = _git("fetch", "origin", config.GITHUB_BRANCH)
        if r.returncode != 0:
            if not quiet:
                print(f"[sync] fetch gagal (mungkin repo masih kosong): {r.stderr[-300:]}")
            return
        _git("checkout", f"origin/{config.GITHUB_BRANCH}", "--", "sessions")
    except Exception as e:
        if not quiet:
            print(f"[sync] error: {e}")
