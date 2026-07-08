"""
Super Cognition Engine — Chain-of-Thought, Planning, Self-Reflection
Bikin agent jadi beneran "berpikir" sebelum bertindak.
"""
import json
import re
from datetime import datetime


class ThoughtStep:
    """Satu langkah dalam proses berpikir."""
    
    def __init__(self, step_type, content, confidence=1.0):
        self.step_type = step_type  # "observe", "think", "plan", "act", "reflect"
        self.content = content
        self.confidence = confidence
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "type": self.step_type,
            "content": self.content,
            "confidence": self.confidence,
            "time": self.timestamp
        }


class SuperCog:
    """
    Super Cognition Engine.
    Bikin agent mikir step-by-step sebelum eksekusi.
    """
    
    def __init__(self):
        self.thoughts = []
        self.execution_plan = []
        self.current_step = 0
        self.error_patterns = []  # Belajar dari error
        self.skills = {}  # Registry skills
        self.memory = []  # Short-term memory
    
    def observe(self, task):
        """Amati task yang diberikan."""
        thought = ThoughtStep("observe", f"Menganalisis task: {task}")
        self.thoughts.append(thought)
        
        # Extract keywords
        keywords = self._extract_keywords(task)
        complexity = self._estimate_complexity(task)
        
        observation = {
            "task": task,
            "keywords": keywords,
            "complexity": complexity,
            "needs_tools": self._needs_tools(task),
            "estimated_steps": complexity * 2,
            "timestamp": datetime.now().isoformat()
        }
        
        self.memory.append({"type": "observation", "data": observation})
        return observation
    
    def think(self, observation):
        """Proses berpikir berdasarkan observasi."""
        thoughts = []
        
        # 1. Analisis kebutuhan
        if observation["needs_tools"]:
            thoughts.append("Task membutuhkan tool execution")
            
            # 2. Rencanakan tool mana yang dipakai
            suggested_tools = self._suggest_tools(observation)
            thoughts.append(f"Tools yang disarankan: {', '.join(suggested_tools)}")
            
            # 3. Cek error patterns
            if self.error_patterns:
                recent_errors = self.error_patterns[-3:]
                thoughts.append(f"Hindari error patterns: {recent_errors}")
        
        # 4. Estimate difficulty
        difficulty = self._assess_difficulty(observation)
        thoughts.append(f"Difficulty: {difficulty}")
        
        # 5. Confidence assessment
        confidence = self._assess_confidence(observation)
        thoughts.append(f"Confidence: {confidence:.0%}")
        
        thought = ThoughtStep("think", "\n".join(thoughts), confidence)
        self.thoughts.append(thought)
        
        self.memory.append({"type": "thoughts", "data": thoughts})
        return thoughts
    
    def create_plan(self, observation, thoughts):
        """Buat rencana eksekusi."""
        plan = []
        
        if observation["needs_tools"]:
            # Build step-by-step plan
            tools = self._suggest_tools(observation)
            
            for i, tool in enumerate(tools):
                step = {
                    "order": i + 1,
                    "tool": tool,
                    "purpose": self._tool_purpose(tool, observation),
                    "risk": self._assess_risk(tool),
                    "fallback": self._suggest_fallback(tool),
                    "status": "pending"
                }
                plan.append(step)
        else:
            plan.append({
                "order": 1,
                "tool": "text_response",
                "purpose": "Jawab langsung tanpa tool",
                "risk": "none",
                "fallback": None,
                "status": "pending"
            })
        
        self.execution_plan = plan
        thought = ThoughtStep("plan", json.dumps(plan, indent=2))
        self.thoughts.append(thought)
        
        self.memory.append({"type": "plan", "data": plan})
        return plan
    
    def act(self, step_index, result, success):
        """Record hasil eksekusi step."""
        if step_index < len(self.execution_plan):
            self.execution_plan[step_index]["status"] = "done" if success else "failed"
            self.execution_plan[step_index]["result"] = str(result)[:200]
        
        return self.execution_plan[step_index] if step_index < len(self.execution_plan) else None
    
    def reflect(self, result, success):
        """Evaluasi hasil eksekusi."""
        reflection = {
            "success": success,
            "result_summary": str(result)[:200],
            "lessons": [],
            "improvements": []
        }
        
        if not success:
            # Catat error pattern
            error_pattern = self._extract_error_pattern(result)
            if error_pattern:
                self.error_patterns.append({
                    "pattern": error_pattern,
                    "time": datetime.now().isoformat(),
                    "context": str(result)[:100]
                })
                reflection["lessons"].append(f"Error pattern recorded: {error_pattern}")
                
                # Suggest improvement
                improvement = self._suggest_improvement(error_pattern)
                if improvement:
                    reflection["improvements"].append(improvement)
        else:
            reflection["lessons"].append("Task completed successfully")
        
        thought = ThoughtStep("reflect", json.dumps(reflection))
        self.thoughts.append(thought)
        
        self.memory.append({"type": "reflection", "data": reflection})
        return reflection
    
    def get_confidence(self):
        """Hitung confidence score berdasarkan thoughts."""
        if not self.thoughts:
            return 0.5
        
        confidences = [t.confidence for t in self.thoughts if hasattr(t, 'confidence')]
        return sum(confidences) / len(confidences) if confidences else 0.5
    
    def get_thought_process(self):
        """Return full thought process untuk debugging."""
        return [t.to_dict() for t in self.thoughts]
    
    def get_memory_summary(self):
        """Return ringkasan memori."""
        return {
            "total_thoughts": len(self.thoughts),
            "total_plans": len(self.execution_plan),
            "error_patterns": len(self.error_patterns),
            "skills_registered": len(self.skills)
        }
    
    def register_skill(self, name, skill_func, description=""):
        """Register skill baru."""
        self.skills[name] = {
            "func": skill_func,
            "description": description,
            "usage_count": 0,
            "success_rate": 1.0
        }
    
    def use_skill(self, name, *args, **kwargs):
        """Pakai skill yang sudah registered."""
        if name not in self.skills:
            return f"[error] Skill '{name}' not found"
        
        self.skills[name]["usage_count"] += 1
        try:
            result = self.skills[name]["func"](*args, **kwargs)
            return result
        except Exception as e:
            self.skills[name]["success_rate"] *= 0.9
            return f"[error] Skill failed: {e}"
    
    def reset(self):
        """Reset thought process untuk task baru."""
        self.thoughts = []
        self.execution_plan = []
        self.current_step = 0
        # Keep error_patterns and skills (persistent learning)
    
    # === PRIVATE METHODS ===
    
    def _extract_keywords(self, task):
        """Extract keywords dari task."""
        common_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                       "dan", "di", "ke", "dari", "ini", "itu", "untuk", "dengan",
                       "yang", "adalah", "akan", "bisa", "tidak", "belum"}
        
        words = re.findall(r'\w+', task.lower())
        keywords = [w for w in words if w not in common_words and len(w) > 2]
        return list(set(keywords))[:10]
    
    def _estimate_complexity(self, task):
        """Estimate task complexity (1-5)."""
        complexity = 1
        
        # Check indicators
        if any(w in task.lower() for w in ["create", "build", "implement", "bikin", "buat"]):
            complexity += 1
        if any(w in task.lower() for w in ["optimize", "refactor", "improve", "tingkatkan"]):
            complexity += 1
        if any(w in task.lower() for w in ["integrate", "connect", "deploy", "koneksi"]):
            complexity += 1
        if len(task.split()) > 20:
            complexity += 1
        
        return min(complexity, 5)
    
    def _needs_tools(self, task):
        """Check apakah task membutuhkan tools."""
        tool_keywords = ["run", "execute", "install", "create file", "read file",
                        "search", "fetch", "download", "compile", "test",
                        "jalankan", "install", "baca file", "cari", "download",
                        "bikin file", "tulis file", "edit", "update"]
        
        return any(kw in task.lower() for kw in tool_keywords)
    
    def _suggest_tools(self, observation):
        """Suggest tools berdasarkan observasi."""
        tools = []
        task = observation["task"].lower()
        
        if any(w in task for w in ["run", "execute", "jalankan"]):
            tools.append("bash_exec")
        if any(w in task for w in ["install"]):
            tools.append("install_package")
        if any(w in task for w in ["create", "write", "buat", "tulis"]):
            tools.append("write_file")
        if any(w in task for w in ["read", "baca", "lihat"]):
            tools.append("read_file")
        if any(w in task for w in ["search", "cari", "find"]):
            tools.extend(["web_search", "search_knowledge"])
        if any(w in task for w in ["fetch", "download", "ambil"]):
            tools.append("fetch_url")
        if any(w in task for w in ["edit", "update", "ubah", "patch"]):
            tools.append("patch_file")
        
        return tools if tools else ["bash_exec"]
    
    def _tool_purpose(self, tool, observation):
        """Explain purpose of tool usage."""
        purposes = {
            "bash_exec": "Menjalankan command shell",
            "install_package": "Install dependency",
            "write_file": "Membuat file baru",
            "patch_file": "Edit file yang sudah ada",
            "read_file": "Baca isi file",
            "fetch_url": "Ambil data dari web",
            "web_search": "Cari informasi online",
            "search_knowledge": "Cari di knowledge base",
            "list_dir": "Lihat struktur folder",
            "index_file": "Index file ke knowledge base",
            "rebuild_index": "Rebuild seluruh index",
            "task_done": "Tandai task selesai"
        }
        return purposes.get(tool, "Execute tool")
    
    def _assess_risk(self, tool):
        """Assess risiko penggunaan tool."""
        high_risk = ["bash_exec", "write_file"]
        medium_risk = ["install_package", "patch_file", "rebuild_index"]
        
        if tool in high_risk:
            return "high"
        elif tool in medium_risk:
            return "medium"
        return "low"
    
    def _suggest_fallback(self, tool):
        """Suggest fallback jika tool gagal."""
        fallbacks = {
            "bash_exec": "Coba command berbeda atau cek syntax",
            "install_package": "Coba package manager lain (pip/npm/pkg)",
            "write_file": "Cek permissions dan path",
            "patch_file": "Gunakan write_file sebagai alternatif",
            "read_file": "Cek file exists dan permissions",
            "fetch_url": "Coba URL lain atau gunakan web_search",
            "web_search": "Gunakan fetch_url langsung",
            "search_knowledge": "Coba rebuild_index lalu search lagi",
            "index_file": "Cek file exists dan format didukung"
        }
        return fallbacks.get(tool)
    
    def _assess_difficulty(self, observation):
        """Assess difficulty level."""
        complexity = observation["complexity"]
        if complexity <= 2:
            return "easy"
        elif complexity <= 3:
            return "medium"
        return "hard"
    
    def _assess_confidence(self, observation):
        """Assess confidence level."""
        base_confidence = 0.7
        
        # Adjust based on complexity
        if observation["complexity"] <= 2:
            base_confidence += 0.2
        elif observation["complexity"] >= 4:
            base_confidence -= 0.2
        
        # Adjust based on error history
        if self.error_patterns:
            base_confidence -= 0.1 * min(len(self.error_patterns), 3)
        
        return max(0.1, min(1.0, base_confidence))
    
    def _extract_error_pattern(self, result):
        """Extract pattern dari error message."""
        result_str = str(result).lower()
        
        patterns = []
        if "permission denied" in result_str:
            patterns.append("permission_issue")
        if "no such file" in result_str or "file not found" in result_str:
            patterns.append("file_not_found")
        if "syntax error" in result_str:
            patterns.append("syntax_error")
        if "timeout" in result_str:
            patterns.append("timeout")
        if "connection" in result_str or "network" in result_str:
            patterns.append("network_issue")
        if "import" in result_str and "error" in result_str:
            patterns.append("import_error")
        if "type" in result_str and "error" in result_str:
            patterns.append("type_error")
        if "name" in result_str and "error" in result_str:
            patterns.append("name_error")
        
        return patterns[0] if patterns else "unknown_error"
    
    def _suggest_improvement(self, error_pattern):
        """Suggest improvement berdasarkan error pattern."""
        improvements = {
            "permission_issue": "Gunakan sudo atau cek permissions",
            "file_not_found": "Pastikan path benar dengan list_dir",
            "syntax_error": "Baca error message dan perbaiki syntax",
            "timeout": "Gunakan timeout lebih besar atau optimasi command",
            "network_issue": "Cek koneksi internet atau gunakan retry",
            "import_error": "Install package yang dibutuhkan",
            "type_error": "Pastikan tipe data sesuai",
            "name_error": "Pastikan variable/function sudah didefinisikan"
        }
        return improvements.get(error_pattern)


# Global instance
cog = SuperCog()
