# DealSim Persistence Layer -- Reliability Review (Week 1)

**Date:** 2026-03-19
**Scope:** `core/store.py`, `core/session.py`, `analytics.py`, `feedback.py`
**Verdict:** Functional for MVP. Seven issues found, three high-severity.

---

## 1. Atomic Writes -- PARTIAL (HIGH)

**File:** `core/store.py`, lines 46-58

The code attempts write-then-rename, which is the correct pattern. However, on Windows there is a crash window between `os.remove()` (line 56) and `os.rename()` (line 57). If the process dies after the remove but before the rename, both the original file and the tmp file are lost -- the original is deleted and the rename never completed.

```python
# Current (vulnerable window between these two calls):
if os.path.exists(str(_STORE_FILE)):
    os.remove(str(_STORE_FILE))
os.rename(tmp, str(_STORE_FILE))
```

**Fix:** Use `os.replace()` which is atomic on both POSIX and Windows (it overwrites the destination in a single syscall). Drop the remove entirely.

```python
def save_sessions(sessions_data: dict[str, dict[str, Any]]) -> None:
    try:
        payload = {
            "updated_at": _now_iso(),
            "sessions": sessions_data,
        }
        tmp = str(_STORE_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(_STORE_FILE))  # atomic on all platforms
    except Exception:
        logger.debug("Could not persist sessions to %s", _STORE_FILE, exc_info=True)
        # Clean up orphaned tmp file
        try:
            os.remove(tmp)
        except OSError:
            pass
```

The `f.flush()` + `os.fsync()` ensures data reaches disk before the rename. Without it, a power loss after rename could leave a zero-length or partial file.

---

## 2. Concurrent Access -- UNPROTECTED (HIGH)

**File:** `core/store.py` -- no locking at all
**File:** `core/session.py` -- no locking on `_SESSIONS` dict

### 2a. File-level race in store.py

Two uvicorn workers (or two async requests in the same worker) can call `save_sessions()` simultaneously. Both write to `.tmp`, one rename overwrites the other. Sessions from the losing write are silently dropped.

**Fix:** Add a `threading.Lock` and, for multi-process safety, use `fcntl.flock` (POSIX) or `msvcrt.locking` (Windows).

```python
import threading

_write_lock = threading.Lock()

def save_sessions(sessions_data: dict[str, dict[str, Any]]) -> None:
    with _write_lock:
        # ... existing write logic with os.replace() fix ...
```

For multi-worker uvicorn (multiple processes), a thread lock is insufficient. Either:
- Switch to SQLite with WAL mode (recommended for production), or
- Use a file-based lock (`filelock` package, pure Python, cross-platform).

### 2b. In-memory dict race in session.py

The global `_SESSIONS` dict is mutated from async request handlers with no lock. Under concurrent requests, `_store_session()` and `_load_session()` can interleave, causing lost updates.

**Fix (minimum):** Add a `threading.Lock` around `_SESSIONS` mutations.

```python
_sessions_lock = threading.Lock()

def _store_session(session: NegotiationSession) -> None:
    with _sessions_lock:
        _SESSIONS[session.session_id] = session
        _persist_all()
```

### 2c. Analytics/Feedback -- ADEQUATE for append-only

Both `analytics.py` and `feedback.py` use `threading.Lock` around their `_append()` methods. This is sufficient for a single-process server. For multi-worker, the append-only JSONL pattern is inherently safer than JSON (a partial line is just skipped on read), so the risk is low.

---

## 3. File Permissions -- NOT SET (LOW)

**Files:** All four modules.

No file is created with explicit permissions. They inherit the default umask, which on many systems is 0o644 (world-readable). The feedback file stores optional email addresses.

**Fix:** Set restrictive permissions on data files at creation time.

```python
import stat

def _ensure_dir(self) -> None:
    self._path.parent.mkdir(parents=True, exist_ok=True)
    # Restrict data directory to owner only
    try:
        os.chmod(self._path.parent, stat.S_IRWXU)  # 0o700
    except OSError:
        pass  # Windows may not support this fully
```

For the store file, open with restricted mode:

```python
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, default=str)
```

---

## 4. Disk Full -- SILENT DATA LOSS (MEDIUM)

**Files:** All writers.

Every write is wrapped in a bare `except Exception` that logs and continues. If the disk is full:
- `store.py`: The `.tmp` file is partially written, rename fails, orphaned `.tmp` left on disk. Next load succeeds from the old file (good), but the `.tmp` wastes the last remaining bytes.
- `analytics.py` / `feedback.py`: The append silently fails. The event is lost permanently. No signal to the caller.

**Fix for store.py:** Clean up the tmp file on failure (see fix in section 1 above).

**Fix for analytics/feedback:** Propagate the error or return a success boolean so callers can retry or alert.

