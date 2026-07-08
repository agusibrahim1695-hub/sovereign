"""
Error Memory System v2.5 — SOVEREIGN Agent
Structured error storage dengan pattern matching & solution recall.
Bukan cuma log doang — tapi beneran belajar dari kesalahan.
"""
import os
import json
import time
import re

MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
ERROR_DB_PATH = os.path.join(MEMORY_DIR, "error-memory.json")
os.makedirs(MEMORY_DIR, exist_ok=True)


def _load_db():
    if not os.path.exists(ERROR_DB_PATH):
        return {"errors": [], "patterns": {}}
    try:
        with open(ERROR_DB_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"errors": [], "patterns": {}}


def _save_db(db):
    with open(ERROR_DB_PATH, "w") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def _extract_pattern(error_msg):
    """Ekstrak pattern dari error message (misal: 'ModuleNotFoundError: No module named X')."""
    # Python error patterns
    patterns = [
        (r"ModuleNotFoundError:\s*No module named '([^']+)'", "missing_module"),
        (r"ImportError:\s*cannot import name '([^']+)'", "import_error"),
        (r"SyntaxError:\s*(.+)", "syntax_error"),
        (r"TypeError:\s*(.+)", "type_error"),
        (r"FileNotFoundError:\s*(.+)", "file_not_found"),
        (r"PermissionError:\s*(.+)", "permission_error"),
        (r"ConnectionError:\s*(.+)", "connection_error"),
        (r"TimeoutError:\s*(.+)", "timeout_error"),
        (r"JSONDecodeError:\s*(.+)", "json_error"),
        (r"IndentationError:\s*(.+)", "indentation_error"),
        (r"NameError:\s*name '([^']+)' is not defined", "name_error"),
        (r"AttributeError:\s*(.+)", "attribute_error"),
        (r"ValueError:\s*(.+)", "value_error"),
        (r"KeyError:\s*(.+)", "key_error"),
        (r"IndexError:\s*(.+)", "index_error"),
        (r"AssertionError:\s*(.+)", "assertion_error"),
        (r"RuntimeError:\s*(.+)", "runtime_error"),
        (r"OSError:\s*(.+)", "os_error"),
        (r"HTTPError\s*(\d+)", "http_error"),
        (r"SSLError:\s*(.+)", "ssl_error"),
        # Node/JS errors
        (r"Error:\s*Cannot find module '([^']+)'", "missing_module"),
        (r"SyntaxError:\s*(.+)", "syntax_error"),
        (r"ReferenceError:\s*(.+)", "name_error"),
        # Shell errors
        (r"command not found:\s*(.+)", "command_not_found"),
        (r"No such file or directory", "file_not_found"),
        (r"Permission denied", "permission_error"),
    ]
    
    for regex, pattern_name in patterns:
        match = re.search(regex, error_msg, re.IGNORECASE)
        if match:
            return pattern_name, match.group(1) if match.lastindex else match.group(0)
    
    return "unknown", error_msg[:100]


def _get_solution_hint(pattern_type, detail):
    """Saran solusi berdasarkan pattern error."""
    hints = {
        "missing_module": f"Install module: pip install {detail} --break-system-packages",
        "import_error": f"Cek spelling & versi module. Mungkin perlu update: pip install --upgrade {detail}",
        "syntax_error": "Cek syntax: indentation, kurung, titik dua, dll",
        "type_error": "Cek tipe data. Mungkin perlu convert: int(), str(), list(), dll",
        "file_not_found": "Cek path file. Pastikan file ada & path benar",
        "permission_error": "Cek permission. Mungkin perlu sudo atau ubah chmod",
        "connection_error": "Cek koneksi internet & URL. Coba lagi atau ganti URL",
        "timeout_error": "Request terlalu lama. Coba tambah timeout atau kurangi data",
        "json_error": "JSON tidak valid. Cek format: kurung, koma, quotes",
        "indentation_error": "Indentasi salah. Gunakan spasi yang konsisten",
        "name_error": "Variable/function belum didefinisikan. Cek spelling",
        "attribute_error": "Object tidak punya attribute/method tersebut. Cek docs",
        "value_error": "Value tidak valid untuk fungsi tersebut",
        "key_error": "Key tidak ada di dictionary. Cek key yang tersedia",
        "index_error": "Index di luar range. Cek panjang list/string",
        "command_not_found": f"Command tidak ditemukan. Install: pkg install {detail} atau pakai path lengkap",
    }
    return hints.get(pattern_type, "Cek error message & docs")


