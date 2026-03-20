# Scoring Fairness Audit

Reviewed: `core/scorer.py`, `core/debrief.py`, `core/playbook.py`
Date: 2026-03-19

---

## 1. Are the Six Dimensions the Right Ones?

**Verdict: Mostly yes, with one significant gap.**

The six dimensions map well to the negotiation skills literature (Fisher/Ury, Malhotra/Bazerman, Voss):

| Dimension | Covers | Research Basis |
|-----------|--------|---------------|
| Opening Strategy | Anchoring effect | Tversky & Kahneman; strong empirical support |
| Information Gathering | Probing, active listening | Fisher/Ury "separate people from positions" |
| Concession Pattern | Reciprocity, diminishing steps | Cialdini; concession pacing is well-studied |
| BATNA Usage | Leverage through alternatives | Fisher/Ury BATNA framework, core concept |
| Emotional Control | Composure under pressure | Voss "never split the difference"; Bazerman |
| Value Creation | Integrative bargaining | Lax & Sebenius "creating and claiming value" |

**Missing dimension: Relationship Management / Process Control.** A skilled negotiator manages rapport, timing, and conversational flow. Someone who asks great questions, anchors well, but is abrasive or rushes the process is missing a skill the scorer ignores. This matters especially in rent, raise, and vendor scenarios where the ongoing relationship is the real product. Recommend adding a seventh dimension (weight 0.10, taken from Concession Pattern's 0.25).

**Minor concern: "Value Creation" is salary-biased.** The keyword list (`bonus`, `equity`, `stock`, `remote`, `vacation`) is tuned for job negotiations. In a medical bill scenario, the integrative terms are `payment plan`, `financial hardship`, `itemized bill`, `charity care`. In car buying, it is `trade-in`, `financing`, `warranty`, `extras`. In rent, it is `lease term`, `maintenance`, `parking`, `move-in date`. A user negotiating a medical bill brilliantly on non-monetary terms would score 25 because none of those words appear in the keyword list.

**Recommendation:** Make the `package_terms` tuple scenario-aware. Pass the scenario type into the scorer and load domain-specific keyword sets.

---

## 2. Are the Weights Well-Calibrated?

Current weights:

| Dimension | Weight |
|-----------|--------|
| Concession Pattern | 0.25 |
| Opening Strategy | 0.20 |
| Information Gathering | 0.15 |
| BATNA Usage | 0.15 |
| Value Creation | 0.15 |
| Emotional Control | 0.10 |

**Verdict: Reasonable but slightly over-indexes on distributive tactics.**

Concession Pattern (0.25) and Opening Strategy (0.20) together account for 45% of the score. These are both distributive (claiming value) skills. Information Gathering (0.15) and Value Creation (0.15) are the integrative (creating value) skills, totaling only 30%. This tilts the system toward rewarding aggressive-but-disciplined negotiators over creative-but-flexible ones.

A user who anchors modestly but discovers a hidden constraint and proposes a creative package deal has objectively negotiated better than one who anchors aggressively and grinds through small concessions. The current weights disagree.

**Proposed rebalance:**

| Dimension | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| Opening Strategy | 0.20 | 0.15 | Still important but shouldn't dominate |
| Information Gathering | 0.15 | 0.20 | Discovery drives everything downstream |
| Concession Pattern | 0.25 | 0.20 | Reduce claim-side overweight |
| BATNA Usage | 0.15 | 0.15 | Fine as-is |
| Emotional Control | 0.10 | 0.10 | Fine as-is; hard to measure from text alone |
| Value Creation | 0.15 | 0.20 | Integrative skill is the advanced skill |

This shifts the balance from 45/30 (distributive/integrative) to 35/40, which better reflects what negotiation research considers expert-level skill.

---

## 3. Can a User Game the System?

**Yes, in at least four ways:**

### 3a. Extreme anchoring exploit
The Opening Strategy scorer gives 95 for any anchor 20%+ above the opponent's opening. There is no ceiling penalty. A user could anchor at 500% above the opponent's opening and still score 95. In a real negotiation, this would destroy credibility and end the conversation. The scorer has no "absurdity penalty" for anchors that exceed the reservation price by unreasonable margins.

**Fix:** Add a credibility band. Anchors beyond 40% above/below the opponent's opening should start losing points (e.g., cap at 85 for 40%+, drop to 60 for 100%+).

### 3b. Keyword stuffing for Value Creation
Mentioning "bonus equity stock remote" in a single sentence would score 88 on Value Creation regardless of whether those terms were used meaningfully. The scorer counts keyword presence, not contextual use.

**Fix:** Require keywords to appear in turns classified as QUESTION or INFORMATION_SHARE moves, not just anywhere in the text.

### 3c. Single-question BATNA exploit
Saying "I have other options" once gives 80 on BATNA Usage. Saying it twice drops to 65. The optimal strategy is exactly one mention, regardless of timing or context. A late, irrelevant BATNA mention scores the same as a well-timed one.

**Fix:** Weight BATNA timing. A BATNA signal in the first third of the negotiation (before counters begin) should score higher than one dropped after the deal is nearly closed.

### 3d. Question count farming
Asking 4 vacuous questions in 10 turns hits the 0.4 ratio threshold for a 90 score. The scorer counts `user_question_count` but does not evaluate question quality or variety.

**Mitigation difficulty:** Hard to fix without NLP analysis. Acceptable for MVP. Could add a "unique topic" check in v2.

---

## 4. Does the Scoring Reward Good Negotiation or Just Aggressive Negotiation?

**It leans aggressive, but the SCORE-01 fix partially corrects this.**

The SCORE-01 fix in `_score_concession_pattern` (lines 243-278) is smart: it checks whether a zero-concession deal actually landed near the reservation price. Accepting the first offer without pushing scores only 35. This prevents the "doormat gets 100" bug.

However, the system still rewards:
- **Aggressive anchoring** (95 at 20%+ gap) without penalizing relationship damage
- **Withholding information** (no penalty for never sharing anything)
- **Pressure tactics** (no explicit penalty for user-side pressure moves)

A "good" negotiation in the collaborative sense (both parties satisfied, relationship intact, creative solution found) can score lower than an aggressive one (extreme anchor, one BATNA threat, tight concessions) that leaves the opponent feeling exploited.

**The playbook partially compensates.** The playbook's advice for accommodating opponents explicitly says "Don't exploit this -- push for fair value but maintain the relationship." The concession ladder recommends conditional trades, not unilateral extraction. But the scorer does not enforce these values -- it only enforces the distributive mechanics.

---

## 5. Scenarios Where a "Good" Negotiation Gets a Bad Score

### Scenario A: Medical bill -- empathetic approach
A user dealing with Karen Webb (billing rep) who politely explains financial hardship, asks about assistance programs, and accepts a 15% discount after two exchanges. This is the textbook correct approach for medical billing.

Score prediction:
- Opening Strategy: 20 (didn't anchor first -- the bill is the anchor)
- Information Gathering: ~48-72 (depends on question count)
- Concession Pattern: ~35-50 (accepted near opening)
- BATNA Usage: 20 (no competing hospital)
- Emotional Control: 85 (stayed calm)
- Value Creation: 25 (no salary keywords in medical context)

**Estimated overall: 35-45.** A terrible score for what is actually optimal medical bill negotiation strategy. The user followed the correct playbook (ask for hardship program, be cooperative) and gets punished.

### Scenario B: Rent negotiation -- long-term relationship play
A user negotiating with Patricia Owens who offers to sign a 2-year lease in exchange for flat rent. This directly triggers a hidden constraint (she would accept flat rent for a 2-year lease). The user never anchors aggressively, never mentions a BATNA, and accepts relatively quickly.

Score prediction:
- Opening Strategy: ~30-55
- BATNA Usage: 20
- Concession Pattern: ~50-70

**Estimated overall: 45-55.** The user executed the optimal strategy for this specific scenario and gets a mediocre score.

### Scenario C: Budget request -- data-driven pitch
A user presenting a strong ROI case to Catherine Wu, who responds to structured arguments. If the user shares information generously (which Wu rewards), asks questions, and makes modest concessions linked to milestones -- this is optimal. But sharing information is not scored positively, and modest anchoring loses points.

### Root cause
The scorer applies the same rubric to all 10 scenario types. Medical bill negotiation is fundamentally different from salary negotiation. The "anchor high, concede slowly, mention BATNA" formula is wrong for 4 of the 10 scenarios (medical_bill, rent, raise, budget_request), where the optimal strategy is collaborative, relationship-first, and sometimes involves accepting a reasonable offer quickly.

**Fix:** Introduce scenario-type weighting adjustments. For medical_bill, suppress Opening Strategy weight and boost Information Gathering and Value Creation. For rent, boost Relationship (if added) and reduce BATNA Usage.

---

## 6. Are the Coaching Tips Useful and Specific?

**Verdict: The tips are above average for a v1. Specific strengths and weaknesses below.**

### Strengths
- Tips are generated only for scores below 70 -- avoids overwhelming the user
- Concession tips include concrete mechanics ("5k -> 2k -> 1k" pattern)
- BATNA tips correctly note that mentioning alternatives too often sounds like bluffing
- Emotional control tips give exact scripts ("Let me think about that")
- Tips are sorted by weakest dimension first -- prioritizes what matters most

### Weaknesses
- **Opening Strategy tip is generic for low scores.** "Anchor 15-25% above your target" does not help in medical bill or rent contexts where anchoring is inappropriate.
- **No positive reinforcement.** Tips only fire below 70. A user who scores 75 on everything gets zero tips. Some "keep doing this" feedback on strengths would improve the learning experience.
- **Value Creation tips are salary-biased.** "Ask about equity, title, remote days" is useless in a car buying scenario.
- **Missing scenario context.** No tip says "In a medical bill negotiation, the optimal first move is to ask about financial assistance programs." Tips are generic across all 10 types.
- **Limited to 3 tips.** The top_tips cap of 3 is good for avoiding overload but means a user who is weak in 5 areas only hears about 2-3 of them. Consider adding a "full report" option alongside the top-3.

---

## 7. Does the Scorer Handle All 10 Scenario Types Correctly?

**No. The scorer is scenario-agnostic, which causes systematic errors for 5 of the 10 types.**

| Scenario Type | Direction Detection | Anchor Scoring | Value Creation Keywords | Correct? |
|---|---|---|---|---|
| salary | user_wants_more | Works | Good match | Yes |
| freelance | user_wants_more | Works | Partial (no "rate", "scope", "deliverable") | Mostly |
| rent | user_wants_less | Works | Bad (no "lease", "maintenance", "parking") | No |
| medical_bill | user_wants_less | Problematic (user rarely "anchors") | Bad (no "payment plan", "hardship", "itemized") | No |
| car_buying | user_wants_less | Works | Partial (no "trade-in", "financing", "warranty") | Mostly |
| scope_creep | user_wants_more | Works | Partial (has "scope" but misses "change order", "SOW") | Mostly |
| raise | user_wants_more | Works | Good match | Yes |
| vendor | user_wants_less | Works | Bad (no "terms", "SLA", "volume discount") | No |
| counter_offer | user_wants_more | Works | Good match | Yes |
| budget_request | user_wants_more | Works | Bad (no "ROI", "milestone", "phased") | No |

The direction detection (line 147: `if anchor >= opp`) works correctly for all types. The mechanical issue is not direction but domain vocabulary and strategy appropriateness.

---

## 8. Is the 0-100 Scale Intuitive?

### What the scores mean in practice

Using the current weights and scoring thresholds:

| Score | Meaning | How You'd Get There |
|---|---|---|
| 90-100 | Near-perfect on all dimensions | Aggressive anchor, 3+ questions, decelerating concessions, one BATNA signal, calm throughout, explored package terms |
| 75-89 | Strong negotiation with minor gaps | Missed one dimension (e.g., no BATNA, or flat concessions) |
| 60-74 | Competent but left significant value on the table | Anchored modestly, few questions, or conceded too freely on one axis |
| 45-59 | Below average -- multiple dimensions weak | Didn't anchor first, no questions, accepted too quickly |
| 30-44 | Poor negotiation | Multiple failures: no anchor, no questions, no BATNA, emotional capitulation |
| 0-29 | Did not negotiate | Accepted first offer with zero engagement |

### Problem: the "average" user will score 40-55

A typical untrained negotiator will:
- Not anchor first (Opening: 20)
- Ask 0-1 questions (Info: 15-48)
- Accept after 1-2 rounds (Concession: 35-50)
- Not mention alternatives (BATNA: 20)
- Stay calm (Emotional: 85)
- Not explore package (Value: 25)

**Weighted average: ~33-45.** This means most first-time users will see a score in the 30s-40s, which feels punitive and discouraging. The scale is technically correct (they did negotiate poorly) but pedagogically counterproductive.

**Recommendation:** Either (a) shift the floor -- make 50 the "you showed up and tried" baseline, or (b) label the scale explicitly ("Under 40 = untrained baseline, most people start here; 60+ = you're ahead of most negotiators") so users understand a 42 is normal, not shameful. The debrief already does good work here by showing what was left on the table -- framing the gap as opportunity rather than failure.

---

## 9. Cross-Module Consistency: Scorer vs. Debrief vs. Playbook

### Scorer and Debrief: Mostly Aligned

Both modules:
- Agree that anchoring first matters
- Agree that concession deceleration is important
- Agree that BATNA overuse weakens the signal
- Use the same direction-detection logic

**One tension:** The debrief's `_compute_optimal_move` (line 491) says accepting when gap_to_reservation > 0 is suboptimal. But the scorer's concession pattern gives 95 for deals near the reservation price even without concessions. These agree on principle but the debrief is stricter -- it wants you to squeeze out every dollar, while the scorer rewards discipline even if you stopped a bit early. This is a healthy tension, not a contradiction.

### Scorer and Playbook: Partially Misaligned

**Misalignment 1: Concession sizing.**
The playbook builds a concession ladder of 40% / 25% / 10% of negotiating room. The scorer penalizes concessions above 7% of anchor per step. These can conflict: if the anchor-to-walkaway range is 30% of anchor, the first playbook step (40% of that range = 12% of anchor) would trigger the scorer's "large concession" penalty. The playbook's recommended first move gets scored as undisciplined.

**Fix:** Align the scorer's "large concession" threshold with the playbook's recommended step sizes, or make the playbook aware of the scoring thresholds.

**Misalignment 2: Information sharing.**
The playbook encourages sharing information with transparent opponents ("Sharing information with a transparent opponent builds trust" -- debrief line 552) and the opening lines frequently share reasoning. But the scorer has no positive signal for information sharing -- only Value Creation's keyword counting, which is indirect. A user who follows the playbook's advice to share context gets no scoring credit for it.

**Misalignment 3: Walk-away point.**
The playbook sets the walk-away at the midpoint between opening and reservation. The scorer evaluates deals against the reservation price. A user who follows the playbook's walk-away advice and leaves at the midpoint will show "money left on the table" in the debrief equal to half the negotiating range. The playbook is conservative (protect the user from bad deals), while the debrief is aspirational (show how much more was possible). This is acceptable if framed clearly, but could confuse users who follow the prep document perfectly and then see a large "left on the table" number.

---

## 10. Summary of Recommended Fixes

### Critical (affects scoring fairness)
1. **Make Value Creation keywords scenario-aware.** Load domain-specific terms per scenario type. Without this, 4 of 10 scenarios have a broken dimension.
2. **Add absurdity penalty to Opening Strategy.** Cap or penalize anchors beyond 40% of opponent's opening to prevent gaming.
3. **Align concession size thresholds** between scorer and playbook so the playbook's own advice does not trigger scoring penalties.

### Important (affects pedagogical quality)
4. **Rebalance weights** toward integrative skills (Information Gathering and Value Creation up, Opening Strategy and Concession Pattern down).
5. **Add score floor or contextual labels** so first-time users scoring in the 30s-40s understand this is a normal starting point.
6. **Add scenario-type weight adjustments** so medical bill, rent, and budget request scenarios do not penalize collaborative approaches.

### Nice-to-Have (v2 improvements)
7. Add a Relationship Management dimension.
8. Gate keyword counting to QUESTION/INFORMATION_SHARE moves to prevent stuffing.
9. Weight BATNA timing (early > late).
10. Add "strengths" feedback alongside weakness-triggered tips.
11. Add a "full report" mode alongside the top-3 tips.
