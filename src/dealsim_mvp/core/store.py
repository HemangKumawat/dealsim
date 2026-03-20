"""
File-based session persistence for DealSim.

Per-session file storage: each session is saved to its own
data/sessions/{session_id}.json file. This eliminates the
full-serialize-all-sessions bottleneck — writes are O(1 session)
regardless of how many sessions are active.

Write pattern: write to a .tmp file, then os.replace() for atomicity.
os.replace() is a single syscall — readers never see a partial write.

Falls back gracefully if the directory is unavailable.
Auto-cleans sessions older than 1 hour at startup via load_all_sessions().

Unit convention: timestamps are ISO 8601 UTC strings.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Session files live in data/sessions/ relative to the project root.
# Respects DEALSIM_DATA_DIR if set (same convention as analytics/feedback).
_DATA_DIR = Path(os.environ.get("DEALSIM_DATA_DIR", "data"))
_SESSIONS_DIR = _DATA_DIR / "sessions"

# Sessions older than this (seconds) are ignored on load.
_MAX_AGE_SECONDS = 3600  # 1 hour


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    """Create the sessions directory if it does not exist."""
    try:
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        logger.debug("Could not create sessions directory %s", _SESSIONS_DIR, exc_info=True)


def _session_path(session_id: str) -> Path:
    return _SESSIONS_DIR / f"{session_id}.json"


# ---------------------------------------------------------------------------
# Per-session write / read
# ---------------------------------------------------------------------------

def save_session(session_id: str, session_data: dict[str, Any]) -> None:
    """
    Persist one session to its own JSON file.

    Uses write-to-tmp then os.replace() for atomic writes.
    No global lock needed — os.replace() is atomic at the OS level,
    and each session has its own file so writers never contend.

    Parameters
    ----------
    session_id:
        UUID string identifying the session.
    session_data:
        JSON-serialisable dict of the session state.
    """
    _ensure_dir()
    target = _session_path(session_id)
    tmp = str(target) + ".tmp"
    try:
        payload = {
            "updated_at": _now_iso(),
            "session": session_data,
        }
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(target))
    except Exception:
        logger.debug("Could not persist session %s", session_id, exc_info=True)
        try:
            os.remove(tmp)
        except OSError:
            pass


def load_session(session_id: str) -> dict[str, Any]:
    """
    Load one session from disk.

    Returns the raw session dict (the value under "session" key).

    Raises
    ------
    FileNotFoundError
        If no file exists for this session_id.
    ValueError
        If the file exists but is corrupt JSON.
    """
    path = _session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(f"No session file for {session_id}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        logger.warning("Corrupt session file %s — archiving", path)
        try:
            corrupt_name = str(path) + f".corrupt.{int(time.time())}"
            os.rename(str(path), corrupt_name)
        except OSError:
            pass
        raise ValueError(f"Corrupt session file for {session_id}") from exc

    return payload.get("session", {})


def load_all_sessions() -> dict[str, dict[str, Any]]:
    """
    Load all session files from disk.

    Called once at startup to restore in-memory state.
    Automatically ignores sessions older than _MAX_AGE_SECONDS.

    Returns
    -------
    dict mapping session_id -> session dict.
    """
    _ensure_dir()
    sessions: dict[str, dict[str, Any]] = {}
    now = time.time()

    try:
        session_files = list(_SESSIONS_DIR.glob("*.json"))
    except Exception:
        logger.debug("Could not list session files in %s", _SESSIONS_DIR, exc_info=True)
        return {}

    stale_count = 0
    for path in session_files:
        # Skip tmp files and corrupt archives
        if path.suffix != ".json" or ".corrupt." in path.name:
            continue

        session_id = path.stem
        try:
            sdata = load_session(session_id)
        except (FileNotFoundError, ValueError):
            continue

        # Age check — delete expired files rather than just skipping them.
        # Without deletion, stale files accumulate on every restart.
        created_str = sdata.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created_str)
            age = now - created_dt.timestamp()
            if age >= _MAX_AGE_SECONDS:
                stale_count += 1
                try:
                    path.unlink()
                    logger.debug("Deleted stale session file %s (age %.0fs)", path.name, age)
                except OSError:
                    pass
                continue
        except (ValueError, TypeError):
            # Can't parse timestamp — skip silently; don't delete (may be a
            # session written by a newer version with a different schema).
            continue

        sessions[session_id] = sdata

    if stale_count:
        logger.info(
            "Cleaned up %d stale session files (>%ds old) at startup",
            stale_count,
            _MAX_AGE_SECONDS,
        )

    return sessions


def delete_session(session_id: str) -> None:
    """Remove a session file from disk. Silently ignores missing files."""
    try:
        _session_path(session_id).unlink(missing_ok=True)
    except Exception:
        pass


def clear_store() -> None:
    """Remove all session files. Used in tests."""
    try:
        for path in _SESSIONS_DIR.glob("*.json"):
            try:
                path.unlink()
            except OSError:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Legacy bulk API — kept for backward compatibility during transition.
# New code should use save_session / load_session directly.
# ---------------------------------------------------------------------------

def save_sessions(sessions_data: dict[str, dict[str, Any]]) -> None:
    """
    Persist multiple sessions by calling save_session for each one.

    Retained for backward compatibility. Prefer save_session() for
    individual writes — it avoids touching sessions you didn't modify.
    """
    for sid, sdata in sessions_data.items():
        save_session(sid, sdata)


def load_sessions() -> dict[str, dict[str, Any]]:
    """Alias for load_all_sessions(). Backward-compatible name."""
    return load_all_sessions()
