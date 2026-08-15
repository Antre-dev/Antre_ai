"""
Local file tools: file_read and file_write.

file_write snapshots the current file to a timestamped .bak before
touching anything, and supports dry_run to preview a diff without
writing a single byte.

Hard rules:
  * .env is off-limits, always. No reads, no writes, no exceptions.
  * Paths resolve against the project root. Absolute paths are
    allowed only when they stay inside the project. No escaping
    through '..'.
"""

import difflib
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FORBIDDEN_NAMES = {".env", ".env.local", ".env.prod", ".env.example"}


def _resolve(path: str) -> Path:
    """Resolve a path against PROJECT_ROOT, blocking escapes and .env."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    p = p.resolve()
    if not p.is_relative_to(PROJECT_ROOT):
        raise ValueError(f"Path escapes the project root: {path}")
    if p.name in FORBIDDEN_NAMES or ".env" in p.parts:
        raise PermissionError(f"Refusing to touch {path}: .env is off-limits.")
    return p


def file_read(path: str, limit: int = 0) -> str:
    """Read a text file, or list a directory. Returns a string."""
    p = _resolve(path)
    if p.is_dir():
        items = sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir())
        return f"{p} ({len(items)} items):\n" + "\n".join(items)
    if not p.exists():
        return f"File not found: {p}"
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if limit and len(lines) > limit:
        return "\n".join(lines[:limit]) + f"\n... [{len(lines) - limit} more lines]"
    return text


def file_write(path: str, content: str, action: str = "write",
               dry_run: bool = False) -> str:
    """Write or append to a file inside the project.

    - action='write': replace the whole file.
    - action='append': add content at the end.
    - dry_run=True: show a unified diff of what would change, no writes.
    Always backs up the previous version to <name>.bak.<timestamp>.
    """
    if action not in ("write", "append"):
        raise ValueError("action must be 'write' or 'append'")
    p = _resolve(path)
    if p.is_dir():
        raise IsADirectoryError(f"{p} is a directory")

    existing = p.read_text(encoding="utf-8", errors="replace") if p.exists() else None
    new_content = content if action == "write" else ((existing or "") + "\n" + content)

    if existing == new_content:
        return f"No change needed: {p} already matches the target."

    if dry_run:
        if existing is None:
            return f"[dry-run] Would create {p} ({len(new_content)} chars)."
        diff = difflib.unified_diff(
            existing.splitlines(), new_content.splitlines(),
            fromfile=str(p) + " (current)", tofile=str(p) + " (new)", lineterm="",
        )
        return "[dry-run] Would modify " + str(p) + ":\n" + "\n".join(diff)

    if existing is not None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = p.with_name(f"{p.name}.bak.{stamp}")
        backup.write_text(existing, encoding="utf-8")
    else:
        backup = None

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(new_content, encoding="utf-8")

    verb = "Updated" if existing is not None else "Created"
    note = f" Backup: {backup.name}." if backup else ""
    return f"{verb} {p} ({len(new_content)} chars).{note}"
