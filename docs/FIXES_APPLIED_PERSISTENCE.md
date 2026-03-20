# Persistence Layer Fixes Applied

**Date:** 2026-03-19
**Scope:** Issues #1, #2, #5, #6, #7 from `PERSISTENCE_REVIEW_W1.md`

---

## 1. `core/store.py` — Atomic writes + locking + recovery

**Changes:**
- Replaced the `os.remove()` + `os.rename()` pair with a single `os.replace()` call, which is atomic on both POSIX and Windows. Eliminates the crash window where both files could be lost.
- Added `f.flush()` + `os.fsync(f.fileno())` before the replace to ensure data reaches disk before the rename.
- Added `threading.Lock` (`_store_lock`) guarding all of `save_sessions()`, `load_sessions()`, and `clear_store()`.
- `save_sessions()` now calls `_STORE_DIR.mkdir(parents=True, exist_ok=True)` before writing, so a missing data directory no longer causes silent failure.
- On corrupt JSON during `load_sessions()`, the file is renamed to `.corrupt.{unix_timestamp}` before returning an empty dict. This preserves evidence for forensic debugging.
- Orphaned `.tmp` files are cleaned up in the exception handler of `save_sessions()`.

**Review items addressed:** #1 (atomic writes), #2a (file-level race), #6 (corrupt recovery), #7 (auto-create directory).

---

## 2. `core/session.py` — Thread-safe `_SESSIONS` dict

**Changes:**
- Added `threading.Lock` (`_sessions_lock`).
- `_store_session()`, `_load_session()`, `_restore_from_file()`, and `list_sessions()` now acquire `_sessions_lock` before accessing the `_SESSIONS` dict.
- `_persist_all()` is called while `_sessions_lock` is held by its callers to prevent interleaving of serialization and mutation.

**Review item addressed:** #2b (in-memory dict race).

---

## 3. `analytics.py` — File rotation

**Changes:**
- Added `_rotate_if_needed()` method to `AnalyticsTracker`. Triggers when the JSONL file exceeds 10 MB.
- Rotation scheme: current file becomes `.1`, previous `.1` becomes `.2`, up to `.3` max. Oldest is deleted.
- Rotation runs inside the existing `_lock`, called at the start of every `_append()`.
- All renames use `os.replace()` for atomicity.

**Review item addressed:** #5 (unbounded file growth).

---

## 4. `feedback.py` — File rotation

**Changes:** Identical rotation logic as `analytics.py`, applied to `FeedbackCollector`.

**Review item addressed:** #5 (unbounded file growth).

---

## 5. `core/analytics.py` — No changes needed

This file is a thin shim that delegates to `dealsim_mvp.analytics` and `dealsim_mvp.feedback`. It performs no direct file I/O, so no persistence fixes apply.

---

## Test Results

- **27/27 session tests pass** (`tests/test_session.py`).
- **177/178 non-API tests pass** (the 1 failure in `test_scorer.py` is pre-existing and unrelated to persistence).
- **Smoke tests pass:** save/load cycle, no orphaned `.tmp`, analytics write, feedback write.
- **Pre-existing failures (not introduced by these changes):**
  - `test_api.py::TestSendMessage::test_404_for_nonexistent_session` — API returns 400 instead of 404.
  - `test_scorer.py::TestConcessionPattern::test_no_concessions_with_deal_scores_high` — scorer logic mismatch.

---

## Items NOT addressed (deferred)

| # | Issue | Reason |
|---|-------|--------|
| 3 | File permissions (0o600) | Low severity; Windows support is incomplete for POSIX permissions. Deferred. |
| 4 | Disk-full error propagation | Medium severity; requires API-layer changes (HTTP 507). Deferred to a separate PR. |
| Multi-process locking | `threading.Lock` is sufficient for single-process uvicorn. Multi-worker requires `filelock` or SQLite. Documented as a production prerequisite. |
