#!/usr/bin/env python3
"""
SOVEREIGN RAG (Retrieval Augmented Generation)
==============================================
Pure Python + SQLite — zero heavy dependencies.

Cara kerja:
  1. Split file -> chunks (per ~400 tokens)
  2. Hitung TF-IDF vector per chunk -> simpan di SQLite
  3. Query masuk -> hitung cosine similarity -> return top-N chunks

Fitur:
  - Auto-index seluruh workspace
  - Incremental update (gak re-index file yang gak berubah)
  - Search by query -> top chunks paling relevan
  - Persistent (SQLite) - gak perlu re-index dari awal
"""
import os
import re
import math
import json
import hashlib
import sqlite3
from collections import Counter
from pathlib import Path

# CONFIG
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_data.db")
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50
MAX_INDEX_CHARS = 50000
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".o", ".a", ".dylib",
    ".db", ".sqlite", ".sqlite3",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".wav", ".avi",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
}
SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    "sessions",
}

STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk",
    "pada", "adalah", "akan", "juga", "sudah", "tidak", "bisa", "ada",
    "belum", "hanya", "atau", "karena", "oleh", "harus",
    "kalau", "kalo", "kayak", "gitu", "sih", "dong",
    "deh", "kan", "nih", "lah", "aja", "banget",
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "and", "but", "or", "not", "so", "if", "then",
    "def", "class", "import", "from", "return", "else",
    "while", "try", "except", "with", "self", "none", "true", "false",
    "print", "lambda", "pass", "raise", "yield", "async", "await",
}


def tokenize(text):
    text = text.lower()
    tokens = re.findall(r'[a-z0-9_]+', text)
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def estimate_tokens(text):
    return len(text) // 4


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_tokens = 0
    for line in lines:
        line_tokens = estimate_tokens(line)
        if current_tokens + line_tokens > chunk_size and current_chunk:
            chunks.append("\n".join(current_chunk))
            overlap_lines = []
            overlap_tokens = 0
            for l in reversed(current_chunk):
                lt = estimate_tokens(l)
                if overlap_tokens + lt > overlap:
                    break
                overlap_lines.insert(0, l)
                overlap_tokens += lt
            current_chunk = overlap_lines
            current_tokens = overlap_tokens
        current_chunk.append(line)
        current_tokens += line_tokens
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks


def chunk_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return []
    if len(content) > MAX_INDEX_CHARS:
        content = content[:MAX_INDEX_CHARS]
    chunks = chunk_text(content)
    return [{"chunk_index": i, "content": c, "token_count": estimate_tokens(c)} for i, c in enumerate(chunks)]


def compute_tf(tokens):
    counts = Counter(tokens)
    total = len(tokens)
    if total == 0:
        return {}
    return {t: c / total for t, c in counts.items()}


def cosine_similarity(vec_a, vec_b):
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def file_hash_get(filepath):
    h = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except Exception:
        return ""
    return h.hexdigest()


def should_skip(filepath):
    name = os.path.basename(filepath)
    _, ext = os.path.splitext(name)
    if ext.lower() in SKIP_EXTENSIONS:
        return True
    for d in SKIP_DIRS:
        if d in filepath:
            return True
    return False


