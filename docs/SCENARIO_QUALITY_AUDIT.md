# Scenario & Challenge Quality Audit

**Reviewer background:** 20 years negotiation training, specializing in AI simulation realism and training value.
**Date:** 2026-03-19
**Files reviewed:** `persona.py` (22 persona templates, 10 scenario types), `challenges.py` (30 daily challenges)

---

## Part 1: Persona Template Review by Scenario Type

### 1. Salary Negotiation (2 templates: startup_cto, corporate_hr)

**Realism:** Strong. The startup CTO being collaborative with moderate pressure reflects real hiring dynamics at Series B companies. The corporate HR being compromising with low pressure and strict pay bands is textbook Fortune 500 behavior. Both personas would be immediately recognizable to anyone who has been through these conversations.

**Hidden constraints:** Well-designed and discoverable. The startup CTO's "board approved 20% above market" is the kind of thing a good candidate surfaces by asking "What does the approved range look like?" The "previous candidate rejected at the low end" rewards candidates who ask about hiring timeline. Corporate HR's signing bonus from a separate budget is a classic real-world lever that trains users to ask about non-salary compensation.

**Price calibration:** The startup CTO's reservation at 115% of target with an opening at 80% creates a generous ZOPA that matches reality — startups competing for talent routinely stretch 15-20% above their initial number. Corporate HR's tight band (reservation at 105%) is accurate for large companies with formal comp structures. Both are realistic for 2026.

**Difficulty adjustment:** The direction-aware modifier is correctly implemented. For salary (user-wants-up), hard mode tightens the reservation down by 5%, reducing the ceiling. Easy mode expands it by 10%. This is sensible. One concern: hard mode also drops patience by 0.3 and transparency by 0.2, which stacks with the price tightening. For corporate_hr (already patience 0.9, transparency 0.2), the hard adjustment produces patience 0.6 and transparency 0.1 — still reasonable. No issues here.

**Verdict:** Ready for production. No changes needed.

---

### 2. Freelance Rate (1 template: budget_client)

**Realism:** Good. The marketing director being competitive with a target at 60% of the freelancer's rate while having budget for the full rate is common behavior. The "previous freelancer quit" constraint is plausible and creates a discoverable lever.

**Hidden constraints:** Solid. "Will pay premium for immediate start" teaches users to probe for urgency. "Has budget for the full rate but wants to save" rewards persistence.

**Price calibration:** Opening at 50% of the freelancer's rate is aggressive but realistic for a budget-conscious agency. Reservation at 85% means the user can capture most of their value with decent technique. Appropriate for 2026 freelance markets where demand remains strong.

**Gap: Only one template.** Every other scenario type has 2-3 templates. This creates repetitive experiences for users who run freelance scenarios multiple times. Recommend adding:
- **Premium client** (collaborative, high-pressure) — e.g., a VP at a well-funded company who needs specialized expertise urgently, reservation at 100-110% of rate. Trains users that not every client is price-sensitive.
- **Procurement gatekeeper** (competitive, low-pressure) — e.g., a procurement officer running a formal RFP process, strict budget bands, requires paperwork. Trains users to handle bureaucratic resistance.

**Verdict:** Functional but thin. Add 1-2 templates.

---

### 3. Rent Negotiation (3 templates: individual_owner, property_manager, corporate_reit)

**Realism:** Excellent three-tier difficulty ladder. Individual owner being accommodating with high emotional reactivity is spot-on — small landlords are often more anxious about vacancy than they let on. Property manager being compromising and professional is accurate. REIT being competitive with 96% occupancy and minimal flexibility mirrors corporate real estate behavior.

**Hidden constraints:** Well-graduated. Individual owner's "would accept flat rent for a 2-year lease" teaches lease-length trading. Property manager's "12% vacancy rate" teaches probing for market conditions. REIT's "cosmetic upgrades instead of price cuts" teaches recognizing non-monetary concessions. Each constraint is discoverable through different questioning approaches.

**Price calibration:** All three open at 8% increase, which is realistic for 2024-2026 rental markets (post-COVID normalization). Reservation prices range from 2% (individual) to 5% (REIT), correctly reflecting that corporate landlords have harder floors. The REIT opening above 8% at 10% to anchor high is a nice touch.

