"""
Self-Health System v2.5 — SOVEREIGN Agent
Agent bisa cek & fix diri sendiri otomatis.
"""
import os
import sys
import json
import time
import subprocess
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CRITICAL_FILES = [
    "agent.py", "tools.py", "providers.py", "config.py",
    "error_memory.py", "skills.py", "rag_core.py", "main.py"
]
HEALTH_LOG = os.path.join(BASE_DIR, "memory", "health-log.json")


def _load_health_log():
    os.makedirs(os.path.dirname(HEALTH_LOG), exist_ok=True)
    if os.path.exists(HEALTH_LOG):
        try:
            with open(HEALTH_LOG) as f:
                return json.load(f)
        except Exception:
            pass
    return {"checks": [], "issues_fixed": 0, "issues_found": 0}


def _save_health_log(data):
    os.makedirs(os.path.dirname(HEALTH_LOG), exist_ok=True)
    with open(HEALTH_LOG, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_syntax():
    """Cek syntax semua file .py kritis."""
    issues = []
    fixed = []
    for fname in CRITICAL_FILES:
        fpath = os.path.join(BASE_DIR, fname)
        if not os.path.exists(fpath):
            issues.append({"file": fname, "error": "FILE MISSING"})
            continue
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", fpath],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                err = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown"
                issues.append({"file": fname, "error": err})
        except Exception as e:
            issues.append({"file": fname, "error": str(e)})
    return {"name": "syntax", "passed": len(CRITICAL_FILES) - len(issues),
            "total": len(CRITICAL_FILES), "issues": issues, "fixed": fixed}


def check_imports():
    """Cek semua module bisa di-import."""
    modules = ["config", "providers", "tools", "rag_core",
               "skills", "error_memory", "agent"]
    issues = []
    for mod in modules:
        try:
            __import__(mod)
        except Exception as e:
            issues.append({"module": mod, "error": str(e)})
    return {"name": "imports", "passed": len(modules) - len(issues),
            "total": len(modules), "issues": issues}


def check_tools():
    """Cek tool dispatch lengkap."""
    try:
        import tools
        expected = [
            "bash_exec", "install_package", "write_file", "patch_file",
            "read_file", "list_dir", "fetch_url", "web_search",
            "search_knowledge", "index_file", "rebuild_index", "rag_stats",
            "skill_save", "skill_load", "skill_search", "skill_list",
            "task_done"
        ]
        missing = [t for t in expected if t not in tools.DISPATCH]
        return {"name": "tools", "passed": len(expected) - len(missing),
                "total": len(expected), "issues": [{"missing": m} for m in missing]}
    except Exception as e:
        return {"name": "tools", "passed": 0, "total": 0,
                "issues": [{"error": str(e)}]}


def check_disk():
    """Cek disk usage."""
    try:
        stat = os.statvfs(BASE_DIR)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used_pct = round((1 - free / total) * 100, 1) if total > 0 else 0
        return {"name": "disk", "total_mb": round(total / 1048576),
                "free_mb": round(free / 1048576), "used_pct": used_pct,
                "issues": [{"warning": "disk > 90%"}] if used_pct > 90 else []}
    except Exception as e:
        return {"name": "disk", "issues": [{"error": str(e)}]}


def check_memory_db():
    """Cek error memory & skill DB."""
    issues = []
    # Error memory
    em_path = os.path.join(BASE_DIR, "memory", "error-memory.json")
    if os.path.exists(em_path):
        try:
            with open(em_path) as f:
                data = json.load(f)
            if len(data.get("errors", [])) > 100:
                issues.append({"warning": f"error_memory: {len(data['errors'])} entries (besar)"})
        except Exception:
            issues.append({"error": "error-memory.json corrupt → reset"})
            try:
                with open(em_path, "w") as f:
                    json.dump({"errors": [], "patterns": {}}, f)
                issues[-1]["fixed"] = True
            except Exception:
                pass
    # Skill DB
    sk_path = os.path.join(BASE_DIR, "memory", "skill-library.json")
    if os.path.exists(sk_path):
        try:
            with open(sk_path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                issues.append({"error": "skill-library.json corrupt → reset"})
        except Exception:
            issues.append({"error": "skill-library.json corrupt → reset"})
    return {"name": "memory_db", "issues": issues}


def check_pycache():
    """Cek & bersihkan __pycache__ berlebihan."""
    total_size = 0
    count = 0
    for root, dirs, files in os.walk(BASE_DIR):
        if "__pycache__" in root:
            for f in files:
                fp = os.path.join(root, f)
                total_size += os.path.getsize(fp)
                count += 1
    size_mb = round(total_size / 1048576, 2)
    issues = []
    if size_mb > 5:
        issues.append({"warning": f"__pycache__ {size_mb}MB ({count} files) — consider cleanup"})
    return {"name": "pycache", "size_mb": size_mb, "file_count": count, "issues": issues}


def cleanup_pycache():
    """Hapus semua __pycache__."""
    count = 0
    for root, dirs, files in os.walk(BASE_DIR):
        if "__pycache__" in root:
            for f in files:
                os.remove(os.path.join(root, f))
                count += 1
            os.rmdir(root)
    return count


def full_health_check(auto_fix=True):
    """
    Jalankan semua health checks.
    Returns dict dengan results, overall status, dan actions.
    """
    checks = [
        check_syntax(),
        check_imports(),
        check_tools(),
        check_disk(),
        check_memory_db(),
        check_pycache(),
    ]

    total_issues = sum(len(c.get("issues", [])) for c in checks)
    total_fixed = 0

    # Auto-fix: bersihkan pycache kalau terlalu besar
    if auto_fix:
        for c in checks:
            if c["name"] == "pycache" and c.get("size_mb", 0) > 5:
                cleaned = cleanup_pycache()
                total_fixed += cleaned

    # Status
    if total_issues == 0:
        status = "🟢 HEALTHY"
    elif total_issues <= 2:
        status = "🟡 WARNING"
    else:
        status = "🔴 CRITICAL"

    result = {
        "status": status,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_issues": total_issues,
        "total_fixed": total_fixed,
        "checks": checks,
    }

    # Log
    log = _load_health_log()
    log["checks"].append({
        "time": result["timestamp"],
        "status": status,
        "issues": total_issues,
        "fixed": total_fixed
    })
    log["checks"] = log["checks"][-50:]  # Keep last 50
    log["issues_found"] = log.get("issues_found", 0) + total_issues
    log["issues_fixed"] = log.get("issues_fixed", 0) + total_fixed
    _save_health_log(log)

    return result


def format_report(result):
    """Format health check jadi teks yang mudah dibaca."""
    lines = [
        f"═══ HEALTH CHECK: {result['status']} ═══",
        f"Time: {result['timestamp']}",
        f"Issues: {result['total_issues']} found, {result['total_fixed']} fixed",
        ""
    ]
    for c in result["checks"]:
        name = c["name"]
        issues = c.get("issues", [])
        if not issues:
            lines.append(f"  ✅ {name}: OK")
        else:
            for issue in issues:
                err = issue.get("error", issue.get("warning", issue.get("missing", "unknown")))
                fixed = " [FIXED]" if issue.get("fixed") else ""
                lines.append(f"  ❌ {name}: {err}{fixed}")
    lines.append("═══════════════════════════════════════")
    return "\n".join(lines)


# === Quick access functions ===

def health():
    """Quick health check → returns formatted string."""
    result = full_health_check(auto_fix=True)
    return format_report(result)


def self_heal():
    """
    Self-heal: check + auto-fix semua yang bisa.
    Returns action summary.
    """
    actions = []
    result = full_health_check(auto_fix=True)

    for c in result["checks"]:
        for issue in c.get("issues", []):
            # Fix: reset corrupt files
            if "corrupt" in issue.get("error", ""):
                if "error-memory" in issue.get("error", ""):
                    em_path = os.path.join(BASE_DIR, "memory", "error-memory.json")
                    with open(em_path, "w") as f:
                        json.dump({"errors": [], "patterns": {}}, f)
                    actions.append("✅ Reset error-memory.json")
                elif "skill-library" in issue.get("error", ""):
                    sk_path = os.path.join(BASE_DIR, "memory", "skill-library.json")
                    with open(sk_path, "w") as f:
                        json.dump({"skills": []}, f)
                    actions.append("✅ Reset skill-library.json")

            # Fix: cleanup pycache
            if "pycache" in issue.get("warning", "") and c["name"] == "pycache":
                cleaned = cleanup_pycache()
                actions.append(f"✅ Cleaned {cleaned} __pycache__ files")

    if not actions:
        actions.append("✅ No fixes needed — system healthy!")

    return {
        "status": result["status"],
        "actions": actions,
        "report": format_report(result)
    }
