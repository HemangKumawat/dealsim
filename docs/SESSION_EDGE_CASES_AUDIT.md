# Session Lifecycle Edge Cases Audit

**Date:** 2026-03-19
**Scope:** `core/session.py`, `core/store.py`, `api/routes.py`, `core/scorer.py`, `api/debrief.py`

---

## 1. Create session then immediately complete (no messages sent)

**Code path:** `create_session()` -> `complete_session(session_id)`

**Trace:**
- `create_session` initializes state with `turn_count=0`, `resolved=False`, empty transcript, all counters at zero.
- `complete_session` sets status to COMPLETED, calls `generate_scorecard(state, session_id)`.
- Scorer runs all six dimension scorers against a zero-turn state.

**Outcome:** Works. Scorecard generates successfully.
- Opening Strategy: score 20 (no anchor stated).
- Information Gathering: `ratio = 0 / max(0,1) = 0`, score 15.
- Concession Pattern: `anchor=None, n_conc=0, resolved=False` -> score 50.
- BATNA Usage: score 20.
- Emotional Control: no capitulation/panic detected -> score 85 (generous for zero effort).
- Value Creation: empty user_texts -> score 25.
- Outcome: `turn_count < 2` -> `"incomplete"`.
- Overall: ~33 weighted average.

**Bug found:** Emotional Control scores 85 ("steady, composed negotiating") for a session with zero interaction. This is misleading. The scorer assumes absence of bad signals = composure. Should default to a neutral score (e.g., 50) when `turn_count == 0`.

**Severity:** Low (cosmetic/misleading, not a crash).

---

## 2. Create session then send 20 messages (MAX_ROUNDS) -- auto-complete

**Code path:** `negotiate()` called 20 times.

**Trace:**
- Each call increments `turn_count` via `generate_response`.
- After the 20th call: `state.turn_count >= MAX_ROUNDS` and if `not state.resolved`, it sets `resolved = True`.
- Then `session.status = COMPLETED`, `completed_at` is set.
- The `TurnResult` returned has `resolved=True`, `session_status="completed"`.

**Outcome:** Works. Auto-completes correctly.

**UX observation:** The response to the 20th message includes the opponent's reply AND signals completion simultaneously. The client sees `resolved: true` and `session_status: "completed"` in the same response. However, no scorecard is generated at this point -- the user must still call `/complete` to get it. The auto-complete sets `resolved=True` but does NOT generate a scorecard.

**Bug found:** When auto-completing, `agreed_value` remains `None` unless the simulator happened to set it. The scorer then produces outcome `"deal_reached"` (because `resolved=True`) but `agreed_value` is `None`. This is semantically inconsistent -- resolved=True with no agreed value. The `complete_session` call will produce outcome `"deal_reached"` in the scorecard but `agreed_value: null` in the API response.

**Severity:** Medium. The UX shows "deal reached" with no value, which is confusing.

---

## 3. Create session then close browser then reopen -- session recovery

**Code path:** `_restore_from_file()` called at module import.

**Trace:**
- Every `_store_session` call persists ALL sessions to `.dealsim_sessions.json` via `save_sessions`.
- On server restart, `_restore_from_file()` runs at module load (line 241).
- `load_sessions()` reads the JSON file, auto-cleans sessions older than 1 hour.
- Each session is deserialized back into `NegotiationSession` with full state.

**Outcome:** Recoverable, with a caveat.

**Bug found:** The `opening_turn` field is NOT serialized/deserialized. After recovery, `session.opening_turn` is `None`. If any code path relies on this field post-recovery, it will get `None`. Currently no endpoint reads `opening_turn` after creation, so this is latent.

**Bug found:** The 1-hour auto-clean in `store.py` means sessions created >1 hour ago are silently dropped on restart. If a user leaves a browser tab open for 2 hours, closes it, and the server restarts, the session is gone. No 404 distinction between "never existed" and "expired".

**Severity:** Medium (1-hour TTL is aggressive for an MVP; opening_turn loss is low).

---

## 4. Create 1000 sessions rapidly -- store handling and memory

**Code path:** 1000x `create_session()` -> `_store_session()` -> `_persist_all()`.

**Trace:**
- Each `create_session` acquires `_sessions_lock`, adds to `_SESSIONS` dict, then calls `_persist_all()`.
- `_persist_all()` serializes ALL sessions and writes the entire JSON file.
- `save_sessions()` acquires `_store_lock`, writes to tmp file, does `fsync`, then `os.replace`.
- So for 1000 sessions: the 1000th write serializes all 1000 sessions and writes a ~1-5MB file.

**Bug found: O(N^2) persistence.** Creating N sessions requires writing 1+2+3+...+N session records total to disk = O(N^2) I/O. The 1000th create writes all 1000 sessions. This is a significant performance bottleneck under load.

