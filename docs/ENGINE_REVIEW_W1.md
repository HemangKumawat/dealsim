# DealSim Engine Review -- Week 1

Reviewer: Game Design Engineer
Date: 2026-03-19
Files reviewed: simulator.py, scorer.py, persona.py, session.py, debrief.py, playbook.py

---

## 1. Logic Bugs (simulator.py)

### BUG-01: Concession direction detection is inverted for several scenario types
**Severity: HIGH**
**Location:** `simulator.py` line 301, `_classify_user_move`

The concession classifier checks `offer < state.user_last_offer` to detect a concession. This works for salary negotiations (user wants more, so moving down = conceding), but **breaks for procurement, medical bills, and vendor contracts** where the user wants to pay less. In those scenarios the user conceding means offering MORE, not less. The classifier would label a legitimate user concession as a COUNTER_OFFER, and a counter-offer as a CONCESSION.

**Impact:** In roughly half of the 10 scenario types, user concession counts, concession-pattern scoring, and debrief dollar-impact calculations are wrong.

**Fix:** Use the same direction-detection logic that `_offer_is_acceptable` already uses. Compare user_anchor vs opponent_anchor to determine whether conceding means going up or down, then flip the comparison accordingly.

---

### BUG-02: Opponent concession_from is recorded AFTER the offer is overwritten
**Severity: MEDIUM**
**Location:** `simulator.py` lines 215-237

At line 221, `state.opponent_last_offer` is updated to `new_offer`. Then at line 234, the Turn is constructed with `concession_from = state.opponent_last_offer`. Because the state was already mutated, `concession_from` always equals the NEW offer, not the previous one. Every opponent concession Turn reports zero delta.

**Fix:** Capture `prev_offer = state.opponent_last_offer` before the mutation block, and use `prev_offer` in the Turn constructor at line 234.

---

### BUG-03: AVOIDING style can produce stuck negotiations
**Severity: MEDIUM**
**Location:** `simulator.py` line 393-394

The AVOIDING strategy returns the current offer unchanged with 40% probability (`return current, MoveType.COUNTER_OFFER`). If the user also doesn't move (asks questions or shares info), the simulator enters a loop where neither side makes progress. With MAX_ROUNDS = 20, this can produce 10+ turns of zero movement, which feels broken rather than "avoiding."

**Fix:** Track consecutive no-movement turns. After 3 consecutive holds, force a micro-concession (e.g., 2-3% of remaining room) so the negotiation eventually converges.

---

### BUG-04: _extract_offer takes the MAX value, which misparses ranges
**Severity: LOW**
**Location:** `simulator.py` line 277

If the user says "I'm thinking between $80,000 and $90,000", the parser extracts $90,000 (the max). For a salary negotiation this is actually the user's weaker number. For procurement it's the stronger one. The correct number to extract depends on direction.

**Fix:** When direction is determinable from state (user_anchor vs opponent_anchor), take the value that is more favorable to the user. Alternatively, take the FIRST number mentioned (conversational anchor) rather than the max.

---

### BUG-05: "sounds good" triggers ACCEPTANCE even in non-agreement contexts
**Severity: LOW**
**Location:** `simulator.py` line 258

A user saying "Sounds good, but I'd like $95k" gets classified as ACCEPTANCE because "sounds good" is in the acceptance signal list, and acceptance is checked before offer extraction. The negotiation resolves prematurely at the opponent's last offer, ignoring the user's counter.

**Fix:** Check for acceptance signals only when no monetary offer is present in the same message. If an offer is detected, the monetary signal should take priority.

---

## 2. Scoring Fairness (scorer.py)

### SCORE-01: Zero-concession deal scores 100 on Concession Pattern -- gameable
**Severity: HIGH**
**Location:** `scorer.py` lines 243-253

If the user accepts the opponent's first offer without any concessions, Concession Pattern scores 100 ("exceptional discipline"). But accepting a first offer is almost always terrible negotiating. A user can game a perfect concession score by simply saying "deal" on turn 1.

**Fix:** If `state.resolved` and `n_conc == 0` but the agreed value equals or is near the opponent's opening offer, score LOW (30-40) rather than 100. Only score 100 if the deal closed near the opponent's reservation price without user concessions.

---

### SCORE-02: Information Gathering ratio rewards short negotiations
**Severity: MEDIUM**
**Location:** `scorer.py` lines 198-223

The score uses `q_count / turns` as the ratio. A user who asks 1 question in a 2-turn negotiation gets ratio = 0.5 and scores 90. A user who asks 4 questions in a 12-turn negotiation gets ratio = 0.33 and scores only 72. The second user gathered far more information.

**Fix:** Score on absolute question count with a turn-adjusted bonus, not a pure ratio. Example: base score from question count (0 = 15, 1 = 40, 2 = 60, 3+ = 75), then add +15 if ratio > 0.3.

---

### SCORE-03: BATNA scoring penalizes persistence with no upside path
**Severity: LOW**
**Location:** `scorer.py` lines 314-332