**Difficulty adjustment:** Correct. Hard mode raises the reservation price (opponent concedes less), easy mode lowers it (opponent more generous). The individual owner on easy mode would accept a slight decrease, which is plausible for a vacancy-averse small landlord.

**Verdict:** This is the strongest scenario set. Use it as the template quality bar for other scenarios.

---

### 4. Medical Bill (3 templates: first_line_rep, billing_supervisor, financial_assistance)

**Realism:** Outstanding. This mirrors the actual escalation path patients face. First-line reps genuinely cannot approve large discounts — their authority caps are real. Supervisors having 20-30% authority is accurate. Financial assistance coordinators being collaborative and able to reduce up to 75% matches hospital charity care policies. The style progression (avoiding -> compromising -> collaborative) is exactly how these departments behave.

**Hidden constraints:** Highly realistic and educational. The first-line rep's "must offer financial assistance form if patient mentions hardship" is actual hospital policy at most US hospitals. The supervisor's "hospital writes off 40% of bills sent to collections" teaches users real leverage. The financial assistance coordinator's retroactive application of assistance is a genuine policy most patients don't know about.

**Price calibration:** First-line can discount 15% (prompt-pay), supervisor can go 30%, financial assistance can go 75%. These match actual US hospital billing practices. The $5,000 bill amount is the median range where negotiation training has the most practical value.

**Training value note:** This scenario teaches users about a real system most people don't understand. It has outsized practical value compared to the other scenarios. Consider featuring it more prominently in the UI.

**Verdict:** Exceptional. No changes needed. This scenario alone justifies the product.

---

### 5. Car Buying (2 templates: floor_salesperson, internet_sales_mgr)

**Realism:** Strong. Tony Russo as a high-pressure floor salesperson using the four-square method is a real and well-documented tactic. The internet sales manager being volume-focused with higher transparency reflects the actual shift in car sales toward online departments.

**Hidden constraints:** Effective. The floor salesperson's "monthly quota is 2 cars short" creates exploitable urgency. "Pre-approved $500 in dealer-added extras" teaches users to ask about non-price sweeteners. The internet manager's "dealer holdback" and "unadvertised factory rebates" teach users that the invoice price is not the dealer's true cost — a critical piece of car-buying knowledge.

**Price calibration:** Floor salesperson opens at 117% of user target (sticker markup), with a reservation at 104% (just above invoice). This is realistic — the average new car markup over invoice in 2024-2025 was 5-8%, and 2026 should be similar as inventory normalizes. Internet sales manager has a tighter spread (112% opening, 102% reservation), reflecting volume-based pricing.

**Gap:** No used car dealer template. Used car negotiations are more common than new car purchases for most people, and they involve different dynamics (no factory invoice, condition debates, no holdback). Recommend adding a used car template.

**Verdict:** Good. Consider adding a used car dealer variant.

---

### 6. Scope Creep (2 templates: startup_founder, corporate_manager)

**Realism:** Very good. The startup founder saying "this should only take an hour" and "I thought this was included" is painfully accurate to freelance life. The corporate manager avoiding paperwork by trying to slip extra work under the original contract is realistic.

**Hidden constraints:** Smart. The startup founder having seed funding but hiding it teaches users to probe financial capacity. The corporate manager's "discretionary budget of 40% above contract" being gated behind paperwork she wants to avoid teaches users that bureaucratic resistance is not always budget resistance.

**Price calibration:** Startup founder reservation at 125% of budget feels slightly low. In practice, seed-stage startups burning through runway before demo day will pay 30-50% premiums for speed. Suggest raising to 1.35. Corporate manager at 140% is accurate for Fortune 1000 discretionary budgets.

**Bug in system prompt:** The corporate_manager's system_prompt contains `${budget * 1.40:.0f}` — this is an f-string formatting expression but the string is not an f-string (it uses plain quotes, not an f-prefix). This will render literally as `${budget * 1.40:.0f}` instead of the actual number. Compare with the startup_founder template, which correctly uses an f-string. This needs a fix.

**Verdict:** Good content, minor code bug to fix, consider raising startup_founder reservation.

---

### 7. Raise Request (2 templates: supportive_manager, dismissive_manager)

**Realism:** Strong contrast between the two. The supportive manager who genuinely values the employee but is constrained by budget bands (5-8% standard, can stretch to 12% with VP approval) is common in mid-to-large tech companies. The dismissive VP hoarding budget while HR flags retention risk is a real organizational dysfunction.

