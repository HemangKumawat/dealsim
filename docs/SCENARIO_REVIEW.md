# Scenario & Difficulty System Review

**Reviewed:** `src/dealsim_mvp/core/persona.py`, `simulator.py`, `scorer.py`, `challenges.py`, `session.py`
**Date:** 2026-03-20
**Method:** Direct source reading. Prior audit findings (SCENARIO_QUALITY_AUDIT.md, SCORING_FAIRNESS_AUDIT.md, ENGINE_CORRECTNESS_AUDIT.md, all dated 2026-03-19) are referenced where relevant but not repeated verbatim.

---

## 1. How Scenarios Are Defined

Each of the 10 scenario types has a dedicated template dict in `persona.py`. Templates are factory lambdas: they accept a single numeric parameter (the user's target value) and return a `NegotiationPersona` dataclass. The persona carries:

- **Three price points:** `target_price` (what the opponent wants), `reservation_price` (their walk-away), `opening_offer` (first number they state).
- **Three behavioral floats (0–1):** `patience`, `transparency`, `emotional_reactivity`.
- **Style and pressure enums:** `NegotiationStyle` (COMPETITIVE, COLLABORATIVE, ACCOMMODATING, AVOIDING, COMPROMISING) and `PressureLevel` (LOW, MEDIUM, HIGH).
- **Hidden constraints:** a list of strings the simulation uses internally but does not show the user — the "discoverable secrets" that reward good questioning.
- **system_prompt:** a plain-English instruction block for a future LLM engine. Currently used only for documentation; the rule-based simulator ignores it.

Template selection is random within the scenario type. If a type has one template (freelance), every freelance session uses the same persona structure. If it has three (rent, medical_bill), the simulator picks one at random.

---

## 2. How Difficulty Affects AI Behavior

Difficulty is applied as a post-template modifier in `generate_persona_for_scenario`. The logic is direction-aware:

**Hard mode:**
- `patience -= 0.3` (capped at min 0.1)
- `transparency -= 0.2` (capped at min 0.1)
- If user wants a lower number (medical_bill, car_buying, rent, vendor, scope_creep): `reservation_price *= 1.05` — opponent's floor rises, less room to push price down.
- If user wants a higher number (salary, raise, freelance, counter_offer, budget_request): `reservation_price *= 0.95` — opponent's ceiling drops, less room to push price up.

**Easy mode:**
- `patience += 0.2` (capped at max 0.9)
- `transparency += 0.3` (capped at max 0.8)
- Buyer scenarios: `reservation_price *= 0.95` — opponent more generous.
- Earner scenarios: `reservation_price *= 1.10` — more headroom.

These modifiers are applied on top of whatever the template set. The combined effect: hard mode produces an opponent who is less patient, less forthcoming, AND has a tighter price range. Easy mode produces a more forthcoming opponent with a wider range.

**The behavioral modifiers matter more than the price shift.** A reduction in transparency means the question-response function (`_question_response` in simulator.py) returns vaguer answers about budget. A reduction in patience doesn't affect turn count directly, but `pressure_factor` in `_compute_opponent_offer` scales the opponent's concession step size — higher pressure means larger concession steps. Lower patience therefore means the opponent concedes in bigger chunks, which is actually easier for the user, not harder. This is a behavioral inversion: hard mode's patience reduction inadvertently makes the opponent more concessive, partially offsetting the tighter reservation price.

**The slider system (opponent_params) is separate from difficulty.** It overrides style (aggressiveness), reservation range (flexibility), patience, transparency, emotional_reactivity, and pressure level directly via 0–100 sliders. The slider and difficulty systems can stack — difficulty runs first, then sliders overwrite specific fields.

---

## 3. How Scoring Works Across the 6 Dimensions

The scorer in `scorer.py` is stateless — it reads a completed `NegotiationState` and computes six scores from the accumulated counters.

| Dimension | Weight | Primary Signal |
|---|---|---|
| Opening Strategy | 0.20 | Whether user anchored first; how far from opponent's opening |
| Information Gathering | 0.15 | `user_question_count` / `turn_count` ratio |
| Concession Pattern | 0.25 | Average concession size as % of anchor; deceleration; reciprocity |
| BATNA Usage | 0.15 | Count of `user_batna_signals` (0=20, 1=80, 2+=65) |
| Emotional Control | 0.10 | Rapid capitulation after PRESSURE move; single step > 15% of anchor |
| Value Creation | 0.15 | Keyword presence (`bonus`, `equity`, `remote`, etc.) + `user_information_shares` |

The overall score is a weighted average. Tips fire only for dimensions below 70, and only the top 3 (by lowest score) are surfaced.

---

## 4. Strongest and Weakest Scenarios

### Strongest

**Medical Bill (3 templates)** is the strongest scenario set in the codebase. The three-persona escalation path (first-line rep → supervisor → financial assistance) mirrors real US hospital billing exactly. The hidden constraints are all real policies most patients don't know exist. The first-line rep's authority cap at 15%, the supervisor's lump-sum bonus, and the financial assistance coordinator's 75% charity care ceiling all teach directly applicable skills. The system prompts are the most carefully written in the file.

**Rent Negotiation (3 templates)** is a close second. The three-tier landlord structure (individual/property manager/REIT) provides a natural difficulty ladder within the scenario type itself, independent of the hard/medium/easy modifier. The individual owner's emotional reactivity (0.7) combined with low pressure creates a qualitatively different dynamic from the REIT's zero-emotion, high-patience profile. The opening-offer anchoring above target (REIT opens at 1.10x, higher than its 1.08x target) is the only example of this tactic in the entire template library — a realistic touch.

**Raise Request (2 templates)** has the best character contrast. The supportive manager and the dismissive VP are immediately recognizable archetypes. The dismissive VP's hidden constraints (company profitable, two employees already left, HR flagged retention risk) create a specific dynamic where the correct play is to present external market evidence — not pressure, not BATNA, but data. This teaches a distinct skill from the salary templates.

### Weakest

**Freelance Rate (1 template)** is the weakest by a significant margin. One template means every freelance scenario produces the same persona (Mike Thompson). Users who run this scenario twice encounter identical behavior. The `budget_client` archetype covers only one of three real freelance client types — the price-sensitive one. There is no high-value urgent client and no bureaucratic procurement gatekeeper. The scenario is playable but thin.

**Budget Request (2 templates)** is the second weakest, not because the templates are poor — they are well-constructed — but because the scoring system fails this scenario specifically. The optimal move when dealing with Catherine Wu (data_driven_vp) is to share ROI data generously and make a structured argument. Information sharing earns nothing in the scorer. The `package_terms` keyword list for Value Creation contains "budget" (which appears in the scenario name, not in integrative trade language) but misses the actual integrative terms for this context: "ROI", "milestone", "phased", "pilot". A user who plays this scenario exactly right will score poorly on two of the six dimensions through no fault of their own.

**Scope Creep (2 templates)** has a known code bug: the `corporate_manager` system_prompt contains an unformatted f-string expression `${budget * 1.40:.0f}` in a plain string. When a future LLM engine reads this prompt, it will see the literal syntax instead of a dollar amount. The startup_founder reservation (1.25x) is also lower than real demo-day urgency would justify.

---

## 5. Difficulty Scaling Assessment

### Does Easy feel approachable?

Yes, with one nuance. Easy mode raises transparency by 0.3, which meaningfully changes the question-response behavior — the opponent will volunteer budget information more readily. Combined with a more generous reservation price, easy sessions genuinely reward basic technique (ask a question, make a reasonable counter, close the gap). A first-time user should be able to reach a deal and score in the 50–65 range on easy with no training.

### Does Hard feel challenging?

Partially. The price tightening works correctly — on hard, a salary negotiation persona that would have gone to 115% of target on medium will only go to ~109% on hard. For experienced users, this meaningfully constrains the outcome ceiling.

The behavioral modifiers are mixed. Reduced transparency on hard mode makes question responses genuinely vaguer, which increases difficulty. However, the patience reduction has the counterintuitive effect described in Section 2: less patient personas apply higher `pressure_factor` in `_compute_opponent_offer`, which causes larger concession steps. A hard-mode opponent may actually concede faster per turn than a medium-mode opponent, even while having a tighter range. This partially undermines the difficulty.

### Is the 5%/10% reservation shift sufficient?

For scenarios with wide ZOPAs, no. The REIT persona on medium difficulty already has a tight range (reservation = 1.05x, opening = 1.10x, ZOPA = 5% of monthly rent). A 5% hard-mode increase pushes reservation to ~1.1025x — nearly identical to the opening offer. The entire negotiating range collapses to near zero. This is accidentally severe rather than intentionally calibrated.

For scenarios with wide ZOPAs (competitive_recruiter on counter_offer: opening = offer, reservation = 1.18x offer — an 18% range), the 5% hard shift reduces it to ~13.1%, which is a meaningful but not dramatic change.

**The core gap:** Flat percentage modifiers applied to absolute reservation prices produce wildly inconsistent difficulty gaps across templates. The ZOPA width varies from 2–3% (REIT) to 18% (recruiter) in the base templates. A ±5% reservation shift means something different in each case.

---

## 6. Are All 10 Scenario Types Properly Implemented?

All 10 are registered in the `templates` dict in `generate_persona_for_scenario` and all 10 resolve to at least one valid template. However "properly implemented" varies by type:

| Scenario | Templates | Implementation Quality | Gap |
|---|---|---|---|
| salary | 2 | Strong | None |
| freelance | 1 | Functional | Thin — only one persona type |
| rent | 3 | Excellent | None |
| medical_bill | 3 | Excellent | None |
| car_buying | 2 | Good | No used-car variant |
| scope_creep | 2 | Good | f-string bug in corporate_manager; startup_founder reservation too low |
| raise | 2 | Strong | None |
| vendor | 2 | Good | Value Creation keywords miss B2B terms |
| counter_offer | 2 | Good | None |
| budget_request | 2 | Good | Value Creation keywords miss ROI/milestone terms |

---

## 7. Scoring Consistency Across Scenarios

The scorer applies a single universal rubric to all 10 types. This causes four systematic errors:

**Error 1: Anchoring is penalized in scenarios where the user is not the one who should anchor.** In medical_bill, the bill amount is the anchor — the opponent sets it before the user speaks. A user who responds to this context by stating a counter-amount below the bill will be scored low on Opening Strategy (they didn't anchor first, or their counter was modest). But the optimal medical bill strategy is not anchoring — it is escalation and documentation. The scorer penalizes the correct approach.

**Error 2: BATNA is irrelevant in three scenarios and the scorer doesn't know.** In rent (where you currently live there), raise (where you work there), and budget_request (internal process), the user typically has no real walk-away alternative. The scorer gives 20/100 for zero BATNA signals regardless of scenario. A manager asking their director for budget has no competing director to threaten.

**Error 3: Value Creation keyword list is salary-tuned.** The keywords (`bonus`, `equity`, `stock`, `remote`, `vacation`, `pto`, `flexible`, `signing`, `relocation`, `title`, `scope`, `budget`, `package`, `benefits`, `option`) make sense for salary, raise, and counter_offer. For medical_bill, the integrative terms are `payment plan`, `financial hardship`, `itemized bill`, `charity care`, `financial assistance`. For car_buying: `trade-in`, `financing`, `warranty`, `accessories`. For budget_request: `ROI`, `milestone`, `phased`, `pilot`. A user who explores all the right non-monetary levers in a medical bill scenario scores 25 on Value Creation.

**Error 4: Opening Strategy direction detection works correctly at the mechanical level but not the strategic level.** The `anchor >= opp` check in `_score_opening_strategy` correctly identifies salary vs. procurement direction. However, the score thresholds (20%+ above = 95, 10%+ = 78, etc.) assume anchoring is always the right first move. For rent negotiations with an individual landlord (Patricia Owens, accommodating style, high emotional reactivity), leading with an aggressive low anchor is likely to trigger emotional defensiveness and reduce flexibility. The scoring rubric rewards aggression equally regardless of the opponent's style.

---

## 8. AI Prompt Quality Assessment

The system prompts in the templates are written for a future LLM engine, not the current rule-based simulator. The current simulator ignores them. Evaluating them as intended LLM prompts:

**Well-crafted prompts:** The three medical_bill prompts are the best in the file. Each specifies the exact authority level ("You can only approve payment plans and up to 15% prompt-pay discount"), the correct escalation signal ("For anything more, say you need to transfer to a supervisor"), and a tonal guide ("Be polite but limited in authority"). These prompts would produce behaviorally distinct, realistic LLM responses.

**Adequate prompts:** The rent negotiation prompts are specific on numbers and tonal register ("Cite market comps and company policy," "Stay professional"). The car_buying floor_salesperson prompt is particularly instructive: "Use the four-square method — shift the conversation to monthly payments, trade-in value, and financing. Avoid discussing the out-the-door price directly." This would produce authentic car-dealer behavior from an LLM.

**Thin prompts:** The scope_creep prompts give the right number but weak behavioral instruction. "Say things like 'this should only take an hour'" provides one example phrase but no underlying behavioral logic. Compare with the dismissive_manager raise prompt: "Deflect with 'review cycle is in Q4' and 'everyone wants a raise.' Only concede when presented with concrete evidence of market value or competing offers." The raise prompt encodes decision logic, not just sample phrases.

**Bug:** The `corporate_manager` scope_creep prompt contains the literal string `${budget * 1.40:.0f}` where it should contain the computed dollar amount. This is because the string is not marked as an f-string (no `f` prefix). The startup_founder template immediately above it uses f-strings correctly. The bug is in `persona.py` at the `corporate_manager` lambda, line 373–378.

**Generic openers:** The `_compose_opener` function in `simulator.py` uses five style-specific template pools, but the templates are written in a salary/hiring context ("based on the role and our budget"). In a rent negotiation, "our standard range for this position starts at $X" is stylistically wrong. The opener templates do not adapt to scenario type — they assume a hiring context.

---

## 9. Are the 6 Scoring Dimensions Well-Defined and Distinguishable?

The definitions are clear in the code. The distinguishability question is more interesting:

**Well-distinguished pairs:**
- Opening Strategy vs. Concession Pattern: Opening is about the first number; Concession is about all subsequent moves. No overlap.
- BATNA Usage vs. Emotional Control: BATNA is about leverage signals; Emotional Control is about reactive behavior under pressure. No overlap.
- Information Gathering vs. Value Creation: Information Gathering counts questions asked; Value Creation counts package terms mentioned. These measure different moves.

**Potential conflation:**
- Information Gathering and Value Creation can both score from the same user move. A user who asks "What does the full package look like?" increments `user_question_count` (boosting Information Gathering) AND mentions the word `package` in their text (boosting Value Creation). The dimensions overlap for package-exploration questions. A user who phrases this as "Tell me about the full package" rather than "What does the full package look like?" gets only Value Creation credit, not Information Gathering credit, because the `?` signal is absent. The scoring boundary depends on punctuation.

- Emotional Control and Concession Pattern overlap in the "panic concession" detection. A single step > 15% of anchor triggers an Emotional Control penalty AND inflates the Concession Pattern average, potentially penalizing both dimensions for the same event.

**The weakest dimension definition:** Emotional Control is defined as the absence of two specific patterns (capitulation after PRESSURE, panic concession). This is narrow. A user could be argumentative, aggressive, or unprofessional in ways that are not captured by these patterns and still score 85. The dimension scores 85 by default — it is the only dimension where the base case (no bad patterns detected) is a high score rather than a low one. This means most users will score high on Emotional Control simply by not doing two specific bad things, which may not reflect their actual composure.

---

## 10. Summary of Findings

### What works well
- The direction-aware difficulty modifier is correctly implemented for all 10 scenario types.
- The rent and medical_bill scenario sets are production-ready and genuinely educational.
- The daily challenge progression (30 challenges across 6 skill categories) is well-sequenced and the success hints are specific and actionable.
- The concession pattern scorer's SCORE-01 fix (checking where in the ZOPA a no-concession deal landed) correctly distinguishes "disciplined hold" from "passive acceptance."
- The hidden constraints across all templates are discoverable through plausible questions and teach real-world leverage.

### What needs attention

**Code bug (should fix before LLM engine integration):**
- `scope_creep` / `corporate_manager` system_prompt is a regular string containing f-string syntax. The computed budget ceiling will never appear.

**Difficulty system gaps:**
- The patience reduction in hard mode has an inverted behavioral effect (less patient opponent = larger concession steps via pressure_factor). The intended effect (harder) and the actual mechanical effect (faster-conceding) work against each other.
- Flat ±5%/±10% reservation modifiers produce wildly different actual difficulty changes depending on the template's base ZOPA width. Templates with tight base ZOPAs (REIT at 5%) become effectively un-negotiable on hard. Templates with wide ZOPAs (recruiter at 18%) barely change.

**Scoring inconsistencies:**
- Value Creation keyword list is salary/raise/counter_offer specific. Medical bill, car buying, vendor, and budget request scenarios have broken Value Creation scoring as a result.
- Opening Strategy and BATNA Usage apply inappropriate rubrics to medical_bill (user rarely anchors first) and budget_request/raise/rent (user rarely has a genuine walk-away alternative).
- The scorer has no scenario-type context — a user who plays all 10 types is evaluated by the same rubric regardless of what the optimal strategy actually is for each type.

**Template gaps:**
- Freelance rate has one template vs. 2–3 for every other type. Repeated play produces identical behavior.

**Prompt quality:**
- The `_compose_opener` templates in `simulator.py` are written in a hiring/salary register and are contextually wrong for rent, medical bill, car buying, and vendor scenarios. When the rule-based simulator is replaced with an LLM, the opener style will already be wrong for half the scenario types.

### Priority ranking

| Priority | Item | File |
|---|---|---|
| 1 | Fix f-string bug in corporate_manager system_prompt | `persona.py` |
| 2 | Make Value Creation keywords scenario-type-aware | `scorer.py` |
| 3 | Investigate patience/pressure_factor interaction in hard mode | `simulator.py`, `persona.py` |
| 4 | Scale difficulty modifier relative to ZOPA width, not flat % | `persona.py` |
| 5 | Add scenario-type suppression for inapplicable dimensions (Opening Strategy for medical_bill; BATNA for raise/rent/budget_request) | `scorer.py` |
| 6 | Add 1–2 freelance rate templates (premium client, procurement gatekeeper) | `persona.py` |
| 7 | Rewrite `_compose_opener` with scenario-type variants | `simulator.py` |
| 8 | Raise startup_founder scope_creep reservation from 1.25 to 1.35 | `persona.py` |