1 BATNA signal = 80, 2+ signals = 65. There is no way to score above 80 on this dimension. The max weighted contribution is 0.15 * 80 = 12 points. This ceiling means even perfect BATNA play leaves 3 points permanently unattainable.

**Fix:** 1 well-timed signal = 90, 2 signals = 75, 3+ = 55, 0 = 20. This preserves the diminishing-returns insight while making a 90 achievable.

---

### SCORE-04: Value Creation keyword matching is trivially gameable
**Severity: MEDIUM**
**Location:** `scorer.py` lines 406-433

The user just needs to mention 3 words from the list ("bonus", "equity", "remote", etc.) to score 88. They could say "I don't care about bonus, equity, or remote" and still get the maximum score. There is no check for whether the user actually explored these topics substantively.

**Fix:** Require that package terms appear in QUESTION or INFO_SHARE classified turns only, not in arbitrary text. This at least ensures the user was probing, not just name-dropping.

---

## 3. Persona Balance (persona.py)

### PERSONA-01: Difficulty modifier is backwards for several scenario types
**Severity: HIGH**
**Location:** `persona.py` lines 617-624

The difficulty adjustment on line 620 does `reservation_price *= 0.95` for "hard" and `*= 1.10` for "easy". This works for salary scenarios where a higher reservation means more room. But for medical bills, car buying, and vendor contracts, the reservation price is BELOW the opening -- so multiplying by 0.95 actually makes the opponent MORE generous (lower floor), which is the opposite of harder.

**Fix:** Apply the modifier based on the direction. For "user_wants_less" scenarios, hard should push reservation UP (tighter) and easy should push it DOWN (more generous).

---

### PERSONA-02: AVOIDING personas (medical_bill first_line_rep, corporate_manager) are frustrating, not engaging
**Severity: MEDIUM**

Combined with BUG-03, AVOIDING opponents deflect 40% of the time and reveal almost nothing (transparency 0.1-0.2). The negotiation stalls. The user learns little and the experience feels like talking to a wall rather than practicing negotiation.

**Fix:** For AVOIDING personas, give them a "break point" -- after 3 deflections, they reveal one hidden constraint as a scripted event. This teaches the user that persistence works against avoiders while keeping engagement high.

---

### PERSONA-03: Accommodating opponents make scenarios too easy
**Severity: LOW**

Patricia Owens (rent, ACCOMMODATING, emotional_reactivity 0.7) + the accommodating step formula (`step = abs(midpoint - current) * 0.6 * pressure_factor`) converges to the user's number within 3-4 turns with almost any pressure. There is no tension.

**Fix:** For ACCOMMODATING personas, add a "relationship threshold" -- they concede fast on price but expect the user to acknowledge the relationship or make a non-monetary gesture. Without it, they still concede but slower. This teaches integrative negotiation.

---

### PERSONA-04: COMPROMISING pressure_factor is ignored
**Severity: MEDIUM**
**Location:** `simulator.py` line 397

The COMPROMISING step calculation is `abs(user_offer - current) * 0.5` with no `pressure_factor` multiplier, unlike every other style. A HIGH-pressure COMPROMISING opponent behaves identically to a LOW-pressure one.

**Fix:** Apply pressure_factor: `abs(user_offer - current) * 0.5 * pressure_factor`.

---

## 4. Debrief Accuracy (debrief.py)

### DEBRIEF-01: "Money left on table" is correct for deal scenarios but misleading for no-deal
**Severity: MEDIUM**
**Location:** `debrief.py` lines 107-109

When no deal is reached, the calculation is `abs(reservation_price - opening_offer)`. This reports the opponent's FULL negotiating range as "money left on table." But the user may have walked away deliberately (good BATNA), and the "money left" should be measured from the user's last offer to the reservation, not from the opening.

**Fix:** For no-deal scenarios, use `abs(reservation_price - user_last_offer)` if the user made an offer, or `abs(reservation_price - opening_offer)` only if the user never offered a number. This properly reflects how close the user was to a deal.

---

### DEBRIEF-02: Dollar impact calculation uses stale state references
**Severity: MEDIUM**
**Location:** `debrief.py` lines 391-396

The `_build_move_analysis` function references `state.opponent_last_offer` and `state.user_last_offer` inside the loop, but these are the FINAL state values, not the values at the time of each turn. Every turn's dollar impact is computed against the final positions rather than the positions at that moment.

**Fix:** Track running `opp_last` and `user_last` variables inside the loop, updating them as each turn is processed, instead of reading from the terminal state.

---

### DEBRIEF-03: Optimal outcome reveals reservation price in the pre-play playbook
**Severity: LOW but design-relevant**
**Location:** `playbook.py` lines 260-264

The `_build_scenario_summary` includes the reservation price in plain text: "their actual walk-away point is $X." If the playbook is generated before the negotiation (which the docstring says is supported), this gives away the answer. The simulation becomes a math exercise rather than a negotiation.

**Fix:** In pre-session playbooks, use a range estimate: "their walk-away is likely 10-20% beyond their opening." Reveal the exact number only in the post-session debrief.