**Hidden constraints:** Well-designed. The supportive manager's "can supplement with title bump and RSU refresh from a different budget" teaches users to expand the negotiation space. The dismissive manager's "two people already left over pay" gives the user leverage if they can discover it through the right questions.

**Price calibration:** Supportive manager offering 5% with a ceiling of 12% is realistic for 2026 tech compensation cycles. The dismissive manager at 2-8% is also accurate — many companies still default to cost-of-living adjustments. One note: the user is described as wanting 15%, but the supportive manager's ceiling at 12% and dismissive at 8% mean neither can fully satisfy the request. This is intentional and realistic — it teaches users that 15% raises within a company are genuinely hard to get without a competing offer.

**Verdict:** Ready for production.

---

### 8. Vendor Contract (2 templates: sales_rep, account_manager)

**Realism:** Good. The sales rep under quarterly quota pressure willing to discount 18% on 35% margins is authentic B2B sales behavior. The account manager focused on retention and willing to go 20% to keep a top-10% client is realistic.

**Hidden constraints:** Effective. Quarter-end pressure is the single most exploitable constraint in B2B purchasing — training users to recognize it is high-value. The account manager knowing about a competitor undercutting by 20% teaches users that vendors track competitive threats.

**Price calibration:** Sales rep margins at 35% with an 18% discount ceiling leave the vendor profitable — realistic. Account manager willing to go to 80% of list to retain is aggressive but plausible for a high-value client relationship.

**Verdict:** Solid. No changes needed.

---

### 9. Counter-Offer (2 templates: competitive_recruiter, rigid_hr)

**Realism:** Good contrast. The competitive recruiter with an 18% ceiling and separate signing bonus budget reflects tech recruiting in a tight market. The rigid HR analyst with an 8% hard ceiling and internal equity concerns is accurate for more structured organizations.

**Hidden constraints:** The recruiter's "req open for 4 months" is powerful information that shifts leverage if discovered. The HR analyst's "3 current employees at or below this offer" explains the rigidity and teaches users to empathize with institutional constraints.

**Price calibration:** 18% above initial offer as a ceiling for a recruiter is on the high side but plausible for in-demand roles in 2026. 8% hard ceiling for rigid HR is realistic. The recruiter's separate signing bonus budget ($5K-15K) is accurate for the industry.

**Verdict:** Good. No changes needed.

---

### 10. Budget Request (2 templates: data_driven_vp, risk_averse_vp)

**Realism:** Well-differentiated. The data-driven VP wanting ROI metrics and rewarding structured arguments is a realistic product-side decision-maker. The risk-averse VP of Finance burned by a past failure and wanting phased funding is a common archetype.

**Hidden constraints:** Strong. The data-driven VP's "unspent Q3 budget gets clawed back" creates hidden alignment — she actually wants to spend. The risk-averse VP's "CEO privately told him to fund innovation" means his resistance is emotional, not strategic. Both teach users to look past surface resistance.

**Price calibration:** Data-driven VP opening at 60% but going to 90% is a realistic corporate budget negotiation range. Risk-averse VP at 40-75% with a preference for phased funding is accurate for finance-oriented executives post-market correction.

**Verdict:** Ready for production.

---

## Part 2: Difficulty Adjustment Analysis

The direction-aware difficulty system (PERSONA-01 fix) is correctly designed:

- **User-wants-up scenarios** (salary, raise, freelance, counter_offer, budget_request): Hard mode lowers reservation (less room to negotiate up), easy mode raises it (more room). Correct.
- **User-wants-down scenarios** (medical_bill, car_buying, rent, vendor, scope_creep): Hard mode raises reservation (opponent less willing to concede downward), easy mode lowers it (opponent more generous). Correct.

The behavioral modifiers (patience, transparency) stack with price changes, which creates a meaningful difficulty gap. On hard mode, a less transparent, less patient opponent with a tighter price range is substantially harder than just a tighter range alone.

**One concern:** The 5% reservation shift (hard) and 5-10% shift (easy) may not be enough differentiation for some scenarios. The rent scenario's corporate REIT already has a tight reservation (1.05x) — a 5% hard-mode increase pushes it to ~1.10x, which barely changes the difficulty. Consider scaling the modifier based on the existing ZOPA width rather than applying a flat percentage.

---

