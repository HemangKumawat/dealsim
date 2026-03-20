# DealSim MVP — Bug Fix Changelog (2026-03-19)

## Bug 1: Offer extraction crashes on range format

**File:** `src/dealsim_mvp/core/simulator.py` (line 248)

**Before:** `_MONEY_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{1,2})?)\s*(k)?", re.IGNORECASE)`
- `[\d,]+` could match commas alone or produce empty captures
- `_extract_offer("$135-145K")` raised `ValueError: could not convert string to float: ''`

**After:** `_MONEY_RE = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(k)?", re.IGNORECASE)`
- Changed `[\d,]+` to `\d[\d,]*` — requires at least one digit to start the capture
- Added empty-string guard in `_extract_offer()` loop (`if not cleaned: continue`)
- Added null-check on `suffix` before calling `.lower()`

**Verified:** `_extract_offer("$135-145K")` now returns `145000.0` (takes max value from range).

---

## Bug 2: Frontend field name mismatches with API

**Files:** `src/dealsim_mvp/api/models.py`, `static/index.html`

**Audit result:** The working frontend (`static/index.html`) already uses correct field names:
- `data.opponent_name` (correct, matches `CreateSessionResponse.opponent_name`)
- `data.opponent_response` (correct, matches `SendMessageResponse.opponent_response`)
- `data.resolved` (correct, matches `SendMessageResponse.resolved`)
- `data.overall_score`, `data.dimensions`, `data.top_tips` (correct, match `CompleteResponse`)

**Fix:** Updated `models.py` to match the actual inline models in `routes.py`. The stale `models.py` had `negotiation_state` instead of `resolved`/`session_status`, and `ScorecardResponse` with `total`/`grade`/`breakdown` instead of `overall_score`/`dimensions`/`top_tips`. Now both files are in sync.

---

## Bug 3: Session lost on uvicorn reload / multi-worker

**Files:** NEW `src/dealsim_mvp/core/store.py`, modified `src/dealsim_mvp/core/session.py`

**Before:** Sessions stored only in `_SESSIONS` dict — lost on process restart or invisible to other workers.

**After:**
- Created `store.py` with `save_sessions()` and `load_sessions()` using a JSON file (`.dealsim_sessions.json`)
- `_store_session()` now persists all sessions to file after every state change (atomic write via tmp+rename)
- `_restore_from_file()` runs at module import — loads surviving sessions back into memory
- Auto-cleans sessions older than 1 hour on every load
- Falls back gracefully to in-memory if file I/O fails
- Full serialization/deserialization of `NegotiationSession` including persona, state, and transcript

---

## Bug 4: Missing HTML escaping in chat (XSS)

**File:** `static/index.html`

**Before:** Scorecard tips and dimension labels rendered via `innerHTML` with unescaped content — user-influenced text could contain `<script>` tags.

**After:**
- Added `escapeHtml()` utility function using `textContent`-based escaping
- Scorecard dimension labels escaped: `${escapeHtml(label)}`
- Coaching tips escaped: `${escapeHtml(tip)}`
- Chat bubbles already used `textContent` (safe) — no change needed there

---

## Bug 5: No max message length

**Files:** `static/index.html`, `src/dealsim_mvp/api/routes.py`

**Before:** No character limit on user messages. Could send arbitrarily long text.

**After:**
- Frontend: `MAX_MESSAGE_LENGTH = 2000` constant; `sendMessage()` rejects messages exceeding limit with a system message
- API: `SendMessageRequest.message` now has `max_length=2000` in `routes.py` (Pydantic enforced)
- `models.py` already had `max_length=2000` — now consistent

---

## Bug 6: No max rounds limit

**Files:** `static/index.html`, `src/dealsim_mvp/core/session.py`

**Before:** Sessions could continue indefinitely with no round cap.

**After:**
- Server: `MAX_ROUNDS = 20` in `session.py`; `negotiate()` auto-sets `resolved = True` after 20 rounds
- Frontend: `MAX_ROUNDS = 20` constant; after round 20, auto-calls `fetchScorecard()` with user notification

---

## Bug 7: Opponent name shows "AI Opponent" instead of actual name

**File:** `static/index.html`

**Audit result:** The frontend correctly reads `data.opponent_name` at the root level of `CreateSessionResponse`. The `??  'AI Opponent'` fallback only triggers when the field is null/undefined (server error edge case). The API response in `routes.py` correctly populates `opponent_name=state.persona.name`. No fix needed — working as designed.
