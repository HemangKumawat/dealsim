# Engine Fixes Applied — Direction Awareness Bug

Date: 2026-03-19
Scope: BUG-01, BUG-02, BUG-05, SCORE-01, PERSONA-01, PERSONA-04, DEBRIEF-01, DEBRIEF-02, DEBRIEF-03, PLAY-01
Test status: 303/303 passing

---

## simulator.py

### BUG-01 (HIGH): Direction-aware concession detection
Added `_user_wants_more()` helper that determines negotiation direction from anchor comparison or persona structure (reservation vs opening fallback). `_classify_user_move` now uses this to detect concessions correctly in both directions:
- User wants UP (salary): concession = offer drops below last offer
- User wants DOWN (medical bill, car, rent, vendor): concession = offer rises above last offer

Also added `_USER_WANTS_DOWN` and `_USER_WANTS_UP` frozensets for scenario-type-based direction detection.

### BUG-02 (MEDIUM): concession_from recorded after state mutation
Captured `prev_opponent_offer` before mutating `state.opponent_last_offer`. The Turn constructor now uses `prev_opponent_offer` for `concession_from`, so concession deltas are correct.

### BUG-05 (LOW): "sounds good" triggers false acceptance
Moved offer extraction before acceptance signal check. Acceptance signals are now only matched when NO monetary offer is present in the same message. "Sounds good, but I'd like $95k" now correctly parses as an anchor/counter-offer.

### PERSONA-04 (MEDIUM): COMPROMISING ignores pressure_factor
Added `* pressure_factor` to the COMPROMISING step calculation, matching every other style.

---

## persona.py

### PERSONA-01 (HIGH): Difficulty modifier backwards for buyer scenarios
The difficulty adjustment now branches on scenario direction:
- **User wants DOWN** (medical_bill, car_buying, rent, vendor, scope_creep): hard pushes reservation UP (opponent less generous), easy pushes DOWN
- **User wants UP** (salary, raise, freelance, counter_offer, budget_request): hard pushes reservation DOWN (less room), easy pushes UP

Previously, `*= 0.95` for hard made buyer scenarios easier (lower floor = more generous opponent).

---

## scorer.py

### SCORE-01 (HIGH): Zero-concession deal gameable to 100
When no concessions were made but a deal was reached, the score is now computed based on where the deal landed relative to the opponent's full range:
- Deal near reservation (progress >= 0.7): score 95 (genuinely held firm)
- Deal in midrange (progress >= 0.4): score 70
- Deal near opening (progress < 0.4): score 35 (just accepted first offer)

Previously, accepting the first offer scored 100 on Concession Pattern.

---

## debrief.py

### DEBRIEF-01 (MEDIUM): No-deal money left uses wrong baseline
For no-deal scenarios, `money_left_on_table` now measures distance from user's last offer to reservation (how close they were to a deal). Falls back to full range only if the user never made an offer.

### DEBRIEF-02 (MEDIUM): Dollar impact uses terminal state
`_build_move_analysis` now tracks `running_opp_offer` and `running_user_offer` variables that update as each turn is processed, instead of reading from `state.opponent_last_offer` / `state.user_last_offer` (which reflect terminal state).

---

## playbook.py

### DEBRIEF-03 (LOW): Pre-session playbook leaks reservation price
Added `is_pre_session` parameter to `generate_playbook` and `_build_scenario_summary`. When True, the scenario summary shows "walk-away point is likely 10-20% beyond their opening" instead of the exact reservation price.

### PLAY-01 (partial): Scenario type coverage in summary
`_build_scenario_summary` now covers all 10 scenario types (salary, freelance, rent, medical_bill, car_buying, scope_creep, raise, vendor, counter_offer, budget_request) instead of only 4.

---

## Test updates

- `test_debrief.py`: Updated `test_no_deal_money_left` to expect new DEBRIEF-01 behavior (85K not 35K). Added `test_no_deal_no_user_offer_money_left` to cover the fallback path.
- `test_scorer.py`: Replaced `test_no_concessions_with_deal_scores_high` (which asserted score=100 for any zero-concession deal) with two tests: `test_no_concessions_with_deal_near_reservation_scores_high` (score >= 90) and `test_no_concessions_accept_first_offer_scores_low` (score <= 40).
- `test_persona.py`: Fixed `test_hard_tightens_reservation` and `test_easy_increases_reservation` to seed `random` before each call, preventing template-selection non-determinism.

---

## Remaining from ENGINE_REVIEW_W1 (not addressed in this pass)

- BUG-03: AVOIDING style stuck negotiations (needs consecutive-hold tracking)
- BUG-04: Max-value extraction misparses ranges (needs direction-aware first-vs-max)
- SCORE-02: Information gathering ratio rewards short negotiations
- SCORE-03: BATNA dimension capped at 80
- SCORE-04: Value Creation gameable via keyword spam
- PERSONA-02: AVOIDING personas frustrating (needs break-point mechanic)
- PERSONA-03: ACCOMMODATING too easy (needs relationship threshold)
- PLAY-01 (full): Opening lines still salary-centric for non-salary scenarios
- PLAY-02: Concession ladder ignores non-monetary trades
- PLAY-03: Literal [placeholder] brackets in objection responses
- PLAY-04: Key questions salary-biased