---

## 5. Playbook Quality (playbook.py)

### PLAY-01: Opening lines are salary-centric regardless of scenario type
**Severity: MEDIUM**

All opening lines reference "what I bring to the table" and "the value I'll deliver" -- phrasing suited for salary and freelance, but wrong for rent negotiation ("I've been a reliable tenant for 3 years"), medical bills ("I received this bill and I'd like to discuss options"), car buying ("I've researched the market value of this vehicle"), or budget requests ("Here's the ROI case for this investment").

**Fix:** Branch opening line generation by scenario type (available from persona.role or the scenario dict). At minimum, detect the 4 major framing categories: earning (salary/freelance/raise/counter-offer), spending (car/vendor/rent), reducing (medical bill), and requesting (budget/scope-creep).

---

### PLAY-02: Concession ladder is scenario-agnostic
**Severity: LOW**

The ladder always phrases concessions as dollar movements from the anchor. For scenarios like scope creep, rent, and medical bills, concessions are often non-monetary (longer lease, payment plan, phased delivery). The ladder should include at least one non-monetary concession step drawn from the persona's hidden_constraints.

**Fix:** For each scenario type, define 1-2 domain-specific concession options (e.g., for rent: "Offer to sign a 2-year lease" which matches Patricia Owens' hidden constraint). Insert these as step 1 or 2 in the ladder, as they cost the user little and are high-value to the opponent.

---

### PLAY-03: Objection responses contain placeholder brackets
**Severity: LOW**
**Location:** `playbook.py` line 482, line 506

Two objection responses include literal `[specific value]` and `[specific item]` brackets that will display to the user as-is. These should be filled from the persona/scenario context.

**Fix:** Replace `[specific value]` with a concrete example drawn from the persona's hidden_constraints or scenario type. For the fallback case, use a generic but real example ("my track record on similar projects" rather than "[specific value]").

---

### PLAY-04: Key questions are redundant for low-constraint personas
**Severity: LOW**
**Location:** `playbook.py` lines 634-695

If `persona.hidden_constraints` is empty (possible if someone passes a custom persona), the question list maxes out at 3 generic questions with no constraint-specific probes. The questions are also salary-biased ("compensation package beyond base salary") even for non-salary scenarios.

**Fix:** Add scenario-type-specific question pools (rent: "What's the vacancy rate in this building?", medical: "Do you have a prompt-pay discount policy?") as fallbacks when constraint-derived questions are unavailable.

---

## Summary Table

| ID | Category | Severity | Component | One-line |
|---|---|---|---|---|
| BUG-01 | Logic | HIGH | simulator | Concession direction inverted for non-salary scenarios |
| BUG-02 | Logic | MEDIUM | simulator | concession_from recorded after state mutation |
| BUG-03 | Logic | MEDIUM | simulator | AVOIDING style causes stuck negotiations |
| BUG-04 | Logic | LOW | simulator | Max-value extraction misparses offer ranges |
| BUG-05 | Logic | LOW | simulator | "sounds good" triggers false acceptance |
| SCORE-01 | Scoring | HIGH | scorer | Zero-concession deal gameable to 100 |
| SCORE-02 | Scoring | MEDIUM | scorer | Question ratio rewards short games |
| SCORE-03 | Scoring | LOW | scorer | BATNA dimension capped at 80 |
| SCORE-04 | Scoring | MEDIUM | scorer | Value Creation gameable via keyword spam |
| PERSONA-01 | Persona | HIGH | persona | Difficulty modifier backwards for half the scenarios |
| PERSONA-02 | Persona | MEDIUM | persona | AVOIDING personas are frustrating not engaging |
| PERSONA-03 | Persona | LOW | persona | ACCOMMODATING too easy, no tension |
| PERSONA-04 | Persona | MEDIUM | persona | COMPROMISING ignores pressure_factor |
| DEBRIEF-01 | Debrief | MEDIUM | debrief | No-deal money-left uses wrong baseline |
| DEBRIEF-02 | Debrief | MEDIUM | debrief | Dollar impact uses terminal state not per-turn state |
| DEBRIEF-03 | Debrief | LOW | playbook | Pre-session playbook leaks reservation price |
| PLAY-01 | Playbook | MEDIUM | playbook | Opening lines are salary-only framing |
| PLAY-02 | Playbook | LOW | playbook | Concession ladder ignores non-monetary trades |
| PLAY-03 | Playbook | LOW | playbook | Literal [placeholder] brackets in output |
| PLAY-04 | Playbook | LOW | playbook | Key questions salary-biased, no scenario branching |

**HIGH severity (fix first):** BUG-01, SCORE-01, PERSONA-01
**MEDIUM severity (fix in W2):** BUG-02, BUG-03, SCORE-02, SCORE-04, PERSONA-02, PERSONA-04, DEBRIEF-01, DEBRIEF-02, PLAY-01
**LOW severity (polish pass):** BUG-04, BUG-05, SCORE-03, PERSONA-03, DEBRIEF-03, PLAY-02, PLAY-03, PLAY-04
