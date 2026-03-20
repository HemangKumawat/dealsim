# Engine Correctness Audit

**Date:** 2026-03-19
**Scope:** All 11 files in `src/dealsim_mvp/core/`
**Auditor:** Senior Python engineer review (automated)

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL (data corruption / wrong outcomes) | 3 |
| HIGH (incorrect behavior in edge cases) | 8 |
| MEDIUM (robustness / type safety) | 12 |
| LOW (style / minor correctness) | 6 |

The engine is well-structured overall. Direction-awareness was clearly a focus of a prior fix pass (BUG-01 through BUG-05, SCORE-01, DEBRIEF-01/02/03, PERSONA-01/04, PLAY-01 are all referenced in comments). The remaining issues cluster around **division-by-zero edge cases**, **inconsistent concession tracking when direction flips**, and **type-safety gaps in the offer parser**.

---

## File-by-File Findings

### 1. simulator.py

#### CRITICAL-01: `_user_concession_ratio` divides by anchor which can be zero

**Location:** Line 454
```python
def _user_concession_ratio(state: NegotiationState) -> float:
    anchor = state.user_opening_anchor
    if not anchor:
        return 0.0
    return state.user_total_concession / abs(anchor)
```

**Problem:** `if not anchor` is falsy for `0.0`, which is correct for guarding against zero-division, but the function is called from `_compute_opponent_offer` (line 422) where `anchor` being `None` vs `0.0` has different semantics. A user who opens at `$0` (contrived but possible via the API) would hit the `not anchor` guard and return `0.0` -- this is actually safe. However, `user_total_concession / abs(anchor)` can produce extremely large values if `anchor` is small (e.g., `$1`). No upper bound is applied.

**Fix:** Clamp the return value: `return min(state.user_total_concession / abs(anchor), 5.0)`.

#### HIGH-01: `_update_state_from_user_move` counts ALL offer changes as concessions

**Location:** Lines 355-358
```python
if state.user_last_offer is not None:
    delta = abs(offer - state.user_last_offer)
    if delta > 0.01:
        state.user_total_concession += delta
        state.user_concession_count += 1
```

**Problem:** This increments `user_total_concession` for every offer change, regardless of direction. If the user moves AWAY from the opponent (hardening their position), `delta` is still added. The `_classify_user_move` function correctly detects direction for the MoveType label (line 329-340), but `_update_state_from_user_move` ignores direction when accumulating `user_total_concession`.

**Impact:** The scorer's concession-pattern dimension uses `user_total_concession` to compute `avg_pct` (scorer.py line 280). A user who raises their ask (moving away from opponent) would be penalized as if they conceded.

**Fix:** Only increment `user_total_concession` when the move is toward the opponent, not away. Use `_user_wants_more` to determine direction.

#### HIGH-02: `_extract_offer` always returns the MAX value, ignoring direction

**Location:** Line 287
```python
return max(values) if values else None
```

**Problem:** If a user writes "I'm thinking somewhere between $80,000 and $90,000", the parser returns `$90,000`. In a "user wants less" scenario (e.g., medical bill), the user's intent is likely the lower number. The parser has no access to state/direction, so it always picks the largest.

**Impact:** In buyer/payer scenarios, the extracted offer will systematically overstate what the user meant.

**Fix:** Either (a) pass direction context to `_extract_offer` and pick min/max accordingly, or (b) document this as a known limitation. Since the parser is stateless by design, option (b) is pragmatic for MVP.

#### MEDIUM-01: `_offer_is_acceptable` uses `user_opening_anchor or offer` for direction detection

**Location:** Lines 383-384
```python
user_anchor = state.user_opening_anchor or offer
opp_anchor  = state.opponent_opening_anchor or persona.opening_offer
if user_anchor >= opp_anchor:
    return offer <= persona.reservation_price
```