## Part 3: Missing Scenarios

High-value additions ranked by frequency of real-world occurrence and training value:

1. **Real estate purchase** — The largest financial negotiation most people will ever face. Involves agent dynamics, inspection contingencies, appraisal gaps, closing cost credits, and emotional attachment to the property. Templates: buyer's agent presenting an offer (collaborative), listing agent protecting seller's price (competitive), FSBO seller with emotional attachment (accommodating/high emotional reactivity). Estimated training value: very high.

2. **Insurance claim dispute** — Common, adversarial, and most people have zero training. The adjuster's incentives are directly opposed to the claimant's. Templates: auto insurance adjuster (competitive, low transparency), homeowner's claim adjuster after a disaster (compromising, medium pressure), health insurance appeal coordinator (avoiding, low pressure). Hidden constraints: adjusters have settlement authority thresholds and are measured on claim closure speed.

3. **Partnership/business dissolution** — High stakes, high emotion. Two former partners splitting assets, clients, IP, and liabilities. Templates: amicable co-founder split (collaborative), acrimonious split with lawyer involvement (competitive). Teaches emotional control under personal betrayal pressure.

4. **Debt collection negotiation** — Extremely practical. Most consumers don't know collectors buy debt at 5-15 cents on the dollar. Templates: original creditor (more rigid), third-party collector (much more flexible). Hidden constraints teach users about debt validation rights and pay-for-delete agreements.

5. **Home contractor/renovation** — Common consumer negotiation. Timeline, materials, payment schedule, warranty, and scope are all in play. Teaches multi-issue trading in a context where most people are inexperienced.

6. **Severance negotiation** — Underserved training area. Most employees don't know severance is negotiable. Templates: HR during layoff (accommodating/guilty), HR during termination-for-cause (competitive). Hidden constraints: non-compete scope, COBRA coverage, reference letter, equity vesting acceleration.

---

## Part 4: Daily Challenges Audit

### 4.1 Variety Assessment

The 30 challenges cover 6 categories with 5 challenges each:

| Category | Days | Scoring Focus |
|---|---|---|
| Anchoring | 1-5 | Opening Strategy |
| Information Extraction | 6-10 | Information Gathering |
| BATNA Usage | 11-15 | BATNA Usage |
| Concession Management | 16-20 | Concession Pattern |
| Emotional Pressure | 21-25 | Emotional Control |
| Multi-Issue Trades | 26-30 | Value Creation |

**Variety within categories is good.** Each category varies the context (selling, buying, renting, employment, contracting) so users don't repeat the same type of transaction. For example, Anchoring covers: selling a MacBook, quoting a logo project, selling a car, salary expectations, and consulting scope. This is well-designed — the skill transfers across contexts.

**Context diversity across the full 30 is strong.** Scenarios include: peer-to-peer sales (MacBook, car, couch), B2B (vendor contracts, consulting), employment (salary, job offers), consumer (hospital bills, rent), and client services (freelancing). No single context dominates.

**One gap:** No challenges involving negotiation on behalf of someone else (e.g., negotiating a raise for a team member, or a parent negotiating with a school). Third-party negotiation is a distinct skill and could be a valuable addition in a future expansion.

### 4.2 Skill Progression

Within each 5-challenge block, the progression is generally sound:

**Anchoring (Days 1-5):** Starts with the simplest case (name a price for a product you're selling), then adds complexity: expert opposition (day 2), re-anchoring after a lowball (day 3), the sensitive salary context (day 4), and finally non-price anchoring (day 5). This is a well-designed learning curve.

**Information Extraction (Days 6-10):** Moves from extracting budget info (straightforward) to detecting hidden deadlines (day 7), reading ambiguous signals (day 8), handling evasive responses (day 9), and probing institutional systems (day 10). Good progression from simple to complex.

**BATNA Usage (Days 11-15):** Covers having a BATNA (day 11), using a mild BATNA (day 12), operating without one (day 13), weakening the opponent's BATNA (day 14), and leveraging research against lock-in (day 15). Day 13 ("BATNA When You Have None") is particularly valuable — most training only covers the case where you have leverage.

**Concession Management (Days 16-20):** Shrinking concessions (day 16), conditional concessions (day 17), resisting split-the-difference (day 18), non-monetary trades (day 19), and conceding on the right dimension (day 20). Solid progression from mechanics to strategy.

**Emotional Pressure (Days 21-25):** Exploding offer (day 21), guilt trip (day 22), anger (day 23), silence (day 24), good-cop/bad-cop (day 25). Each targets a different emotional trigger. Day 24 (silence) is an unusual and valuable inclusion — most people instinctively fill silence with concessions.

**Multi-Issue Trades (Days 26-30):** Expanding the pie (day 26), bundling (day 27), trading across time (day 28), multi-term rent deal (day 29), and the "final boss" combining all dimensions (day 30). Day 30 as a capstone that tests all skills simultaneously is excellent design.

**Overall progression verdict:** The macro arc from mechanical skills (anchoring, info extraction) to strategic skills (concessions, multi-issue trades) with emotional resilience in the middle is pedagogically sound. Users who complete all 30 will have practiced the core negotiation competencies in a logical sequence.

### 4.3 Success Criteria Fairness

Each challenge uses the `success_hint` field to indicate what good performance looks like. These are shown after completion, not during, which is correct — they function as teaching moments.

**Achievability in 3 exchanges:** This is the critical constraint. With only 3 back-and-forth exchanges, users cannot employ long discovery phases or slow concession ladders. The challenges are designed around this:

- **Anchoring challenges:** 3 exchanges is sufficient — anchor, justify, hold. Fair.
- **Information Extraction:** Tight. Extracting 2+ constraints in 3 exchanges requires efficient questioning. Day 9 (evasive client, only needs "at least one data point") correctly adjusts the bar downward. Day 6 asks for "at least two key constraints" which is ambitious but achievable with open-ended questions. Borderline fair.
- **BATNA Usage:** 3 exchanges works — state alternative, respond to pushback, close. Fair.
- **Concession Management:** Day 16 asks for 3 progressively smaller concessions in 3 exchanges — this maps perfectly (one concession per exchange). Fair.
- **Emotional Pressure:** 3 exchanges is actually ideal — these test whether you fold under pressure immediately. The shorter format prevents overthinking. Fair.
- **Multi-Issue Trades:** Day 30 asks users to trade across 4 dimensions (base, PTO, signing bonus, title) in 3 exchanges. This is ambitious but achievable if the user packages their ask efficiently. The hint confirms this: propose a multi-dimensional trade in one move. Challenging but fair.

**Scoring focus alignment:** Each challenge targets exactly one scorer dimension, which means feedback will be specific and actionable. This is strong design — multi-dimensional scoring on a 3-exchange scenario would produce noisy, unhelpful feedback.

**One concern with opponent calibration in challenges:** Several challenge opponents have very wide ZOPAs (e.g., Day 2: Victor targets $2,000 but will pay $4,000; Day 9: Claire targets $15,000 but budget is $30,000). In a 3-exchange format, this means even mediocre performance can land a "deal." The scoring system needs to distinguish between reaching any agreement (easy) and reaching a good agreement (the actual test). If the scorer only checks deal/no-deal, these challenges are too forgiving. If it evaluates where in the ZOPA the user lands, they are well-calibrated.

---

## Part 5: Summary of Recommendations

### Must Fix
1. **Bug:** `scope_creep` corporate_manager system_prompt is not an f-string — the budget ceiling will render as a literal string instead of a number.

### Should Add
2. **Freelance rate templates:** Add 1-2 more templates (premium client, procurement gatekeeper) to match other scenario types.
3. **Real estate purchase scenario:** Highest-value missing scenario by frequency and financial impact.
4. **Used car dealer template:** More common than new car purchases for most users.

### Should Consider
5. **Difficulty scaling:** Consider ZOPA-proportional difficulty modifiers instead of flat 5%/10% shifts.
6. **Startup founder scope creep reservation:** Raise from 1.25 to 1.35 to reflect real demo-day urgency.
7. **Insurance claim scenario:** High practical value, adversarial dynamics, undertrained population.
8. **Severance negotiation scenario:** Underserved, high-stakes, emotionally charged.
9. **Debt collection scenario:** Extremely practical, wide information asymmetry.

### No Changes Needed
- Salary negotiation, rent negotiation, medical bill, raise request, vendor contract, counter-offer, budget request: all production-ready.
- Daily challenges: well-varied, properly sequenced, fair success criteria.
- Direction-aware difficulty adjustment: correctly implemented for all 10 scenario types.
