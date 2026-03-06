import json
import datetime
from pathlib import Path

SESSIONS_DIR = Path.home() / ".local" / "share" / "terminox" / "sessions"
MAX_SESSIONS = 5
PREVIEW_LEN = 60


def save_session(messages: list, path: Path | None = None) -> None:
    """Save messages to a session file. Skips if no user messages.

    If path is given, overwrites that file. Otherwise creates a new timestamped file.
    """
    if not any(m["role"] == "user" for m in messages):
        return
    now = datetime.datetime.now()
    updated = now.isoformat(timespec="seconds")
    if path is None:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        created = updated
        filename = now.isoformat(timespec="microseconds").replace(":", "-") + ".json"
        path = SESSIONS_DIR / filename
    else:
        existing = json.loads(path.read_text())
        created = existing.get("created", updated)
    path.write_text(json.dumps({"created": created, "updated": updated, "messages": messages}, indent=2))


def load_session(path: Path) -> list:
    """Load messages from a session file."""
    data = json.loads(path.read_text())
    return data["messages"]


def _preview(messages: list) -> str:
    for m in messages:
        if m["role"] == "user":
            text = m["content"].replace("\n", " ").strip()
            if len(text) > PREVIEW_LEN:
                return text[:PREVIEW_LEN] + "..."
            return text
    return "(no user messages)"


def list_sessions() -> list:
    """Return up to MAX_SESSIONS most recent sessions, newest first.

    Each entry: {"path": Path, "created": str, "preview": str}
    """
    if not SESSIONS_DIR.exists():
        return []
    files = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for f in files[:MAX_SESSIONS]:
        try:
            data = json.loads(f.read_text())
            result.append({
                "path": f,
                "created": data.get("created", ""),
                "updated": data.get("updated", ""),
                "preview": _preview(data.get("messages", [])),
            })
        except Exception:
            continue
    return result