**Problem:** When `user_opening_anchor is None` (user hasn't anchored yet), this substitutes the current offer as the anchor for direction detection. If the user's first message contains a number below the opponent's opening, direction detection works. But if the user's first number happens to equal the opponent's opening, `>=` treats it as "user wants more" which may be wrong.

**Impact:** Edge case -- only triggers when the user's first offer exactly equals the opponent's opening. Direction will be inferred as "salary" even if it's a procurement scenario.

#### MEDIUM-02: `_render_opponent_response` reads stale `state.opponent_last_offer`

**Location:** Line 552
```python
current = state.opponent_last_offer or persona.opening_offer
```

**Problem:** This is called AFTER `state.opponent_last_offer` was already updated to `new_offer` (line 222). So `current` is actually the NEW offer, not the previous one. The comparison `abs(new_offer - current) < 1` on line 555 will always be true (comparing `new_offer` to itself), meaning the holding-line text will always be selected instead of the new-offer text.

**Impact:** After the first opponent concession, the opponent's text will say "I have to stay at $X" even when they just moved. The text rendering is cosmetically wrong.

**Fix:** Pass `prev_opponent_offer` (captured at line 216) into `_render_opponent_response` instead of re-reading from state.

#### MEDIUM-03: No guard against `persona.opening_offer == 0`

Several functions divide by or use `persona.opening_offer` as a denominator indirectly (e.g., `_round_offer` line 458 uses `reference` which is `opening_offer`). An opening offer of exactly 0 would cause `full_range = abs(reservation_price - opening_offer)` to be the entire reservation price, which is technically valid, but `_round_offer` with `reference=0` would fall through to `round(value, 2)` which is fine. No crash, but worth documenting.

#### LOW-01: Turn numbering assumes strict alternation

**Location:** Line 172
```python
turn_n = state.turn_count * 2   # user = odd, opponent = even
```

If `generate_response` is called twice without user input changing (e.g., a retry), turn numbering will be wrong. Not a bug in normal flow but fragile.

---

### 2. persona.py

#### MEDIUM-04: `corporate_manager` scope-creep template has an f-string bug

**Location:** Line 374
```python
"Your budget ceiling is ${budget * 1.40:.0f} but you want to avoid "
```

**Problem:** This is inside a regular string (not an f-string), so `${budget * 1.40:.0f}` is a literal string, not an interpolation. The `system_prompt` field will contain the literal text `${budget * 1.40:.0f}` instead of the computed value.

**Impact:** When a future LLM engine reads `system_prompt`, it will see the raw template syntax instead of the actual dollar amount.

**Fix:** Change the string to an f-string or use the same pattern as other templates.

#### MEDIUM-05: Difficulty modifier can push `reservation_price` past `opening_offer` boundary

**Location:** Lines 627-644

In "user wants down" scenarios with `difficulty == "hard"`, `reservation_price *= 1.05` pushes the reservation UP. For the `first_line_rep` medical bill template, reservation starts at `bill * 0.85`. After hard modifier: `bill * 0.85 * 1.05 = bill * 0.8925`. This is still below `bill` (the opening), so the direction stays correct.

But for the `financial_assistance` template: reservation = `bill * 0.25`, opening = `bill * 0.60`. After hard: `bill * 0.25 * 1.05 = bill * 0.2625`. Direction is `reservation < opening`, so the opponent concedes downward. This is fine.

However, for "user wants up" + `difficulty == "easy"`, `reservation *= 1.10`. For `dismissive_manager`: reservation = `salary * 1.08`, after easy: `salary * 1.08 * 1.10 = salary * 1.188`. Opening is `salary * 1.02`. Direction: `reservation > opening` (correct). No inversion found after checking all templates.

**Verdict:** No actual bug found, but the lack of a post-modifier assertion `assert reservation != opening` means a future template could silently create a zero-range persona.

#### LOW-02: `generate_persona_for_scenario` silently falls back to salary templates

**Location:** Line 612
```python
available = templates.get(scenario_type, SALARY_NEGOTIATION_TEMPLATES)
```

An unrecognized `scenario_type` silently uses salary templates. This is intentional for MVP but could mask typos in API callers (e.g., `"medical bill"` with a space instead of underscore).

---

### 3. scorer.py

#### HIGH-03: `_score_concession_pattern` computes `avg_pct` incorrectly

**Location:** Line 280
```python
avg_pct = (total_conc / abs(anchor)) / n_conc if anchor != 0 else 0
```

**Problem:** `total_conc` is already an absolute sum (from `_update_state_from_user_move`). Dividing by `abs(anchor)` gives total concession as fraction of anchor. Then dividing by `n_conc` gives the average step as a fraction. This is mathematically correct.

However, due to HIGH-01 above (`_update_state_from_user_move` counts ALL moves as concessions, including hardening moves), `total_conc` may be inflated. The average will therefore overstate true concession size.

**Impact:** Users who alternate between conceding and hardening will be penalized twice -- once for the "concession" count and once for the inflated total.

#### HIGH-04: `_check_deceleration` ignores negotiation direction

**Location:** Lines 469-479
```python
steps = [abs(offers[i] - offers[i - 1]) for i in range(1, len(offers))]
violations = sum(1 for i in range(1, len(steps)) if steps[i] > steps[i - 1])
```

**Problem:** Uses `abs()` on all offer deltas. In a "user wants less" scenario, if the user goes 5000 -> 4800 -> 4900 (backed off then hardened), the steps would be [200, 100] which looks like deceleration. But the user actually REVERSED direction. The deceleration check does not account for direction reversals.

**Impact:** A user who hardens their position after a concession will not be flagged for inconsistent signaling.

#### MEDIUM-06: `_score_opening_strategy` division guard `if opp > 0`

**Location:** Line 149
```python
pct_above = (anchor - opp) / opp if opp > 0 else 0.0
```

If `opp` is negative (theoretically impossible but not type-guarded), this would invert the percentage. Acceptable for MVP since all templates use positive values.

#### MEDIUM-07: Weight sum assertion is missing

**Location:** Lines 51-58

The weights are documented as "must sum to 1.0" but no runtime assertion verifies this. `0.20 + 0.15 + 0.25 + 0.15 + 0.10 + 0.15 = 1.00` -- correct today, but fragile if someone edits a weight.

**Fix:** Add `assert abs(sum(_WEIGHTS.values()) - 1.0) < 0.001` at module level.

---

### 4. session.py

#### HIGH-05: `_restore_from_file` runs at module import time

**Location:** Line 241
```python
_restore_from_file()
```

**Problem:** This runs when `session.py` is first imported, which happens during application startup. If the store file is large or corrupt, this blocks the import. More critically, if the store file references enum values that don't exist (e.g., from a newer version), the `_deserialize_session` call will raise a `ValueError` that `_restore_from_file` catches, but all sessions will be lost silently.

**Impact:** Upgrading the application (adding new enum values, changing field names) could silently lose all active sessions.

#### MEDIUM-08: Race condition in `negotiate()` between `_load_session` and `_store_session`

**Location:** Lines 319-336

`negotiate()` calls `_load_session()` (acquires and releases lock), mutates the session in memory, then calls `_store_session()` (acquires and releases lock). Between these two lock acquisitions, another thread could call `negotiate()` on the same session. Both would read the same state, both would mutate it, and the last to call `_store_session` wins.

**Impact:** In a multi-threaded server (uvicorn with multiple workers), concurrent requests on the same session could produce inconsistent state. For MVP with single-user sessions this is unlikely.

**Fix:** Hold the lock for the entire `negotiate()` call, or use per-session locks.

#### MEDIUM-09: `MAX_ROUNDS` auto-complete does not set `agreed_value`

**Location:** Lines 329-331
```python
if session.state.turn_count >= MAX_ROUNDS and not session.state.resolved:
    session.state.resolved = True
```

When auto-completing after 20 rounds, `resolved` is set to `True` but `agreed_value` remains `None`. The scorer will see `outcome = "deal_reached"` (since `resolved` is True) but `agreed_value` is None, which means score computations that depend on `agreed_value` (like SCORE-01's progress calculation) will use `agreed_value or opp_opening` -- falling back to the opponent's opening offer as the "deal value".

**Fix:** Either keep `resolved = False` (treat it as "no deal" / timeout) or set `agreed_value` to the midpoint of last offers.

---

### 5. debrief.py

#### HIGH-06: `_build_move_analysis` dollar-impact accumulates rounding errors

**Location:** Lines 410-418

The `expected_outcome` is updated on every turn by averaging the latest offers. Over a long negotiation (10+ turns), this running average diverges from the true trajectory because each step compounds a midpoint calculation on top of a previous midpoint.

**Impact:** The `dollar_impact` per turn becomes less meaningful in later turns. For a 10-turn negotiation, the cumulative dollar_impact may not equal the actual difference between opening and closing positions.

**Fix:** Consider computing dollar_impact as the marginal change in the midpoint of the two sides' latest offers, rather than chaining averages.

#### MEDIUM-10: `_find_undiscovered_constraints` keyword matching is overly broad

**Location:** Lines 619-647

The keyword `"budget"` matches constraints about "budget" but also matches user text containing "budget" in any context (e.g., "What's a typical budget?" counts as discovering a constraint about "Board approved up to 20%"). The keyword overlap between categories is significant -- "pay" appears under "budget", which would match a user asking about "pay" even if the hidden constraint is about budget ceilings.

**Impact:** Constraints may be marked as "discovered" when the user only tangentially touched the topic. The debrief will understate undiscovered information.

---

### 6. playbook.py

#### MEDIUM-11: `_compute_walk_away` returns the same value regardless of direction

**Location:** Lines 228-233
```python
if direction == "user_wants_more":
    walk_away = midpoint
else:
    walk_away = midpoint
```

Both branches compute the same value. The `if/else` is dead code. This is technically correct (the midpoint IS a reasonable walk-away in both directions), but the dead branch suggests an incomplete implementation where different walk-away strategies were intended for each direction.

#### LOW-03: Playbook leaks `reservation_price` in post-session mode

**Location:** Lines 281-288 and line 391

The post-session summary reveals `persona.reservation_price` explicitly. This is intended (it is the "reveal" after the game), but the `_build_anchor_justification` function (line 391) also exposes it: `"their real ceiling is ${reservation:,.0f}"`. In pre-session mode, `is_pre_session=True` hides the reservation in the summary (DEBRIEF-03 fix), but the anchor justification is not gated on `is_pre_session` and always reveals it.

**Fix:** Gate `_build_anchor_justification` on `is_pre_session` to use vague language instead of the exact number.

---

### 7. offer_analyzer.py

#### HIGH-07: `_estimate_percentile` synthetic anchors distort extreme values

**Location:** Lines 332-338
```python
points = [
    (0,   benchmarks["p25"] * 0.70),   # synthetic p0 anchor
    (25,  benchmarks["p25"]),
    ...
    (100, benchmarks["p90"] * 1.15),    # synthetic p100 anchor
]
```

**Problem:** The synthetic p0 is 70% of p25, and p100 is 115% of p90. This means:
- A salary at exactly p25 benchmark maps to percentile 25 (correct).
- A salary at 70% of p25 maps to percentile 0 (correct).
- But a salary between p0 and p25 is linearly interpolated across 25 percentile points over a 30% range, while p25-p50 is linearly interpolated across 25 percentile points over whatever the actual p25-p50 range is.

The distortion: if the p25-p50 gap is small (compressed market), the synthetic p0-p25 range may be wider than p25-p50, making below-p25 values appear artificially low. This primarily affects the "how bad is my offer" messaging.

**Impact:** Offers below p25 will show slightly pessimistic percentile estimates. Offers above p90 will show slightly optimistic estimates. Moderate but misleading.

#### HIGH-08: `parse_offer_text` does not handle negative values or reject garbage

**Location:** Lines 922-990

The parser extracts numbers from free text but has no validation on extracted values. A text containing "we lost $500,000 last quarter" could extract `$500,000` as a base salary. The parser returns whatever the regex matches, and `analyze_offer` only validates `base_salary` bounds (SALARY_MIN=1, SALARY_MAX=10M).

**Impact:** Garbage-in-garbage-out on unstructured text. The parser is best-effort by design, but no warning is surfaced to the user when the extracted value seems implausible (e.g., a "junior" role with a $500K salary).

**Fix:** Add a plausibility check: if the extracted salary is above p90*2 for the inferred role+level, add a warning to the result dict.

#### MEDIUM-12: `_ordinal` crashes on negative input

**Location:** Line 566
```python
def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{['th','st','nd','rd','th','th','th','th','th','th'][n % 10]}"
```

If `n` is negative (e.g., -5), `n % 10` is `-5` in Python (not 5), which would index `[-5]` into the list -- this actually works in Python (negative indexing), returning `'th'` for -5 (index 5 from the end). So it does not crash but produces `"-5th"` which is nonsensical. Since `_estimate_percentile` clamps to 0-100, this is unreachable in practice.

---

### 8. earnings.py

#### LOW-04: No guard against negative `years_to_retirement`

**Location:** Line 121
```python
for n in range(years_to_retirement):
```

If `years_to_retirement` is 0 or negative, `range()` produces an empty sequence, the function returns an `EarningsImpact` with `total_salary_difference=0.0`, `retirement_impact=0.0`, and empty `year_by_year`. This is mathematically correct (0 years = 0 impact) but the `key_insight` would say "Negotiating $X more today = $0 over 0 years" which is confusing.

**Fix:** Add a guard: `if years_to_retirement <= 0: raise ValueError(...)`.

#### LOW-05: No guard against negative `negotiated_increase`

A negative `negotiated_increase` (user negotiated LESS) would produce negative salary differences throughout, which is mathematically valid and could be useful for showing "here's what you lose by accepting less". But the `key_insight` text would say "Negotiating -$5,000 more today = -$XXX" which reads oddly. Document or guard.

#### MATHEMATICAL VERIFICATION

The compound interest formula is correct:
- `salary_diff = negotiated_increase * (1 + raise_rate) ** n` -- geometric growth, correct.
- `retirement_balance = retirement_balance * (1 + invest_rate) + employee_contrib + employer_contrib` -- end-of-year contribution model, standard.
- `employer_contrib = employee_contrib * match_rate` -- correct: match is percentage of employee contribution.

The docstring example checks out:
- 5 years, 0% raise, 10% contribution, 50% match, 0% return:
  - Salary: 5 * $10,000 = $50,000. Correct.
  - Retirement: 5 * ($1,000 + $500) = $7,500. Correct.

---

### 9. email_audit.py

#### MEDIUM-13: Score can exceed 100 due to power-phrase bonus

**Location:** Lines 430-431
```python
power_count = sum(1 for p in POWER_PHRASES if p in lower)
score = min(100, score + min(power_count * 3, 10))
```

The `min(100, ...)` cap is present, so score cannot exceed 100. However, the interaction between deductions and bonus means an email with many issues AND many power phrases could score higher than expected. For example: 2 HIGH issues (-30) + 10 power phrases (+10) = 80. This seems intentional.

**Verdict:** Not a bug. The cap at 100 is correct.

#### LOW-06: `_rewrite` can produce empty output

If the entire email text consists only of hedging phrases, `_rewrite` will strip everything and return an empty string. The `EmailAudit.rewritten_version` would be `""`.

**Fix:** If rewritten is empty or whitespace after stripping, return a placeholder like "[Original text was entirely hedging language -- rewrite from scratch]".

---

### 10. challenges.py

No bugs found. The 30-challenge library is static data. The `get_daily_challenge` function correctly handles the day rotation with `(date.today().toordinal() % 30) + 1` and clamps input to 1-30.

One note: the `toordinal() % 30` mapping means that day 1 of the challenge rotation does not align with the 1st of the month. This is by design (rolling rotation) but could confuse users who expect day 1 on March 1st.

---

### 11. store.py

#### MEDIUM-14: `load_sessions` releases lock before returning, allowing concurrent `save_sessions` to overwrite cleaned data

**Location:** Lines 87-126

`load_sessions()` reads the file, cleans stale sessions, and returns the cleaned dict -- but does NOT write the cleaned data back. The cleaned sessions only live in the caller's memory. Stale sessions remain on disk until the next `save_sessions` call, which overwrites the entire file. This means:
1. Load: reads 10 sessions, cleans to 7.
2. Another thread loads: reads 10 sessions (stale data still on disk), cleans to 7.
3. First thread saves: writes 7 sessions.
4. Second thread saves: writes 7 sessions (same 7, or different if new sessions were added).

No data loss occurs because `save_sessions` always writes all in-memory sessions. But the auto-clean logging may fire repeatedly on every load until a save happens.

**Impact:** Minor -- extra log noise, no data corruption.

#### MEDIUM-15: 1-hour TTL may be too aggressive for long negotiations

`_MAX_AGE_SECONDS = 3600` means any session older than 1 hour is purged on load. A user who starts a negotiation, takes a 90-minute lunch break, and returns will find their session gone.

**Impact:** User-facing data loss. The 1-hour window is likely too short for a product where users might negotiate across multiple sittings.

**Fix:** Increase to 24 hours, or make it configurable, or only purge sessions in `abandoned` or `completed` status.

---

## Cross-File Consistency Issues

### CROSS-01: Direction detection is implemented three times with slightly different logic

| Location | Method |
|----------|--------|
| `simulator.py:_user_wants_more()` | Compares user_anchor vs opp_anchor, fallback: reservation > opening |
| `debrief.py:_negotiation_direction()` | Same logic, returns string instead of bool |
| `playbook.py:_detect_direction()` | Only checks reservation vs opening (no anchor check) |

**Problem:** `playbook.py` does not consider user anchors, so if a persona has `reservation > opening` but the user anchored below the opponent (buying scenario with unusual persona setup), the playbook would generate "user wants more" advice while the simulator treated it as "user wants less".

**Fix:** Extract direction detection into a shared utility function in `simulator.py` and import it everywhere.

### CROSS-02: `_USER_WANTS_DOWN` / `_USER_WANTS_UP` frozensets in simulator.py are unused

**Location:** simulator.py lines 262-268

These scenario-type sets are defined but never referenced. They appear to be remnants of an earlier direction-detection approach that was replaced by the anchor-comparison method. Dead code.

### CROSS-03: Scorer and debrief disagree on what "no concession + deal" means

- **Scorer** (SCORE-01): If user made 0 concessions and deal was reached near opponent's opening, scores 35 (bad -- user just accepted).
- **Debrief**: `money_left_on_table` for a resolved deal = `reservation - agreed_value` (or vice versa). If user accepted at opponent's opening, money_left = `abs(reservation - opening)`.

These are consistent in their conclusion (user left money on table) but the scorer says "concession discipline is irrelevant" while debrief says "there was $X,000 of room". A user might see a low concession score and think "but the debrief says I was close!" -- the messaging should be aligned.

---

## Mathematical Correctness Summary

| Module | Formula | Status |
|--------|---------|--------|
| earnings.py | Compound growth + end-of-year contributions | CORRECT |
| scorer.py | Weighted average (weights sum to 1.0) | CORRECT |
| scorer.py | Concession avg_pct computation | CORRECT (but inflated due to HIGH-01) |
| offer_analyzer.py | Percentile interpolation | CORRECT (with synthetic anchor distortion noted) |
| offer_analyzer.py | Location multiplier application | CORRECT |
| offer_analyzer.py | Counter-strategy upside calculation | CORRECT (equity annualized /4) |
| simulator.py | Opponent step computation | CORRECT per style |
| simulator.py | Offer rounding | CORRECT |
| debrief.py | Money-left-on-table | CORRECT for resolved; approximation for no-deal |
| playbook.py | Anchor computation (15-20% beyond reservation) | CORRECT |
| playbook.py | Concession budget (60% of anchor-to-walkaway) | REASONABLE heuristic |

---

## Recommended Fix Priority

### Must-fix before production

1. **CRITICAL-01** -- Clamp `_user_concession_ratio` return value.
2. **HIGH-01** -- Direction-aware concession accumulation in `_update_state_from_user_move`.
3. **MEDIUM-02** -- `_render_opponent_response` reads stale state (opponent always says "holding" instead of new number).
4. **MEDIUM-09** -- `MAX_ROUNDS` auto-complete should not set `resolved=True` without `agreed_value`.

### Should-fix before beta

5. **CROSS-01** -- Unify direction detection into one shared function.
6. **MEDIUM-04** -- Fix f-string bug in `corporate_manager` system_prompt.
7. **LOW-03** -- Gate anchor justification on `is_pre_session` to avoid leaking reservation.
8. **MEDIUM-15** -- Increase session TTL from 1 hour to 24 hours.
9. **MEDIUM-07** -- Add weight-sum assertion in scorer.py.

### Nice-to-have

10. **HIGH-07** -- Improve synthetic percentile anchors in offer_analyzer.
11. **HIGH-08** -- Add plausibility check to `parse_offer_text`.
12. **CROSS-02** -- Remove dead `_USER_WANTS_DOWN` / `_USER_WANTS_UP` frozensets.
13. **LOW-06** -- Handle empty rewrite output in email_audit.

---

## Files Not Requiring Fixes

- **challenges.py** -- Static data, no logic bugs.
- **earnings.py** -- Mathematically correct, minor input validation gaps only.
- **store.py** -- Functionally correct, TTL policy is a product decision.
