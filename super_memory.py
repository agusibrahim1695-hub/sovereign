"""
Super Memory System — Long-term, Short-term, Episodic Memory
Bikin agent punya memori yang bener-bener "hidup".
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import config


class MemoryEntry:
    """Satu entry dalam memori."""
    
    def __init__(self, memory_type, content, importance=0.5, context=None):
        self.id = None  # Will be set by database
        self.type = memory_type  # "fact", "event", "skill", "error", "preference"
        self.content = content
        self.importance = importance  # 0.0 - 1.0
        self.context = context or {}
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.access_count = 0
        self.tags = []
    
    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "importance": self.importance,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "tags": self.tags
        }


class SuperMemory:
    """
    Super Memory System.
    Bikin agent punya memori jangka panjang dan pendek.
    """
    
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "super_memory.db"
        )
        self.short_term = []  # Short-term memory (current session)
        self.working = {}  # Working memory (current task)
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            importance REAL DEFAULT 0.5,
            context TEXT,
            tags TEXT,
            created_at TEXT,
            last_accessed TEXT,
            access_count INTEGER DEFAULT 0
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS relations (
            from_id INTEGER,
            to_id INTEGER,
            relation_type TEXT,
            strength REAL DEFAULT 1.0,
            FOREIGN KEY (from_id) REFERENCES memories(id),
            FOREIGN KEY (to_id) REFERENCES memories(id)
        )''')
        
        conn.commit()
        conn.close()
    
    def remember(self, memory_type, content, importance=0.5, context=None, tags=None):
        """Simpan ke memori."""
        # Create entry
        entry = MemoryEntry(memory_type, content, importance, context)
        if tags:
            entry.tags = tags
        
        # Add to short-term
        self.short_term.append(entry)
        
        # Keep only important ones in short-term
        if len(self.short_term) > 50:
            self.short_term.sort(key=lambda x: x.importance, reverse=True)
            self.short_term = self.short_term[:30]
        
        # Save to database if important enough
        if importance >= 0.3:
            self._save_to_db(entry)
        
        return entry
    
    def recall(self, query=None, memory_type=None, limit=10):
        """Recall dari memori."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        query_conditions = []
        params = []
        
        if memory_type:
            query_conditions.append("type = ?")
            params.append(memory_type)
        
        if query:
            query_conditions.append("content LIKE ?")
            params.append(f"%{query}%")
        
        where_clause = " AND ".join(query_conditions) if query_conditions else "1=1"
        
        c.execute(f"""
            SELECT * FROM memories 
            WHERE {where_clause}
            ORDER BY importance DESC, last_accessed DESC
            LIMIT ?
        """, params + [limit])
        
        memories = []
        for row in c.fetchall():
            entry = MemoryEntry(
                row[1],  # type
                row[2],  # content
                row[3],  # importance
                json.loads(row[4]) if row[4] else {}  # context
            )
            entry.id = row[0]
            entry.tags = json.loads(row[5]) if row[5] else []
            entry.created_at = datetime.fromisoformat(row[6])
            entry.last_accessed = datetime.fromisoformat(row[7])
            entry.access_count = row[8]
            
            # Update access
            c.execute("""
                UPDATE memories 
                SET access_count = access_count + 1, last_accessed = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), entry.id))
            
            memories.append(entry)
        
        conn.commit()
        conn.close()
        
        return memories
    
    def forget(self, memory_id):
        """Hapus dari memori."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        c.execute("DELETE FROM relations WHERE from_id = ? OR to_id = ?", (memory_id, memory_id))
        
        conn.commit()
        conn.close()
    
    def strengthen(self, memory_id, amount=0.1):
        """Perkuat memori (naikkan importance)."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            UPDATE memories 
            SET importance = MIN(1.0, importance + ?)
            WHERE id = ?
        """, (amount, memory_id))
        
        conn.commit()
        conn.close()
    
    def weaken(self, memory_id, amount=0.1):
        """Melemahkan memori (turunkan importance)."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            UPDATE memories 
            SET importance = MAX(0.0, importance - ?)
            WHERE id = ?
        """, (amount, memory_id))
        
        conn.commit()
        conn.close()
    
    def associate(self, from_id, to_id, relation_type="related", strength=1.0):
        """Buat hubungan antar memori."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO relations (from_id, to_id, relation_type, strength)
            VALUES (?, ?, ?, ?)
        """, (from_id, to_id, relation_type, strength))
        
        conn.commit()
        conn.close()
    
    def get_related(self, memory_id, limit=5):
        """Dapatkan memori yang terkait."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            SELECT m.*, r.relation_type, r.strength
            FROM memories m
            JOIN relations r ON (m.id = r.to_id AND r.from_id = ?) OR (m.id = r.from_id AND r.to_id = ?)
            ORDER BY r.strength DESC
            LIMIT ?
        """, (memory_id, memory_id, limit))
        
        memories = []
        for row in c.fetchall():
            entry = MemoryEntry(
                row[1],  # type
                row[2],  # content
                row[3],  # importance
                json.loads(row[4]) if row[4] else {}  # context
            )
            entry.id = row[0]
            memories.append(entry)
        
        conn.commit()
        conn.close()
        
        return memories
    
    def working_set(self, task_id):
        """Access working memory untuk task tertentu."""
        if task_id not in self.working:
            self.working[task_id] = {}
        return self.working[task_id]
    
    def clear_working(self, task_id):
        """Clear working memory untuk task."""
        if task_id in self.working:
            del self.working[task_id]
    
    def get_stats(self):
        """Get memory statistics."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        stats = {}
        
        # Total memories
        c.execute("SELECT COUNT(*) FROM memories")
        stats["total_memories"] = c.fetchone()[0]
        
        # By type
        c.execute("SELECT type, COUNT(*) FROM memories GROUP BY type")
        stats["by_type"] = dict(c.fetchall())
        
        # Average importance
        c.execute("SELECT AVG(importance) FROM memories")
        stats["avg_importance"] = c.fetchone()[0] or 0
        
        # Recent memories
        c.execute("SELECT COUNT(*) FROM memories WHERE created_at > ?", 
                  ((datetime.now() - timedelta(days=7)).isoformat(),))
        stats["last_week"] = c.fetchone()[0]
        
        # Total relations
        c.execute("SELECT COUNT(*) FROM relations")
        stats["total_relations"] = c.fetchone()[0]
        
        conn.close()
        
        return stats
    
    def cleanup(self, days=30, min_importance=0.2):
        """Cleanup old and unimportant memories."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        c.execute("""
            DELETE FROM memories 
            WHERE created_at < ? AND importance < ? AND access_count < 3
        """, (cutoff_date, min_importance))
        
        deleted = c.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted
    
    def export_memories(self, output_file):
        """Export semua memori ke JSON."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT * FROM memories ORDER BY importance DESC")
        
        memories = []
        for row in c.fetchall():
            memories.append({
                "id": row[0],
                "type": row[1],
                "content": row[2],
                "importance": row[3],
                "context": json.loads(row[4]) if row[4] else {},
                "tags": json.loads(row[5]) if row[5] else [],
                "created_at": row[6],
                "last_accessed": row[7],
                "access_count": row[8]
            })
        
        with open(output_file, 'w') as f:
            json.dump(memories, f, indent=2)
        
        conn.close()
        
        return len(memories)
    
    def _save_to_db(self, entry):
        """Save memory entry ke database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO memories (type, content, importance, context, tags, created_at, last_accessed, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.type,
            entry.content,
            entry.importance,
            json.dumps(entry.context),
            json.dumps(entry.tags),
            entry.created_at.isoformat(),
            entry.last_accessed.isoformat(),
            entry.access_count
        ))
        
        entry.id = c.lastrowid
        
        conn.commit()
        conn.close()


# === Specialized Memory Classes ===

class FactMemory(SuperMemory):
    """Memori untuk fakta-fakta."""
    
    def remember_fact(self, fact, source="", confidence=1.0):
        return self.remember(
            "fact",
            fact,
            importance=confidence * 0.8,
            context={"source": source},
            tags=["fact"]
        )
    
    def recall_facts(self, topic=None):
        return self.recall(query=topic, memory_type="fact")


class SkillMemory(SuperMemory):
    """Memori untuk skills yang dipelajari."""
    
    def remember_skill(self, skill_name, how_to_use, success=True):
        importance = 0.7 if success else 0.3
        return self.remember(
            "skill",
            f"{skill_name}: {how_to_use}",
            importance=importance,
            context={"skill": skill_name, "success": success},
            tags=["skill", skill_name]
        )
    
    def recall_skills(self, skill_name=None):
        return self.recall(query=skill_name, memory_type="skill")


class ErrorMemory(SuperMemory):
    """Memori untuk error patterns."""
    
    def remember_error(self, error_msg, solution=None, context=None):
        importance = 0.6 if solution else 0.4
        return self.remember(
            "error",
            error_msg,
            importance=importance,
            context={"solution": solution, **(context or {})},
            tags=["error"]
        )
    
    def recall_errors(self, error_pattern=None):
        return self.recall(query=error_pattern, memory_type="error")
    
    def find_solution(self, error_msg):
        """Cari solusi untuk error."""
        errors = self.recall(error_msg, memory_type="error", limit=5)
        for error in errors:
            if error.context.get("solution"):
                return error.context["solution"]
        return None


class PreferenceMemory(SuperMemory):
    """Memori untuk user preferences."""
    
    def remember_preference(self, preference, value):
        return self.remember(
            "preference",
            f"{preference}: {value}",
            importance=0.9,
            context={"preference": preference, "value": value},
            tags=["preference", preference]
        )
    
    def recall_preference(self, preference):
        prefs = self.recall(preference, memory_type="preference", limit=1)
        if prefs:
            return prefs[0].context.get("value")
        return None


# Global instances
memory = SuperMemory()
facts = FactMemory()
skills_mem = SkillMemory()
errors = ErrorMemory()
preferences = PreferenceMemory()