```python
def _append(self, record: dict) -> bool:
    with self._lock:
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            return True
        except OSError as e:
            logger.error("Write failed (disk full?): %s — %s", self._path, e)
            return False
```

At the API layer, if `_append` returns `False`, return HTTP 507 (Insufficient Storage) instead of 200.

---

## 5. Unbounded File Growth -- NO ROTATION (MEDIUM)

**Files:** `analytics.py` (`data/events.jsonl`), `feedback.py` (`data/feedback.jsonl`)

Both files are append-only with no size limit, no rotation, and no archival. The `get_stats()` method reads the entire file into memory on every call. At 100k events (the stated design limit), each `get_stats()` call parses the full file.

Growth estimate: ~200 bytes/event, 1000 sessions/day with 10 events each = 10k events/day = 2 MB/day. After 1 year: ~700 MB. `get_stats()` would parse 700 MB of JSON on every dashboard load.

**Fix (phased):**

Phase 1 (immediate) -- Add a size check and warning:
```python
def _check_size(self) -> None:
    try:
        size_mb = self._path.stat().st_size / (1024 * 1024)
        if size_mb > 50:
            logger.warning("Analytics file is %.1f MB — consider rotation", size_mb)
    except OSError:
        pass
```

Phase 2 (before production) -- Implement daily rotation:
```python
def _rotate_if_needed(self, max_mb: float = 100.0) -> None:
    try:
        if self._path.stat().st_size > max_mb * 1024 * 1024:
            archive = self._path.with_suffix(
                f".{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
            )
            self._path.rename(archive)
            logger.info("Rotated %s -> %s", self._path, archive)
    except OSError:
        pass
```

Phase 3 (production) -- Switch to SQLite for analytics. JSONL is fine for write-heavy/read-rare, but `get_stats()` reading the full file on every call does not scale.

---

## 6. Startup Recovery -- GOOD for store, ADEQUATE for JSONL

**File:** `core/store.py`, `load_sessions()` lines 62-102

If the JSON file is corrupted (truncated write, encoding error), `json.load()` raises, the except catches it, and the function returns `{}`. All sessions are lost but the server starts cleanly. This is acceptable for an MVP where sessions are ephemeral (1-hour TTL).

However, no backup is made before discarding the corrupt file. A single bit flip wipes all active sessions.

**Fix:** Before returning empty on parse failure, rename the corrupt file for forensics.

```python
except Exception:
    logger.warning("Corrupt session store — archiving %s", _STORE_FILE)
    try:
        corrupt_name = str(_STORE_FILE) + f".corrupt.{int(time.time())}"
        os.rename(str(_STORE_FILE), corrupt_name)
    except OSError:
        pass
    return {}
```

**JSONL files (analytics, feedback):** Recovery is inherently good. Corrupt lines are skipped individually (`json.JSONDecodeError` on line 209/139). Only the corrupt line is lost, not the whole file. No fix needed.

---

## 7. Data Directory Creation -- SPLIT BEHAVIOR (LOW)

**analytics.py and feedback.py:** Both call `self._path.parent.mkdir(parents=True, exist_ok=True)` in `__init__`. The `data/` directory is auto-created. Good.

**store.py:** The store file lives at project root (`_STORE_DIR / ".dealsim_sessions.json"`), which already exists. But there is no `mkdir` call. If the computed `_STORE_DIR` path is wrong (e.g., package installed in a read-only location), the write fails silently.

**Fix:** Add a directory existence check in `save_sessions`:

```python
def save_sessions(sessions_data: dict[str, dict[str, Any]]) -> None:
    try:
        _STORE_DIR.mkdir(parents=True, exist_ok=True)
        # ... rest of write logic ...
```

---

## Summary Table

| # | Issue | Severity | File(s) | Status |
|---|-------|----------|---------|--------|
| 1 | Non-atomic write on Windows (remove+rename gap) | HIGH | store.py:55-57 | Use `os.replace()` + `fsync` |
| 2 | No concurrency protection on session store | HIGH | store.py, session.py | Add threading.Lock minimum |
| 3 | No file permissions set | LOW | all | Use 0o600 for data files |
| 4 | Disk-full errors silently swallowed | MEDIUM | all writers | Return error signal, clean tmp |
| 5 | Unbounded JSONL growth, no rotation | MEDIUM | analytics.py, feedback.py | Add rotation, plan SQLite migration |
| 6 | Corrupt JSON discards all sessions without backup | MEDIUM | store.py:73-77 | Archive corrupt file before reset |
| 7 | Store directory not auto-created | LOW | store.py | Add mkdir before write |

**Recommended priority:** Fix #1 and #2 before any multi-worker deployment. Fix #5 before sustained production traffic. The rest can be addressed incrementally.
