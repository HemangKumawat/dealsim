# P1 Engine Fixes — Applied 2026-03-19

All five fixes applied and verified. **310/310 tests pass.**

---

## Fix 1: Offer text parser missing "Base:" and hourly rate formats

**File:** `src/dealsim_mvp/core/offer_analyzer.py`

**Problem:** `parse_offer_text()` failed to extract base salary from bare "Base: $185,000" (no "salary" keyword), bare "Sign-on: $50,000" (no "bonus" keyword), and hourly rates like "$85/hour".

**Changes:**
- Added regex pattern for bare `Base:` format at index 6 in `_PATTERNS["base_salary"]` (no multiplier needed).
- Added regex pattern for hourly rate `$XX/hour` or `$XX/hr` at index 7, with 2080x annualization via `_PAY_PERIOD_MULTIPLIERS[7] = 2080.0`.
- Added regex pattern for bare `Sign-on:` format in `_PATTERNS["signing_bonus"]`.

---

## Fix 2: Opponent text says "holding firm" even when conceding

**File:** `src/dealsim_mvp/core/simulator.py`

**Problem:** In `generate_response()`, `_render_opponent_response` read `state.opponent_last_offer` to determine whether the opponent moved. But that field was already mutated to `new_offer` on line 222, so the holding-firm check (`abs(new_offer - current) < 1`) always evaluated true — producing "I have to stay at $X" text even when the opponent conceded.

**Fix:** `prev_opponent_offer` (already captured before mutation at line 216) is now passed as a keyword argument to `_render_opponent_response`. The function uses it as the baseline for the holding-firm vs. new-offer decision.

---

## Fix 3: User hardening position counted as concession

**File:** `src/dealsim_mvp/core/simulator.py`

**Problem:** `_update_state_from_user_move()` accumulated `user_total_concession` and `user_concession_count` on every price change, regardless of direction. A user increasing their ask from $130K to $140K (hardening) was counted as a concession.

**Fix:** Added direction check using `_user_wants_more()`. Concession is only accumulated when the user moves TOWARD the opponent's position (down in salary scenarios, up in buyer scenarios).

---

## Fix 4: Broken f-string in scope_creep corporate_manager template

**File:** `src/dealsim_mvp/core/persona.py`

**Problem:** The `system_prompt` for `corporate_manager` in `SCOPE_CREEP_TEMPLATES` had a line with `${budget * 1.40:.0f}` but was missing the `f` prefix on that string fragment. The output contained the literal text `${budget * 1.40:.0f}` instead of the computed value.

**Fix:** Added `f` prefix to the second line of the concatenated string.

---

## Fix 5: Auto-complete at MAX_ROUNDS sets agreed_value to None

**File:** `src/dealsim_mvp/core/session.py`

**Problem:** When `negotiate()` auto-completed at `MAX_ROUNDS`, it set `state.resolved = True` but never set `state.agreed_value`, leaving it `None`. Downstream scoring treated this as "no deal reached."

**Fix:** After setting `resolved = True`, compute `agreed_value` as:
1. Midpoint of `user_last_offer` and `opponent_last_offer` (if both exist).
2. Fallback to `opponent_last_offer` alone.
3. Fallback to `user_last_offer` alone.

---

## Test Results

```
310 passed in 0.49s
```