**Bug found: Double locking.** `_store_session` holds `_sessions_lock` while calling `_persist_all()`, which internally calls `save_sessions()`, which acquires `_store_lock`. These are two separate locks. This is not a deadlock (always acquired in the same order), but `_sessions_lock` is held for the entire duration of file I/O, blocking ALL session reads (`_load_session` also acquires `_sessions_lock`). Under 1000 rapid creates, every `negotiate()` call on any session blocks until the file write completes.

**Memory:** Each `NegotiationSession` holds a `NegotiationState`, `NegotiationPersona`, and a `RuleBasedSimulator`. Rough estimate: ~5-10KB per session in memory. 1000 sessions = ~5-10MB. Not a problem for memory, but the file I/O is the bottleneck.

**Severity:** High for production. The API becomes unresponsive under concurrent load due to lock contention on file writes.

---

## 5. Send message to a completed session -- 409 error

**Code path:** `api_send_message()` -> `negotiate()` -> status check.

**Trace:**
- `negotiate()` calls `_load_session(session_id)` -- succeeds.
- Checks `session.status != SessionStatus.ACTIVE` -- True (status is COMPLETED).
- Raises `RuntimeError("Session {id} is completed -- cannot accept new turns.")`.
- In `routes.py`, `RuntimeError` is caught by the `except (ValueError, RuntimeError)` block (line 400).
- Returns HTTP 409 with the error message.

**Outcome:** Correct. Returns 409 with a clear message.

**No bugs.**

---

## 6. Send message to non-existent session -- 404 error

**Code path:** `api_send_message()` -> `negotiate()` -> `_load_session()`.

**Trace:**
- `_validate_session_id` checks UUID4 format. If valid format but non-existent: passes.
- `_load_session` does `_SESSIONS.get(session_id)` -> `None` -> raises `KeyError`.
- In `routes.py`, `KeyError` is caught (line 398) -> HTTP 404.

**Outcome:** Correct. Returns 404.

**Edge case:** If the session_id is not a valid UUID4 format (e.g., "abc"), `_validate_session_id` returns HTTP 400 before the 404 logic runs. This is correct behavior.

**No bugs.**

---

## 7. Send an empty message -- validation

**Code path:** `api_send_message()` with `body.message = ""`.

**Trace:**
- `SendMessageRequest` has `message: str = Field(min_length=1, max_length=2000)`.
- Pydantic validates BEFORE the endpoint function runs.
- Empty string fails `min_length=1` -> HTTP 422 with Pydantic validation error detail.

**Outcome:** Correct. Pydantic catches it with a 422.

**No bugs.**

---

## 8. Send a 10KB message -- truncation/rejection

**Code path:** `api_send_message()` with a ~10,000 character message.

**Trace:**
- `SendMessageRequest.message` has `max_length=2000`.
- 10KB (~10,000 chars) exceeds 2000 -> Pydantic rejects with HTTP 422.

**Outcome:** Correct. Rejected at validation layer.

**No bugs.** The 2000-char limit is reasonable for a negotiation message.

---

## 9. Two simultaneous requests to the same session -- race condition

**Code path:** Two concurrent `negotiate(session_id, msg)` calls.

**Trace:**
1. Thread A: `_load_session(sid)` acquires `_sessions_lock`, reads session, releases lock.
2. Thread B: `_load_session(sid)` acquires `_sessions_lock`, reads THE SAME session object (same reference), releases lock.
3. Thread A: calls `simulator.generate_response(session.state, msgA)` -- mutates `state` in place.
4. Thread B: calls `simulator.generate_response(session.state, msgB)` -- mutates THE SAME `state` object concurrently.
5. Both threads then call `_store_session` -- last writer wins.

**Bug found: Race condition.** `_load_session` returns a reference to the same `NegotiationSession` object in memory. Two threads mutating `session.state` concurrently will corrupt the state (interleaved transcript, wrong turn counts, duplicated entries). The `_sessions_lock` only protects dict access, not the session object itself.

**Impact:** Corrupted transcript, wrong scores, potential crashes from inconsistent state.

**Severity:** High. FastAPI with uvicorn uses thread pools for sync endpoints, making this exploitable under normal concurrent usage.

---

## 10. Complete a session twice -- idempotent or error

**Code path:** Two calls to `complete_session(session_id)`.

**Trace:**
- First call: `session.scorecard is None` -> generates scorecard, caches it, returns.
- Second call: `session.scorecard is not None` -> returns cached scorecard immediately (line 357-358).

**Outcome:** Idempotent. Returns the same scorecard both times.

**No bugs.** This is explicitly documented in the docstring: "Safe to call on an already-completed session -- returns cached scorecard."

---

## 11. Request debrief before completion -- behavior

**Code path:** `api_get_debrief(session_id)` on an ACTIVE session.

**Trace:**
- `get_session_state(session_id)` succeeds regardless of status.
- `generate_debrief(state, session_id)` runs on the current state.
- No status check exists in the debrief endpoint.

