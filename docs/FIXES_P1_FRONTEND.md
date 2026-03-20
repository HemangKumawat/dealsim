# P1 Frontend Integration Fixes

**Date:** 2026-03-19
**Status:** Applied and verified (310/310 tests pass)

## Fix 1: Wire all 10 scenario types into the dropdown

**Problem:** The frontend dropdown only offered 4 options (salary, freelance, business, custom). "business" and "custom" silently defaulted to salary on the backend since no matching templates existed.

**Changes:**
- `static/index.html` (line ~275): Replaced the 4 dropdown `<option>` elements with all 10 scenario types supported by the persona engine: salary, freelance, rent, medical_bill, car_buying, scope_creep, raise, vendor, counter_offer, budget_request. Each uses a human-readable label.
- `src/dealsim_mvp/api/routes.py` (SCENARIOS list): Expanded from 2 to 10 entries so the `/api/scenarios` endpoint returns complete metadata for all scenario types.

## Fix 2: Make opponent tuner sliders actually work

**Problem:** The frontend collected `opponent_params` from the tuner sliders and sent them in the POST body, but the Pydantic model `CreateSessionRequest` had no such field, so FastAPI silently dropped them. The persona generator never saw the values.

**Changes:**
- `src/dealsim_mvp/api/routes.py`: Added `opponent_params: dict | None = None` to `CreateSessionRequest`. Passed it through the scenario dict to persona generation.
- `src/dealsim_mvp/core/persona.py` (`generate_persona_for_scenario`): Added a block after difficulty modifiers that reads `opponent_params` from the scenario dict and applies slider overrides:
  - **Aggressiveness** (0-100): Shifts negotiation style to COMPETITIVE (>70) or ACCOMMODATING (<30)
  - **Flexibility** (0-100): Scales reservation price via factor `1 + (flex-50)/200`
  - **Patience** (0-100): Maps directly to `persona.patience` (0.05-0.95)
  - **Knowledge** (0-100): Maps to `persona.transparency` (0.05-0.95)
  - **Emotion** (0-100): Maps to `persona.emotional_reactivity` (0.05-0.95)
  - **Budget** (0-100): Shifts pressure level to LOW (>70, high authority) or HIGH (<30, low authority)
- Default slider value of 50 produces no change (multiplicative identity / midpoint).

## Fix 3: Guard debrief endpoint against mid-game access

**Problem:** The debrief endpoint returned full hidden state (reservation price, hidden constraints, move analysis) for any session regardless of status. A user could call it mid-negotiation to cheat.

**Changes:**
- `src/dealsim_mvp/core/session.py`: Added `get_session_status()` helper that returns the session's lifecycle status without exposing internal state.
- `src/dealsim_mvp/api/routes.py` (`api_get_debrief`): Now checks session status first. Returns HTTP 409 with message "Session is still active. Complete the negotiation before viewing the debrief." if the session has not been completed.

## Fix 4: Fix playbook silently completing sessions

**Problem:** The playbook endpoint called `complete_session()` which mutated the session status to COMPLETED as a side effect. Viewing a playbook mid-game would end the negotiation.

**Changes:**
- `src/dealsim_mvp/api/routes.py` (`api_get_playbook`): Replaced `complete_session(session_id)` with `generate_scorecard(state, session_id)` which computes the score from current state without any side effects on session status.
- Added import of `generate_scorecard` from `dealsim_mvp.core.scorer`.

## Files Modified

| File | Changes |
|------|---------|
| `static/index.html` | Dropdown options (4 → 10 scenarios) |
| `src/dealsim_mvp/api/routes.py` | CreateSessionRequest model, debrief guard, playbook fix, SCENARIOS list |
| `src/dealsim_mvp/core/persona.py` | Slider override logic in `generate_persona_for_scenario` |
| `src/dealsim_mvp/core/session.py` | Added `get_session_status()` helper |

## Test Results

All 310 existing tests pass with no regressions.
