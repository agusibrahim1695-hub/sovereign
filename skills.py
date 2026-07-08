"""
Skill System — Modular skills yang bisa dipakai agent.
Setiap skill adalah fungsi standalone yang bisa di-register ke SuperCog.
"""
import os
import json
import subprocess
import config
from datetime import datetime


# === SKILL: Code Analysis ===
def skill_analyze_code(file_path):
    """Analisis kode Python: complexity, functions, classes, imports."""
    try:
        full_path = os.path.join(config.WORKSPACE_DIR, file_path)
        with open(full_path, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        total_lines = len(lines)
        
        # Count features
        functions = [l.strip() for l in lines if l.strip().startswith('def ')]
        classes = [l.strip() for l in lines if l.strip().startswith('class ')]
        imports = [l.strip() for l in lines if l.strip().startswith(('import ', 'from '))]
        
        # Estimate complexity
        max_indent = 0
        for l in lines:
            if l.strip():
                indent = len(l) - len(l.lstrip())
                max_indent = max(max_indent, indent)
        
        return {
            "file": file_path,
            "total_lines": total_lines,
            "functions": len(functions),
            "function_names": [f.replace('def ', '').split('(')[0] for f in functions],
            "classes": len(classes),
            "class_names": [c.replace('class ', '').split('(')[0].split(':')[0] for c in classes],
            "imports": len(imports),
            "max_nesting": max_indent // 4,
            "complexity_score": min(10, (len(functions) + len(classes) + max_indent // 4))
        }
    except Exception as e:
        return {"error": str(e)}


# === SKILL: Project Setup ===
def skill_setup_project(project_name, project_type="python"):
    """Setup project structure baru."""
    try:
        base_dir = os.path.join(config.WORKSPACE_DIR, project_name)
        
        if project_type == "python":
            dirs = ["src", "tests", "docs"]
            files = {
                "README.md": f"# {project_name}\n\nProject description here.\n",
                "requirements.txt": "# Dependencies\n",
                "setup.py": f"from setuptools import setup\n\nsetup(name='{project_name}', version='0.1.0')\n",
                ".gitignore": "__pycache__/\n*.pyc\n.env\nvenv/\n",
                "src/__init__.py": "",
                "tests/__init__.py": ""
            }
        elif project_type == "node":
            dirs = ["src", "test", "docs"]
            files = {
                "README.md": f"# {project_name}\n\nProject description here.\n",
                "package.json": json.dumps({
                    "name": project_name,
                    "version": "1.0.0",
                    "scripts": {"test": "jest"}
                }, indent=2),
                ".gitignore": "node_modules/\n.env\n"
            }
        else:
            return {"error": f"Unknown project type: {project_type}"}
        
        # Create directories
        os.makedirs(base_dir, exist_ok=True)
        for d in dirs:
            os.makedirs(os.path.join(base_dir, d), exist_ok=True)
        
        # Create files
        for file_path, content in files.items():
            full_path = os.path.join(base_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
        
        return {
            "success": True,
            "project": project_name,
            "type": project_type,
            "location": base_dir,
            "structure": dirs + list(files.keys())
        }
    except Exception as e:
        return {"error": str(e)}


# === SKILL: Git Operations ===
def skill_git_status():
    """Get git status dari workspace."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=config.WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        return {
            "clean": len(lines) == 0,
            "changes": len(lines),
            "files": lines[:20]  # Max 20 files
        }
    except Exception as e:
        return {"error": str(e)}


def skill_git_log(count=5):
    """Get recent git commits."""
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{count}"],
            cwd=config.WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return {
            "commits": result.stdout.strip().split('\n') if result.stdout.strip() else []
        }
    except Exception as e:
        return {"error": str(e)}


# === SKILL: System Info ===
def skill_system_info():
    """Get system information."""
    try:
        info = {}
        
        # CPU info
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
        info['cpu_cores'] = cpuinfo.count('processor')
        
        # Memory info
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        for line in meminfo.split('\n'):
            if 'MemTotal' in line:
                info['total_memory'] = line.split(':')[1].strip()
            elif 'MemAvailable' in line:
                info['available_memory'] = line.split(':')[1].strip()
        
        # Disk usage
        result = subprocess.run(
            ["df", "-h", config.WORKSPACE_DIR],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                info['disk_total'] = parts[1] if len(parts) > 1 else 'unknown'
                info['disk_used'] = parts[2] if len(parts) > 2 else 'unknown'
                info['disk_available'] = parts[3] if len(parts) > 3 else 'unknown'
        
        # Uptime
        result = subprocess.run(
            ["uptime", "-p"],
            capture_output=True,
            text=True,
            timeout=5
        )
        info['uptime'] = result.stdout.strip() if result.stdout else 'unknown'
        
        return info
    except Exception as e:
        return {"error": str(e)}


# === SKILL: File Operations ===
def skill_file_stats(file_path):
    """Get detailed file statistics."""
    try:
        full_path = os.path.join(config.WORKSPACE_DIR, file_path)
        
        stat = os.stat(full_path)
        
        with open(full_path, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        return {
            "file": file_path,
            "size_bytes": stat.st_size,
            "size_human": _human_readable_size(stat.st_size),
            "total_lines": len(lines),
            "empty_lines": sum(1 for l in lines if not l.strip()),
            "code_lines": sum(1 for l in lines if l.strip() and not l.strip().startswith('#')),
            "comment_lines": sum(1 for l in lines if l.strip().startswith('#')),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


def _human_readable_size(size):
    """Convert bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


# === SKILL: Search & Discovery ===
def skill_search_files(pattern, directory="."):
    """Search files by pattern in directory."""
    try:
        full_dir = os.path.join(config.WORKSPACE_DIR, directory)
        
        result = subprocess.run(
            ["find", full_dir, "-name", pattern, "-type", "f"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        return {
            "pattern": pattern,
            "directory": directory,
            "matches": len(files),
            "files": [os.path.relpath(f, config.WORKSPACE_DIR) for f in files[:20]]
        }
    except Exception as e:
        return {"error": str(e)}


def skill_grep_search(pattern, directory="."):
    """Search for pattern in file contents."""
    try:
        full_dir = os.path.join(config.WORKSPACE_DIR, directory)
        
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.md",
             pattern, full_dir],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        matches = []
        for line in result.stdout.strip().split('\n')[:20]:
            if ':' in line:
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    matches.append({
                        "file": os.path.relpath(parts[0], config.WORKSPACE_DIR),
                        "line": parts[1],
                        "content": parts[2].strip()
                    })
        
        return {
            "pattern": pattern,
            "matches": len(matches),
            "results": matches
        }
    except Exception as e:
        return {"error": str(e)}


# === SKILL: Quality Check ===
def skill_code_quality(file_path):
    """Quick code quality check."""
    try:
        full_path = os.path.join(config.WORKSPACE_DIR, file_path)
        
        with open(full_path, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        issues = []
        
        # Check for common issues
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Too long lines
            if len(line) > 120:
                issues.append(f"Line {i}: Too long ({len(line)} chars)")
            
            # TODO/FIXME
            if stripped.startswith('#') and ('TODO' in stripped or 'FIXME' in stripped):
                issues.append(f"Line {i}: {stripped[:50]}")
            
            # Missing docstring
            if stripped.startswith('def ') and not stripped.endswith(':'):
                # Check next line for docstring
                if i < len(lines):
                    next_line = lines[i].strip() if i < len(lines) else ''
                    if not next_line.startswith('"""') and not next_line.startswith("'''"):
                        issues.append(f"Line {i}: Function '{stripped.split('(')[0]}' missing docstring")
            
            # Bare except
            if stripped == 'except:':
                issues.append(f"Line {i}: Bare except (use specific exception)")
        
        # Score
        quality_score = max(0, 100 - len(issues) * 5)
        
        return {
            "file": file_path,
            "total_lines": len(lines),
            "issues": issues[:10],
            "total_issues": len(issues),
            "quality_score": quality_score,
            "grade": "A" if quality_score >= 90 else "B" if quality_score >= 70 else "C" if quality_score >= 50 else "D"
        }
    except Exception as e:
        return {"error": str(e)}


# === SKILL: Documentation ===
def skill_generate_readme(project_dir):
    """Generate basic README for project."""
    try:
        full_dir = os.path.join(config.WORKSPACE_DIR, project_dir)
        
        # Gather info
        files = os.listdir(full_dir) if os.path.exists(full_dir) else []
        py_files = [f for f in files if f.endswith('.py')]
        
        # Read first Python file for description
        description = "No description available"
        if py_files:
            first_py = os.path.join(full_dir, py_files[0])
            with open(first_py, 'r') as f:
                content = f.read()
            
            # Extract docstring
            if '"""' in content:
                start = content.find('"""') + 3
                end = content.find('"""', start)
                if end > start:
                    description = content[start:end].strip()
        
        readme = f"""# {project_dir}

{description}

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

## Structure

```
{project_dir}/
{''.join(f'├── {f}\\n' for f in sorted(files))}
```

## License

MIT
"""
        
        readme_path = os.path.join(full_dir, "README.md")
        with open(readme_path, 'w') as f:
            f.write(readme)
        
        return {
            "success": True,
            "file": "README.md",
            "preview": readme[:200]
        }
    except Exception as e:
        return {"error": str(e)}


# === SKILL: Performance ===
def skill_profile_script(script_path):
    """Basic profiling of Python script."""
    try:
        full_path = os.path.join(config.WORKSPACE_DIR, script_path)
        
        import cProfile
        import pstats
        from io import StringIO
        
        # Create profiler
        profiler = cProfile.Profile()
        
        # Compile and run
        with open(full_path, 'r') as f:
            code = f.read()
        
        # Profile (with timeout)
        profiler.enable()
        try:
            exec(compile(code, full_path, 'exec'), {"__name__": "__main__"})
        except:
            pass
        profiler.disable()
        
        # Get stats
        stream = StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats('cumulative')
        stats.print_stats(10)
        
        return {
            "file": script_path,
            "profile": stream.getvalue()[:1000]
        }
    except Exception as e:
        return {"error": str(e)}


# === Skill Registry ===
SKILLS = {
    # Code Analysis
    "analyze_code": {
        "func": skill_analyze_code,
        "description": "Analisis kode: complexity, functions, classes, imports",
        "category": "analysis"
    },
    "code_quality": {
        "func": skill_code_quality,
        "description": "Quick code quality check",
        "category": "analysis"
    },
    
    # Project Setup
    "setup_project": {
        "func": skill_setup_project,
        "description": "Setup project structure baru",
        "category": "project"
    },
    "generate_readme": {
        "func": skill_generate_readme,
        "description": "Generate README untuk project",
        "category": "project"
    },
    
    # Git Operations
    "git_status": {
        "func": skill_git_status,
        "description": "Get git status",
        "category": "git"
    },
    "git_log": {
        "func": skill_git_log,
        "description": "Get recent git commits",
        "category": "git"
    },
    
    # System Info
    "system_info": {
        "func": skill_system_info,
        "description": "Get system information",
        "category": "system"
    },
    
    # File Operations
    "file_stats": {
        "func": skill_file_stats,
        "description": "Get detailed file statistics",
        "category": "file"
    },
    "search_files": {
        "func": skill_search_files,
        "description": "Search files by pattern",
        "category": "file"
    },
    "grep_search": {
        "func": skill_grep_search,
        "description": "Search in file contents",
        "category": "file"
    },
    
    # Performance
    "profile_script": {
        "func": skill_profile_script,
        "description": "Profile Python script performance",
        "category": "performance"
    }
}


def get_skill(name):
    """Get skill function by name."""
    if name in SKILLS:
        return SKILLS[name]["func"]
    return None


def list_skills():
    """List all available skills."""
    return {name: info["description"] for name, info in SKILLS.items()}


def list_skills_by_category():
    """List skills grouped by category."""
    by_category = {}
    for name, info in SKILLS.items():
        cat = info.get("category", "other")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append({"name": name, "description": info["description"]})
    return by_category