**Outcome:** Works. Returns a debrief for an in-progress session.

**Bug found: Information leak.** The debrief reveals `opponent_target`, `opponent_reservation`, `hidden_constraints`, and `money_left_on_table`. If called mid-session, the user sees the opponent's hidden parameters and can exploit them in subsequent messages. There is no guard preventing this.

**Severity:** High (game-breaking for the simulation's educational purpose). The debrief and playbook endpoints should check session status and return 409 if the session is still ACTIVE.

---

## 12. Request playbook for a session that hasn't started -- response

**Code path:** `api_get_playbook(session_id)` on a fresh session (0 turns).

**Trace:**
- `get_session_state(session_id)` returns state with all zeros.
- `complete_session(session_id)` is called (line 561) -- this COMPLETES the session as a side effect.
- Scorecard is generated (see scenario 1 above).
- `generate_playbook(state, session_id, scorecard.overall)` runs on zero-turn state.

**Outcome:** Returns a playbook, but also silently completes the session.

**Bug found:** Requesting a playbook has the side effect of completing the session. If a user accidentally hits the playbook endpoint, their active session is terminated. The playbook endpoint calls `complete_session()` internally to get the scorecard.

**Severity:** Medium. Accidental session termination from a GET request violates the principle of safe/idempotent GETs.

---

## 13. Server restart mid-session -- state recovery from file

**Code path:** Server stops -> restarts -> `_restore_from_file()`.

**Trace:**
- On normal operation, every state change writes to `.dealsim_sessions.json`.
- On restart, `_restore_from_file()` loads the file, deserializes all sessions.
- The `RuleBasedSimulator` is reconstructed fresh (line 192 in `_deserialize_session`).
- Active sessions resume from their last persisted state.

**Outcome:** Recovered, with caveats from scenario 3.

**Additional concern:** If the server crashes mid-write (between `open(tmp, "w")` and `os.replace`), the tmp file exists but the original is intact. On next `load_sessions()`, it reads the original (safe). The tmp file is orphaned but harmless. This is correct -- the atomic write pattern works.

**Bug found:** The `scorecard` field is not serialized. If a session was completed and had a cached scorecard, after restart the scorecard is `None`. Calling `complete_session` again will regenerate it (idempotent), so this is functional but wastes computation.

**Severity:** Low.

---

## 14. Corrupt session file on disk -- graceful degradation

**Code path:** `load_sessions()` with invalid JSON.

**Trace:**
- `json.load(f)` raises an exception.
- `load_sessions()` catches it, logs a warning, renames the file to `.corrupt.{timestamp}`.
- Returns empty dict.
- `_restore_from_file()` proceeds with zero sessions loaded.
- Server starts fresh with no sessions.

**Outcome:** Graceful degradation. All existing sessions are lost, but the server starts cleanly. The corrupt file is preserved for forensics.

**Edge case:** If the file contains valid JSON but with wrong schema (e.g., missing `"sessions"` key), `payload.get("sessions", {})` returns `{}`. No crash, just empty sessions.

**Edge case:** If individual session data is malformed (e.g., missing `"persona"` key), `_deserialize_session` will raise a `KeyError`. This happens inside `_restore_from_file`'s try/except, which catches ALL exceptions. One bad session kills recovery of ALL sessions.

**Bug found:** The `_restore_from_file` error handling is all-or-nothing. If session #50 out of 100 has corrupt data, all 100 sessions are lost. The loop should catch per-session exceptions and skip only the bad one.

**Severity:** Medium. A single corrupt session entry wipes all session recovery.

---

## Summary of Bugs Found

| # | Scenario | Bug | Severity |
|---|----------|-----|----------|
| 1 | Immediate complete | Emotional Control scores 85 for zero interaction | Low |
| 2 | Max rounds | `resolved=True` with `agreed_value=None` is semantically inconsistent | Medium |
| 3 | Browser reopen | `opening_turn` not serialized; 1-hour TTL aggressive | Medium |
| 4 | 1000 sessions | O(N^2) persistence; lock contention blocks all reads during writes | High |
| 9 | Concurrent requests | Race condition: shared mutable state without per-session locking | High |
| 11 | Debrief before complete | Reveals hidden opponent parameters mid-game | High |
| 12 | Playbook pre-start | GET request silently completes session (side effect) | Medium |
| 14 | Corrupt file | One bad session entry kills all session recovery | Medium |
| N/A | `api_get_session` | `status` field returns `persona.name` instead of session status (line 492 of routes.py) | Medium |

### Additional Observation (routes.py line 492)

`api_get_session` sets `status=state.persona.name` instead of the actual session status. This means the GET `/sessions/{id}` endpoint returns the opponent's name in the `status` field. The correct value should come from the session's `status` attribute, not from the negotiation state's persona name.