class ErrorMemory:
    def __init__(self):
        self.db = _load_db()
    
    def remember(self, error_msg, context="", solution_tried="", success=False):
        """
        Simpan error ke memory.
        - error_msg: pesan error lengkap
        - context: tool/action yang lagi dilakukan
        - solution_tried: solusi yang sudah dicoba
        - success: apakah solusi berhasil
        """
        pattern_type, detail = _extract_pattern(error_msg)
        
        # Cek apakah error serupa sudah ada
        existing = None
        for e in self.db["errors"]:
            if e.get("pattern_type") == pattern_type and e.get("detail") == detail:
                existing = e
                break
        
        if existing:
            # Update error yang sudah ada
            existing["count"] = existing.get("count", 0) + 1
            existing["last_seen"] = time.strftime("%Y-%m-%d %H:%M")
            if solution_tried and success:
                existing["solutions"] = existing.get("solutions", [])
                if solution_tried not in existing["solutions"]:
                    existing["solutions"].append(solution_tried)
            existing["contexts"] = existing.get("contexts", [])
            if context and context not in existing["contexts"]:
                existing["contexts"].append(context)
        else:
            # Error baru
            new_error = {
                "id": len(self.db["errors"]) + 1,
                "pattern_type": pattern_type,
                "detail": detail,
                "full_message": error_msg[:500],
                "count": 1,
                "contexts": [context] if context else [],
                "solutions": [solution_tried] if solution_tried and success else [],
                "first_seen": time.strftime("%Y-%m-%d %H:%M"),
                "last_seen": time.strftime("%Y-%m-%d %H:%M"),
            }
            self.db["errors"].append(new_error)
            
            # Update pattern stats
            if pattern_type not in self.db["patterns"]:
                self.db["patterns"][pattern_type] = {"count": 0, "examples": []}
            self.db["patterns"][pattern_type]["count"] += 1
            if detail not in self.db["patterns"][pattern_type]["examples"]:
                self.db["patterns"][pattern_type]["examples"].append(detail)
                # Keep max 5 examples
                self.db["patterns"][pattern_type]["examples"] = \
                    self.db["patterns"][pattern_type]["examples"][-5:]
        
        _save_db(self.db)
        return f"[error-memory] logged: {pattern_type}:{detail[:50]}"
    
    def check_before_action(self, action_description):
        """
        Cek apakah action ini mirip dengan error yang pernah terjadi.
        Return warning atau None.
        """
        action_lower = action_description.lower()
        
        for error in self.db["errors"]:
            if error.get("count", 0) < 2:  # Skip error yang baru sekali
                continue
            
            # Cek apakah action mengandung detail error yang sama
            detail = error.get("detail", "").lower()
            pattern = error.get("pattern_type", "")
            
            # Special checks per pattern type
            if pattern == "missing_module" and detail in action_lower:
                return (
                    f"⚠️ PERINGATAN: Module '{detail}' pernah gagal di-install sebelumnya "
                    f"({error.get('count', 0)}x). "
                    f"Solutions yang berhasil: {error.get('solutions', ['belum ada'])}"
                )
            
            if pattern == "file_not_found" and any(
                d in action_lower for d in detail.split() if len(d) > 3
            ):
                return (
                    f"⚠️ PERINGATAN: File mirip '{detail}' pernah tidak ditemukan. "
                    f"Cek path dengan list_dir dulu!"
                )
            
            if pattern == "permission_error":
                if "chmod" in action_lower or "sudo" in action_lower:
                    return (
                        f"⚠️ PERINGATAN: Permission error pernah terjadi. "
                        f"Solutions: {error.get('solutions', ['pakai sudo/chmod'])}"
                    )
        
        return None
    
    def get_suggestion(self, error_msg):
        """Dapatkan saran solusi untuk error tertentu."""
        pattern_type, detail = _extract_pattern(error_msg)
        
        # Cari error serupa di memory
        for error in self.db["errors"]:
            if error.get("pattern_type") == pattern_type:
                solutions = error.get("solutions", [])
                if solutions:
                    return (
                        f"💡 Solusi yang pernah berhasil:\n"
                        + "\n".join(f"  - {s}" for s in solutions)
                    )
        
        # Fallback ke hint umum
        hint = _get_solution_hint(pattern_type, detail)
        return f"💡 Saran: {hint}"
    
    def get_context_warnings(self):
        """Ambil semua peringatan yang relevan untuk context saat ini."""
        warnings = []
        for error in self.db["errors"]:
            if error.get("count", 0) >= 3:  # Error yang sering terjadi
                warnings.append(
                    f"⚠️ RECURRING ERROR ({error['count']}x): "
                    f"{error['pattern_type']}:{error.get('detail', '')[:50]}"
                )
        return warnings[:5]  # Max 5 warnings
    
    def stats(self):
        """Statistik error memory."""
        total_errors = len(self.db["errors"])
        total_patterns = len(self.db["patterns"])
        recurring = sum(1 for e in self.db["errors"] if e.get("count", 0) >= 2)
        solved = sum(1 for e in self.db["errors"] if e.get("solutions"))
        
        pattern_stats = []
        for p, data in sorted(
            self.db["patterns"].items(), 
            key=lambda x: x[1].get("count", 0), 
            reverse=True
        )[:5]:
            pattern_stats.append(f"  - {p}: {data.get('count', 0)}x")
        
        return (
            f"📊 Error Memory Stats:\n"
            f"  Total errors: {total_errors}\n"
            f"  Unique patterns: {total_patterns}\n"
            f"  Recurring (2+): {recurring}\n"
            f"  With solutions: {solved}\n"
            f"\nTop patterns:\n" + "\n".join(pattern_stats) if pattern_stats else ""
        )
    
    def forget_old(self, max_age_days=30):
        """Lupakan error yang sudah tua (opsional, untuk cleanup)."""
        # Not implemented yet - bisa ditambah nanti
        pass


# Singleton
_memory = None

def get_error_memory():
    global _memory
    if _memory is None:
        _memory = ErrorMemory()
    return _memory
