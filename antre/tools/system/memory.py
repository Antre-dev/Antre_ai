import json
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path(__file__).resolve().parent.parent.parent / "memory.json"


def _load() -> dict:
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": [], "next_id": 1}


def _save(data: dict) -> None:
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def memory_save(text: str, tags: str = "") -> str:
    """Persist an important fact the model wants to remember."""
    data = _load()
    entry = {
        "id": data["next_id"],
        "text": text.strip(),
        "tags": [t.strip().lower() for t in tags.split(",") if t.strip()],
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    data["entries"].append(entry)
    data["next_id"] += 1
    _save(data)
    return f"Saved to long-term memory as entry #{entry['id']}."


def memory_recall(query: str = "", limit: int = 5) -> str:
    """Return the most relevant stored memories, scored by keyword + tags."""
    data = _load()
    entries = data["entries"]
    if not entries:
        return "Memory is empty."

    words = query.lower().split()
    scored = []
    for e in entries:
        score = 0
        text = e["text"].lower()
        for w in words:
            if w in text:
                score += 1
            if w in e["tags"]:
                score += 2
        scored.append((score, e))

    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    if not query:
        scored = [(0, e) for e in entries[-limit:]]

    lines = [
        f"[#{e['id']}] ({e['created']}) tags: {', '.join(e['tags']) or '-'}\n{e['text']}"
        for s, e in scored[:limit]
    ]
    return "\n\n".join(lines)