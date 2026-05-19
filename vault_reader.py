"""
Reads and parses the Obsidian vault, extracting notes and pending tasks.
"""
import re
from pathlib import Path
from datetime import datetime, timedelta


_SKIP_DIRS = {".obsidian", ".trash", ".git", "__pycache__"}

# Matches Obsidian daily note filenames: 2025-05-19.md or 2025-05-19 Monday.md
_DAILY_NOTE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _extract_frontmatter_date(content: str) -> datetime | None:
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    for line in match.group(1).splitlines():
        if re.match(r"\s*(date|created|modified)\s*:", line, re.I):
            date_str = line.split(":", 1)[1].strip().strip('"\'')
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(date_str[:len(fmt)], fmt)
                except ValueError:
                    continue
    return None


def _extract_tasks(content: str, source_file: str, modified: datetime) -> list[dict]:
    tasks = []
    for line in content.splitlines():
        m = re.match(r"\s*-\s+\[\s\]\s+(.+)", line)
        if m:
            task_text = m.group(1).strip()
            # Look for inline date: 📅 2025-05-20 or (due: 2025-05-20)
            due_match = re.search(r"(?:📅|due:?)\s*(\d{4}-\d{2}-\d{2})", task_text, re.I)
            due_date = None
            if due_match:
                try:
                    due_date = datetime.strptime(due_match.group(1), "%Y-%m-%d").isoformat()
                except ValueError:
                    pass
            tasks.append({
                "task": task_text,
                "file": source_file,
                "due_date": due_date,
                "note_modified": modified.isoformat(),
            })
    return tasks


def read_vault(vault_path: str, days_recent: int = 7, max_content_chars: int = 2500) -> dict:
    """
    Walk the vault and return structured data for the AI analyzer.

    Returns:
        {
            "recent_notes": [...],   # modified within days_recent
            "older_notes": [...],    # summary only (title + first 300 chars)
            "all_tasks": [...],
            "total_notes": int,
        }
    """
    vault = Path(vault_path)
    if not vault.exists():
        raise FileNotFoundError(f"Vault não encontrado: {vault_path}")

    cutoff = datetime.now() - timedelta(days=days_recent)
    recent_notes: list[dict] = []
    older_notes: list[dict] = []
    all_tasks: list[dict] = []

    for md_file in vault.rglob("*.md"):
        if any(skip in md_file.parts for skip in _SKIP_DIRS):
            continue

        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        stat = md_file.stat()
        modified = datetime.fromtimestamp(stat.st_mtime)
        relative_path = str(md_file.relative_to(vault))

        # Prefer frontmatter date for daily notes
        fm_date = _extract_frontmatter_date(content)
        effective_date = fm_date or modified

        tasks = _extract_tasks(content, relative_path, modified)
        all_tasks.extend(tasks)

        note = {
            "file": relative_path,
            "modified": modified.isoformat(),
            "effective_date": effective_date.isoformat(),
            "word_count": len(content.split()),
            "task_count": len(tasks),
            "content": content[:max_content_chars],
        }

        if modified > cutoff:
            recent_notes.append(note)
        else:
            # Keep only a brief summary for older notes to save tokens
            older_notes.append({
                "file": relative_path,
                "modified": modified.isoformat(),
                "word_count": note["word_count"],
                "task_count": len(tasks),
                "snippet": content[:300],
            })

    recent_notes.sort(key=lambda n: n["modified"], reverse=True)
    all_tasks.sort(key=lambda t: (t["due_date"] or "9999", t["note_modified"]), reverse=False)

    return {
        "recent_notes": recent_notes[:30],
        "older_notes": older_notes,
        "all_tasks": all_tasks[:50],
        "total_notes": len(recent_notes) + len(older_notes),
        "vault_path": str(vault),
    }