class RAGDatabase:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            file_hash TEXT NOT NULL,
            indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            tokens TEXT NOT NULL,
            tf_json TEXT NOT NULL,
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id)")
        self.conn.commit()

    def file_indexed(self, filepath, file_hash):
        c = self.conn.cursor()
        c.execute("SELECT file_hash FROM files WHERE path = ?", (filepath,))
        row = c.fetchone()
        return row and row[0] == file_hash

    def index_file(self, filepath, chunks_data):
        c = self.conn.cursor()
        file_hash = file_hash_get(filepath)
        c.execute("SELECT id FROM files WHERE path = ?", (filepath,))
        old = c.fetchone()
        if old:
            c.execute("DELETE FROM chunks WHERE file_id = ?", (old[0],))
            c.execute("DELETE FROM files WHERE id = ?", (old[0],))
        c.execute("INSERT INTO files (path, file_hash) VALUES (?, ?)", (filepath, file_hash))
        file_id = c.lastrowid
        for chunk in chunks_data:
            tokens = tokenize(chunk["content"])
            tf = compute_tf(tokens)
            c.execute("INSERT INTO chunks (file_id, chunk_index, content, tokens, tf_json) VALUES (?, ?, ?, ?, ?)",
                (file_id, chunk["chunk_index"], chunk["content"], json.dumps(tokens), json.dumps(tf)))
        self.conn.commit()
        return len(chunks_data)

    def delete_file(self, filepath):
        c = self.conn.cursor()
        c.execute("SELECT id FROM files WHERE path = ?", (filepath,))
        row = c.fetchone()
        if row:
            c.execute("DELETE FROM chunks WHERE file_id = ?", (row[0],))
            c.execute("DELETE FROM files WHERE id = ?", (row[0],))
            self.conn.commit()
            return True
        return False

    def search(self, query, top_n=5):
        query_tokens = tokenize(query)
        query_tf = compute_tf(query_tokens)
        c = self.conn.cursor()
        c.execute("SELECT c.id, c.content, c.tf_json, f.path, c.chunk_index FROM chunks c JOIN files f ON c.file_id = f.id")
        results = []
        for row in c.fetchall():
            chunk_id, content, tf_json, fpath, cidx = row
            chunk_tf = json.loads(tf_json)
            sim = cosine_similarity(query_tf, chunk_tf)
            if sim > 0.01:
                results.append({"score": round(sim, 4), "content": content, "file": fpath, "chunk_index": cidx})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]

    def stats(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM files")
        n_files = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM chunks")
        n_chunks = c.fetchone()[0]
        c.execute("SELECT SUM(LENGTH(content)) FROM chunks")
        total_chars = c.fetchone()[0] or 0
        return {"files": n_files, "chunks": n_chunks, "total_chars": total_chars, "est_tokens": total_chars // 4}

    def list_files(self):
        c = self.conn.cursor()
        c.execute("SELECT path, indexed_at FROM files ORDER BY path")
        return [{"path": r[0], "indexed_at": r[1]} for r in c.fetchall()]

    def rebuild(self, workspace_dir):
        c = self.conn.cursor()
        c.execute("DELETE FROM chunks")
        c.execute("DELETE FROM files")
        self.conn.commit()
        return index_workspace(workspace_dir, self)

    def close(self):
        self.conn.close()


def index_workspace(workspace_dir, db=None):
    if db is None:
        db = RAGDatabase()
    total_files = 0
    total_chunks = 0
    skipped = 0
    errors = 0
    for root, dirs, files in os.walk(workspace_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
        for fname in files:
            filepath = os.path.join(root, fname)
            rel_path = os.path.relpath(filepath, workspace_dir)
            if should_skip(filepath):
                skipped += 1
                continue
            try:
                fh = file_hash_get(filepath)
                if not fh:
                    errors += 1
                    continue
                if db.file_indexed(rel_path, fh):
                    continue
                chunks = chunk_file(filepath)
                if not chunks:
                    skipped += 1
                    continue
                n = db.index_file(rel_path, chunks)
                total_files += 1
                total_chunks += n
            except Exception:
                errors += 1
    return {"files_indexed": total_files, "chunks_created": total_chunks, "skipped": skipped, "errors": errors}


# PUBLIC API
_rag_db = None

def get_db():
    global _rag_db
    if _rag_db is None:
        _rag_db = RAGDatabase()
    return _rag_db

def search_knowledge(query, top_n=5):
    db = get_db()
    results = db.search(query, top_n=top_n)
    if not results:
        return "[info] Tidak ditemukan hasil yang relevan."
    lines = []
    for i, r in enumerate(results):
        lines.append(f"[{i+1}] {r['file']} (chunk {r['chunk_index']}, score={r['score']})")
    lines.append("")
    for i, r in enumerate(results):
        content_preview = r["content"][:800]
        lines.append(f"--- Hasil {i+1} ({r['file']}) ---")
        lines.append(content_preview)
        lines.append("")
    return "\n".join(lines)

def index_file_cmd(filepath, workspace_dir):
    db = get_db()
    if not os.path.isabs(filepath):
        filepath = os.path.join(workspace_dir, filepath)
    if not os.path.exists(filepath):
        return f"[error] File tidak ditemukan: {filepath}"
    rel = os.path.relpath(filepath, workspace_dir)
    chunks = chunk_file(filepath)
    if not chunks:
        return f"[info] File kosong atau gak bisa di-index: {filepath}"
    n = db.index_file(rel, chunks)
    return f"[ok] File di-index: {rel} ({n} chunks)"

def rebuild_index(workspace_dir):
    db = get_db()
    result = db.rebuild(workspace_dir)
    return f"[ok] Index rebuilt!\n  Files: {result['files_indexed']}\n  Chunks: {result['chunks_created']}\n  Skipped: {result['skipped']}\n  Errors: {result['errors']}"

def index_stats():
    db = get_db()
    stats = db.stats()
    return f"RAG Index Stats:\n  Files: {stats['files']}\n  Chunks: {stats['chunks']}\n  Characters: {stats['total_chars']:,}\n  Est. tokens: {stats['est_tokens']:,}"

def list_indexed_files():
    db = get_db()
    files = db.list_files()
    if not files:
        return "[info] Belum ada file yang di-index."
    lines = [f"  {f['path']} ({f['indexed_at']})" for f in files]
    return f"Indexed files ({len(files)}):\n" + "\n".join(lines)

if __name__ == "__main__":
    import sys
    _dir = os.path.dirname(os.path.abspath(__file__))
    # Kalau rag_core.py ada di dalam workspace, index dir itu sendiri
    if os.path.basename(_dir) == "workspace":
        ws = _dir
    else:
        ws = os.path.join(_dir, "workspace")
    if len(sys.argv) < 2:
        print("Usage: python3 rag_core.py [index|search|stats|rebuild|list]")
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "index":
        result = index_workspace(ws)
        print(f"Indexed: {result['files_indexed']} files, {result['chunks_created']} chunks")
    elif cmd == "search":
        query = " ".join(sys.argv[2:])
        print(search_knowledge(query))
    elif cmd == "stats":
        print(index_stats())
    elif cmd == "rebuild":
        print(rebuild_index(ws))
    elif cmd == "list":
        print(list_indexed_files())
