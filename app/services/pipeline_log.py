"""In-memory pipeline activity log.

Stores per-session log entries that the frontend polls to display
a real-time activity feed during pipeline execution.
"""

import threading
from datetime import datetime, timezone
from typing import Optional

_lock = threading.Lock()
_logs: dict[str, list[dict]] = {}
_progress: dict[str, dict] = {}  # session_id -> {step, pct}


def add_log(
    session_id: str,
    step: str,
    message: str,
    detail: Optional[str] = None,
    emoji: str = "",
) -> None:
    entry = {
        "step": step,
        "emoji": emoji,
        "message": message,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _logs.setdefault(session_id, []).append(entry)


def set_progress(session_id: str, step: str, pct: float) -> None:
    with _lock:
        _progress[session_id] = {"step": step, "pct": round(pct, 1)}


def get_progress(session_id: str) -> dict:
    with _lock:
        return _progress.get(session_id, {"step": "", "pct": 0})


def get_logs(session_id: str, after: int = 0) -> list[dict]:
    with _lock:
        return list(_logs.get(session_id, [])[after:])


def clear(session_id: str) -> None:
    with _lock:
        _logs.pop(session_id, None)
        _progress.pop(session_id, None)
