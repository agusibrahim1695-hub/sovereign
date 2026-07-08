"""
Skill Library v2.5 — SOVEREIGN Agent
Template & pattern untuk task berulang. AI recall skill, bukan mikir dari nol.
"""
import os
import json
import time

SKILLS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory", "skills.json")


def _load_skills():
    if not os.path.exists(SKILLS_PATH):
        return []
    try:
        with open(SKILLS_PATH, "r") as f:
            data = json.load(f)
        return data.get("skills", [])
    except Exception:
        return []


def _save_skills(skills):
    os.makedirs(os.path.dirname(SKILLS_PATH), exist_ok=True)
    with open(SKILLS_PATH, "w") as f:
        json.dump({"skills": skills}, f, ensure_ascii=False, indent=2)


def _fuzzy_match(query, keywords):
    """Simple fuzzy: cek apakah ada keyword yang match (partial match ok)."""
    query_lower = query.lower()
    for kw in keywords:
        kw_lower = kw.lower()
        # Exact match atau query mengandung keyword
        if kw_lower in query_lower or query_lower in kw_lower:
            return True
        # Partial: minimal 4 karakter match
        for i in range(len(kw_lower) - 3):
            if kw_lower[i:i+4] in query_lower:
                return True
    return False


class SkillLibrary:
    def __init__(self):
        self.skills = _load_skills()

    def _reload(self):
        self.skills = _load_skills()

    def save(self, name, description, keywords, steps, code_template="", tags=None):
        """Simpan skill baru atau update yang sudah ada."""
        # Cek duplikat berdasarkan nama
        for i, s in enumerate(self.skills):
            if s["name"].lower() == name.lower():
                self.skills[i].update({
                    "description": description,
                    "keywords": keywords,
                    "steps": steps,
                    "code_template": code_template,
                    "tags": tags or [],
                    "updated_at": time.strftime("%Y-%m-%d %H:%M"),
                })
                _save_skills(self.skills)
                return f"[ok] skill '{name}' di-update"

        skill = {
            "id": len(self.skills) + 1,
            "name": name,
            "description": description,
            "keywords": keywords,
            "steps": steps,
            "code_template": code_template,
            "tags": tags or [],
            "use_count": 0,
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "updated_at": time.strftime("%Y-%m-%d %H:%M"),
            "last_used": None,
        }
        self.skills.append(skill)
        _save_skills(self.skills)
        return f"[ok] skill '{name}' disimpan (id={skill['id']})"

    def load(self, name_or_id):
        """Load skill berdasarkan nama atau ID."""
        self._reload()
        for s in self.skills:
            if str(s["id"]) == str(name_or_id) or s["name"].lower() == name_or_id.lower():
                # Increment use_count
                s["use_count"] = s.get("use_count", 0) + 1
                s["last_used"] = time.strftime("%Y-%m-%d %H:%M")
                _save_skills(self.skills)
                return self._format_skill(s)
        return f"[error] skill '{name_or_id}' tidak ditemukan"

    def search(self, query):
        """Cari skill berdasarkan query (fuzzy match keywords)."""
        self._reload()
        matches = []
        for s in self.skills:
            if _fuzzy_match(query, s.get("keywords", [])):
                matches.append(s)
            elif _fuzzy_match(query, [s.get("name", ""), s.get("description", "")]):
                matches.append(s)

        if not matches:
            return f"[info] tidak ada skill yang cocok dengan '{query}'"

        # Sort by use_count
        matches.sort(key=lambda x: x.get("use_count", 0), reverse=True)

        lines = [f"🔍 Ditemukan {len(matches)} skill:\n"]
        for s in matches[:5]:
            lines.append(f"  [{s['id']}] {s['name']} (used {s.get('use_count', 0)}x)")
            lines.append(f"      {s['description']}")
            lines.append(f"      keywords: {', '.join(s.get('keywords', [])[:5])}")
            lines.append("")

        lines.append("💡 Load skill: `skill_load(\"nama skill\")`")
        return "\n".join(lines)

    def list_all(self):
        """List semua skill."""
        self._reload()
        if not self.skills:
            return "📭 Belum ada skill tersimpan.\n💡 Simpan skill baru: `skill_save(...)`"

        lines = [f"📚 Skill Library ({len(self.skills)} skills):\n"]
        # Sort by use_count desc
        sorted_skills = sorted(self.skills, key=lambda x: x.get("use_count", 0), reverse=True)
        for s in sorted_skills:
            tags = " ".join(f"#{t}" for t in s.get("tags", []))
            lines.append(
                f"  [{s['id']}] {s['name']} "
                f"(used {s.get('use_count', 0)}x) {tags}"
            )
            lines.append(f"      {s['description']}")
        return "\n".join(lines)

    def delete(self, name_or_id):
        """Hapus skill."""
        self._reload()
        for i, s in enumerate(self.skills):
            if str(s["id"]) == str(name_or_id) or s["name"].lower() == name_or_id.lower():
                deleted = self.skills.pop(i)
                _save_skills(self.skills)
                return f"[ok] skill '{deleted['name']}' dihapus"
        return f"[error] skill '{name_or_id}' tidak ditemukan"

    def _format_skill(self, skill):
        """Format skill jadi teks yang bisa langsung dipakai AI."""
        lines = [
            f"📋 Skill: {skill['name']}",
            f"📝 {skill['description']}",
            "",
            "🔢 Steps:",
        ]
        for i, step in enumerate(skill.get("steps", []), 1):
            lines.append(f"  {i}. {step}")

        if skill.get("code_template"):
            lines.append("")
            lines.append("💻 Code Template:")
            lines.append(f"```")
            lines.append(skill["code_template"])
            lines.append(f"```")

        lines.append("")
        lines.append(f"📊 Used {skill.get('use_count', 0)}x | Created: {skill.get('created_at', '?')}")
        return "\n".join(lines)

    def get_relevant_skills(self, task_description):
        """Ambil skill yang relevan buat task tertentu (untuk injection ke context)."""
        self._reload()
        relevant = []
        for s in self.skills:
            if _fuzzy_match(task_description, s.get("keywords", [])):
                relevant.append(s)

        if not relevant:
            return ""

        # Ambil top 3 paling sering dipake
        relevant.sort(key=lambda x: x.get("use_count", 0), reverse=True)
        lines = ["💡 SKILL LIBRARY — ada template yang relevan:\n"]
        for s in relevant[:3]:
            lines.append(f"📋 {s['name']}: {s['description']}")
            if s.get("steps"):
                lines.append(f"   Steps: {' → '.join(s['steps'][:4])}")
            lines.append("")
        return "\n".join(lines)


# Singleton
_library = None

def get_skill_library():
    global _library
    if _library is None:
        _library = SkillLibrary()
    return _library
