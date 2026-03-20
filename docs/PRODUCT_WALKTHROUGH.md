# DealSim Product Walkthrough

End-to-end walkthrough of every feature, performed as a simulated real-user test against the full source code (backend + frontend). Each section traces the data flow from UI to API to engine and back.

---

## 1. Landing Page

**What I see:** Dark navy background, coral accent color, Inter font. Top navigation bar with DealSim logo (rocket emoji), plus nav links: Setup, Demo, Offers, Audit, Calculator, History. Mobile hamburger menu is present and adds Opponent Tuner and Daily Challenge links.

**Value proposition:** Headline reads "DealSim -- The Flight Simulator for Negotiations" with subtext "Practice any negotiation against a calibrated AI opponent. Get scored. Get better." Clear and immediately understandable.

**First action:** A large coral-bordered card dominates the fold: "Try a 60-Second Negotiation / No setup required. Jump in and negotiate with AI right now." Below it, three quick-action cards: Offer Analyzer, Daily Challenge, Earnings Calc. Below all of that, the "Full Simulation Setup" form card.

**Verdict: WORKS WELL.** The hierarchy is correct -- zero-friction demo first, power-user setup second. The badge "AI-Powered Negotiation Training" adds credibility. One privacy note at the bottom: "Each session is private and not stored beyond your conversation" -- though sessions ARE persisted to `.dealsim_sessions.json` on the server, which contradicts this claim.

**Issue found:** The privacy statement is misleading. The backend saves full transcripts, persona details, and state to a JSON file on disk (`core/store.py`). If this ships to production, either the persistence or the privacy claim needs to change.

---

## 2. Instant Demo

**What it does:** Clicking the demo CTA shows a "sec-demo" section. Pre-configured scenario: job offer at $85,000, market rate $95-105k, competing offer at $90k. User gets 3 exchanges.

**API trace:**
1. `POST /api/sessions` with body `{ scenario_type: "salary", target_value: 95000, difficulty: "medium", context: "Demo: ...", demo_mode: true }`
2. Backend calls `create_session()` which picks a random persona template (either `startup_cto` or `corporate_hr`), builds a `NegotiationPersona` with `target_value=95000`, generates an opening statement with the opponent's first offer.
3. Response returns `session_id`, `opponent_name`, `opponent_role`, `opening_message`.

**Does the response make sense?** Yes. For `startup_cto` template with target 95000: opening_offer = 95000 * 0.80 = $76,000. The opener text is style-specific (e.g., "I want this to work for both of us. We're thinking around $76,000 to start"). For `corporate_hr`: opening = 95000 * 0.85 = $80,750. Both are realistic lowball salary offers.

**Demo flow:** User types messages, each sent via `POST /api/sessions/{id}/message`. After 3 exchanges OR if `data.resolved` is true, `completeDemoScore()` fires `POST /api/sessions/{id}/complete`, which generates a scorecard. Score is animated with count-up and color-coded (green >= 70, yellow >= 40, red < 40). Verdict text adapts to score range.

**Issue found:** The `demo_mode: true` parameter is sent in the request body but there is no handling for it in `CreateSessionRequest` or anywhere in the backend. It is silently ignored. This is harmless but indicates an incomplete feature -- demo mode was intended to differentiate from full sessions but was never implemented server-side.

---

## 3. Setup (Full Simulation)

**Options available:**
- **Scenario Type:** Dropdown with Salary, Freelance, Business Deal, Custom. However, the backend actually supports 10 scenario types (salary, freelance, rent, medical_bill, car_buying, scope_creep, raise, vendor, counter_offer, budget_request). The frontend only exposes 4. "Business Deal" and "Custom" do not map to any template -- they will fall through to `SALARY_NEGOTIATION_TEMPLATES` as the default.
- **Target Outcome:** Numeric input (e.g., 95000). Required.
- **Difficulty:** Easy/Medium/Hard toggle buttons. Easy is pre-selected. Affects persona patience, transparency, and reservation price.
- **Context:** Textarea for situation description. Required but content is not actually used by the rule-based engine -- it is stored but only matters for a future LLM engine.
- **Opponent Tuner link:** Navigates to slider page.

**Defaults:** Easy difficulty, salary scenario, no target pre-filled. The form validates that target and context are non-empty before submission.

**Issue found:** The scenario dropdown offers "Business Deal" and "Custom" but the backend has no templates for these. They silently default to salary templates. The persona name will still say "Alex Chen, CTO at a Series B startup" even if the user selected "Business Deal." This is confusing -- the dropdown should either match backend capabilities or the backend should handle these types.

**Issue found:** The `opponent_params` from the tuner sliders are sent in the request body but `CreateSessionRequest` in `routes.py` does not define this field. The Pydantic model will silently discard it. The tuner sliders have zero effect on the simulation. This is a dead feature.

---

## 4. Opponent Tuner

**The 6 sliders:**
1. **Aggressiveness** (Friendly to Hardball) - tooltip: "How forcefully the opponent pushes their position."
2. **Flexibility** (Rigid to Very Flexible) - tooltip: "Willingness to make concessions."
3. **Patience** (Impatient to Very Patient) - tooltip: "How long they'll negotiate before forcing a decision."
4. **Market Knowledge** (Uninformed to Expert) - tooltip: "How well they know market rates and industry norms."
5. **Emotional Reactivity** (Stoic to Highly Reactive) - tooltip: "How emotionally they respond to your moves."
6. **Budget Authority** (No Authority to Full Authority) - tooltip: "How much power they have to approve your asks."

**Labels clear?** Yes. Each slider has a descriptive label, a tooltip with explanation, numeric readout (0-100), and semantic labels at both ends. The UX is well-designed with hover tooltips.

**Reset Defaults** button resets all to 50 with a toast notification. **Apply & Setup Sim** navigates back to landing with a toast.

**Critical issue:** As noted above, these sliders update `state.tunerParams` in the frontend JavaScript, and these params ARE sent in the `POST /api/sessions` body as `opponent_params`. But the backend Pydantic model `CreateSessionRequest` does not include `opponent_params`, so they are silently dropped. The sliders do absolutely nothing. The persona is generated entirely from scenario type, target value, and difficulty. This is the single biggest functional gap in the product -- a prominent feature that is completely inoperative.

---

## 5. Chat (5 simulated messages)

**Message 1 (user):** "I was thinking more along the lines of $110,000, given my experience and the market rate for this role."

API flow: `POST /api/sessions/{id}/message` with `{ message: "..." }`. Backend calls `negotiate()` which calls `RuleBasedSimulator.generate_response()`. The engine:
1. Extracts `$110,000` via `_MONEY_RE` regex.
2. Classifies as `ANCHOR` (first user offer).
3. Sets `user_opening_anchor = 110000`, `user_last_offer = 110000`.
4. Checks acceptance: 110000 vs reservation_price. For startup_cto with target 95000, reservation = 95000 * 1.15 = 109,250 (easy mode: * 1.10 = 120,175). If easy mode, $110k is below reservation so NOT accepted. Engine computes counter-offer.
5. Returns opponent text with new offer number.

**State tracking:** `round_counter` increments in the UI. Transcript appends user turn and opponent turn. The `NegotiationState` updates `user_opening_anchor`, `user_last_offer`.

**Message 2 (user):** "What flexibility do you have on the base salary?"

Classified as `QUESTION` (contains "flexibility" and "?"). `user_question_count` increments. Opponent responds with transparency-dependent answer about budget range. No new offer number returned.

**Message 3 (user):** "I have another offer at $95,000 from a competitor."

Contains "another offer" -- classified as `BATNA_SIGNAL`. Extracts $95,000. `user_batna_signals` increments. Opponent responds with pressure-aware BATNA response. May or may not move on price depending on pressure level.

**Message 4 (user):** "I could come down to $105,000 if we can work out a signing bonus."

$105,000 extracted. Previous user offer was $110,000. Since user wants number up and $105k < $110k, classified as `CONCESSION`. `user_concession_count` increments, `user_total_concession` += 5000. "signing bonus" triggers package term detection for Value Creation scoring. Opponent reciprocates with a counter-offer.

**Message 5 (user):** "Let's split the difference. How about $100,000?"

$100,000 extracted. Another concession from $105k. Opponent may accept if $100k falls within acceptance range.

**Does state track correctly?** Yes. The `NegotiationState` dataclass tracks: user_last_offer, opponent_last_offer, opening anchors for both sides, concession counts/totals for both sides, question count, BATNA signals, information shares, turn count, resolved flag, agreed value, and full transcript. All of this is updated correctly per the code logic.

**Chat UX:** Typing indicator (three animated dots) shows while waiting for API response. Enter sends, Shift+Enter for new line, Escape ends negotiation. Keyboard shortcuts are documented below the input. Messages animate in with a slide-up effect. User bubbles are coral, opponent bubbles are slate.

---

## 6. Scorecard

**Trigger:** User clicks "End & Score" or the negotiation resolves naturally. `POST /api/sessions/{id}/complete` calls `complete_session()` which runs `generate_scorecard()`.

**Six dimensions scored:**
1. **Opening Strategy** (weight 0.20) -- anchoring first and ambitiousness
2. **Information Gathering** (weight 0.15) -- question frequency
3. **Concession Pattern** (weight 0.25) -- concession size, deceleration, reciprocity
4. **BATNA Usage** (weight 0.15) -- alternative reference signals
5. **Emotional Control** (weight 0.10) -- capitulation detection, panic concessions
6. **Value Creation** (weight 0.15) -- package term exploration, info sharing

**Total:** Weighted average, displayed as 0-100 with animated count-up. Color-coded: green (>= 70, "Strong Performer" or "Outstanding"), yellow (>= 40, "Developing"), red (< 40, "Needs Practice").

**Each dimension shows:** Score number, colored bar chart with fill animation, explanation text. Coaching tips appear for dimensions scoring below 70.

**Additional elements:** "Money Left on Table" card (fetched from debrief endpoint), coaching tips section (top 3 from weakest dimensions), Share Score button (copies text to clipboard), Debrief & Reveal button, Playbook button, inline feedback form, Try Again button.

**Is the total clear?** Yes. Large circular badge with score number, color ring, and label text. Summary shows deal outcome and agreed value.

---

## 7. Debrief ("What They Were Thinking")

**Trigger:** Click "Debrief & Reveal" from scorecard. `GET /api/sessions/{id}/debrief`.

**What is revealed:**
- **Opponent Target:** The persona's `target_price` (what they wanted).
- **Reservation Price:** The persona's `reservation_price` (walk-away point).
- **Pressure Points:** Text description of opponent's pressure situation.
- **Hidden Constraints:** Array of 3 strings revealing hidden info (e.g., "Board approved up to 20% above market rate for key hires").
- **Outcome Grade:** Letter grade assessment.
- **Money Left on Table:** `optimal_outcome - agreed_value`. This is the dollar amount the user could have gotten if they'd pushed to the opponent's reservation price.
- **Key Moments:** Highlights from the negotiation.
- **Best Move / Biggest Mistake:** Identified from move analysis.
- **Move-by-Move Analysis:** Each turn annotated with move type, strength assessment, and missed opportunities.

**Is hidden state revealed?** Yes. The debrief fully exposes the opponent's internal parameters that were invisible during the negotiation: target price, reservation price, hidden constraints, and pressure level. This is the core learning mechanism.

**Is "Money Left on Table" shown?** Yes. Both on the scorecard (fetched asynchronously after score renders) and on the debrief page. Displayed as a large yellow number.

**Issue found:** The debrief is generated by `api/debrief.py:generate_debrief()` which calculates `money_left_on_table` as `optimal_outcome - agreed_value`. If no deal was reached (`agreed_value` is None), money left on table defaults to the full range between opening and reservation. This could be confusing -- showing money left on table when no deal happened implies you could have gotten it, but the actual issue was no deal at all.

---

## 8. Playbook

**Trigger:** Click "Playbook" from scorecard or debrief. `GET /api/sessions/{id}/playbook`.

**Content:**
- **Your Negotiation Style:** Text profile based on transcript analysis.
- **Strengths:** Array of identified strengths (e.g., "Strong opening anchor").
- **Areas to Improve:** Array of weaknesses.
- **Recommendations:** Structured entries with category, title, description, and priority (high/medium/low). Color-coded by priority.
- **Practice Scenarios:** Suggested follow-up scenarios to practice specific skills.

**Are recommendations specific to MY session?** Yes. The playbook generator (`api/debrief.py:generate_playbook()`) receives the full `NegotiationState` and score. It analyzes the transcript to identify patterns: which dimensions scored low, what move types were used/missing, concession behavior, BATNA usage. Recommendations are generated based on specific weaknesses detected, not generic advice.

**Additional features:** Print button (CSS print styles defined), Copy button (copies text content to clipboard). Print styles invert colors to white background with dark text.

---

## 9. Offer Analyzer

**Input:** Form with Role/Title, Base Salary, Signing Bonus, Equity/Stock, Location, and a full text area for pasting offer details.

**API:** `POST /api/offers/analyze` with `{ offer_text, role, location }`. Backend calls `analyze_offer()` from `core/offer_analyzer.py`.

**Sample test:** Paste "Base salary $130k, 15% annual bonus, 10k signing bonus, 4 weeks PTO, full health coverage, 10k RSU vesting over 4 years" with role "Senior Software Engineer" and location "San Francisco."

**Output structure:**
- Overall score and market position
- Components breakdown: each comp (salary, bonus, equity, PTO) with value, negotiability rating (high/medium/low), and market position (above/at/below)
- Key insights: array of observations
- Counter strategies: each with name, description, suggested counter phrase, risk level, and rationale

**Does analysis match market data?** The backend has bundled market data in `core/offer_analyzer.py` (BLS/H1B-derived percentiles). If role and location are provided AND match the internal database, the salary component gets a `market_position` enrichment (above/at/below) based on p25/p50/p75/p90 benchmarks.

**Issue found:** The market data enrichment only works if the role matches specific keys like "software_engineer" -- the frontend input is a free text field ("Senior Software Engineer") that likely will NOT match the internal keys. The enrichment comparison checks `comp.name in ("base_salary", "salary", "base")` but the component names come from the offer text parser. There is a likely mismatch between free-text component names and the hardcoded keys.

**CTA:** "Practice Negotiating This Offer" button pre-fills the setup form with the offer salary * 1.15 as target and navigates to the landing page. Smart funnel.

---

## 10. Daily Challenge

**Trigger:** Navigate to Daily Challenge section. MutationObserver fires `loadDailyChallenge()`.

**API:** `GET /api/challenges/today`. Backend calls `get_todays_challenge()` from `api/analytics.py`. This generates a deterministic daily challenge based on the current date (date used as seed for selection from a challenge pool).

**What it shows:** Title, description, date, and "Accept Challenge" button. If already completed today (tracked in localStorage), a "Challenge completed today" badge appears.

**Is it different from main simulation?** Partially. Clicking "Accept Challenge" pre-fills the setup form with `scenario_type: "salary"`, `difficulty: "medium"`, and the challenge description as context. It then navigates to the setup form where the user must fill in a target value and submit. The challenge itself uses the same simulation engine -- it is NOT a separate mode with different rules. It is a guided prompt that funnels into the standard simulation.

**Issue found:** The challenge always sets `scenario_type` to "salary" regardless of what the challenge actually describes. If the daily challenge is about freelance rate negotiation or medical bills, it still creates a salary-type persona. The `scenario_prompt` from the challenge could specify a different type, but the `startChallenge()` function hardcodes "salary."

**Fallback:** If the API is down, a static challenge loads: "The Lowball Counter: Your freelance client just offered 40% below your rate." Good resilience.

---

## 11. Earnings Calculator

**Inputs:** Current/Offered Salary ($85,000 default), Negotiated Salary ($95,000 default), Years in Career (30 default), Annual Raise % (3% default).

**Test: $10K raise ($85K to $95K).**

The frontend `recalcEarnings()` function computes:
- `diff = 95000 - 85000 = 10000`
- For each year y from 0 to 29: `yearDiff = 10000 * (1.03)^y`
- Year 1: $10,000
- Year 10: $10,000 * 1.03^9 = $13,047.73
- Year 30: $10,000 * 1.03^29 = $23,616.35
- Lifetime total: sum of all 30 years = ~$475,401

**Is the compound math correct?** Yes. The formula `diff * (1 + raiseRate)^y` correctly compounds the base salary difference year over year. The total is a geometric series sum. For the given inputs: $10K * sum(1.03^0 to 1.03^29) = $10K * 47.5754 = $475,754. The display shows Year 1, Year 10, Year 30 breakdowns and lifetime total.

**Note:** This is a CLIENT-SIDE calculator. It does not call the backend `POST /api/tools/earnings-calculator` endpoint at all. The frontend computes everything in JavaScript with `recalcEarnings()` triggered by `oninput` on every field. The backend has a separate, more sophisticated calculator in `core/earnings.py` that also factors in retirement contributions, employer match, and investment returns -- but it is never called by the frontend.

**Issue found:** The backend earnings calculator (`core/earnings.py`) is significantly more powerful than the frontend one. It includes retirement multiplier effects (employer match + investment returns) that dramatically increase the lifetime impact. The frontend only shows simple salary compounding. The backend endpoint exists but is disconnected from the UI. This is a missed opportunity -- the backend version would show a much more compelling number.

---

## 12. Email Audit (Negotiation Audit)

**Input:** Context field ("What are you negotiating?") and a large textarea for pasting email/message thread.

**API:** `POST /api/tools/audit-email` with `{ email_text }`. Note: the `audit-context` field from the form is NOT sent to the backend. Only `email_text` is sent.

**Sample email pasted:**
"Hi Sarah, Thank you for the offer. I'm excited about the role. However, after researching market rates, I believe the compensation should be closer to $120,000. I have another offer at $115,000. Could we discuss this further?"

**Output structure:**
- Overall score (0-100, color-coded)
- Tone assessment
- Strengths: array of positive observations (e.g., "References market research")
- Issues: array of problems (e.g., "Reveals exact BATNA amount")
- Suggestions: actionable improvements
- Rewrite hints: specific phrases to change

**Is the feedback useful?** The `audit_email()` function in `core/email_audit.py` analyzes the text for negotiation patterns: anchoring, BATNA usage, tone, specificity, information leakage. It provides structured feedback across multiple dimensions.

**Issue found:** The "Context" field the user fills in (e.g., "Salary for senior engineer role") is captured by `document.getElementById('audit-context')` but the `runAudit()` function only sends `email_text` in the request body. The context field is completely ignored. This means the analysis cannot be context-aware.

---

## 13. Score History

**Storage:** localStorage key `dealsim_scores`. Each entry: `{ date, score, outcome, scenario }`. Capped at 50 entries.

**After 2+ sessions:** The MutationObserver on the history section triggers `renderHistory()` when the section becomes active. If history has entries:
- Canvas chart is shown (custom-drawn line chart with colored dots per score range)
- List of score entries below: date, scenario type, score number
- "Clear all history" button at bottom

**Chart implementation:** Custom Canvas 2D rendering. Draws grid lines, Y-axis labels (0-100), plots points connected by coral line, dots colored by score range. Handles single-point case (no line, just a dot).

**Issue found:** The chart has no X-axis labels (dates). With many sessions, there is no way to tell which dot corresponds to which date. The list below provides dates, but the chart itself is unlabeled on the X axis.

**Issue found:** The `renderHistory()` function is only triggered by MutationObserver when the section's class changes. If you complete a session and navigate directly to History, it will show because the section becomes active. But the chart uses `getBoundingClientRect()` for sizing, which may return 0 if the element is not yet visible during the transition. This could cause a zero-sized chart on first render.

---

## 14. Feedback

**Inline feedback** appears on the scorecard page: 5-star rating, optional comment textarea, optional email field, Submit button. Validation requires selecting a star before submission.

**Modal feedback** appears 15 seconds after score view (only on 2nd+ session, tracked via localStorage `dealsim_session_count`). Same star rating + comment, simpler form. Closeable with X or Escape.

**API:** `POST /api/feedback` with `{ session_id, rating, comment, email, final_score, scenario_type }`. Backend calls `get_collector().submit()` which stores feedback in-memory and also persists to a JSON file.

**Does it save?** Yes. The `FeedbackCollector` in `feedback.py` stores entries in memory and persists to `.dealsim_feedback.json` on disk. The submit endpoint always returns `{ status: "ok" }`. If the API call fails, the frontend catches the error and shows a toast "Could not send feedback. Try again later." -- the inline form still transitions to "Thank you" state even on error, which is incorrect.

**Issue found:** On feedback submission failure, the `catch` block shows a toast but then proceeds to hide the form and show the "Thank you" message. The user sees "Thank you for your feedback!" even though feedback was not actually saved. This should only transition on success.

---

## 15. Admin Dashboard

**Access:** `GET /admin/stats?key=YOUR_KEY`. Protected by `DEALSIM_ADMIN_KEY` environment variable.

**If ADMIN_KEY not set:** Returns 503 "Admin dashboard disabled -- DEALSIM_ADMIN_KEY not configured."

**If wrong key:** Returns 403 "Invalid admin key." Uses `secrets.compare_digest()` for timing-safe comparison.

**If correct key:** Returns a styled HTML dashboard with:
- **Stats cards:** Total Sessions, Completed, Completion Rate %, Average Score, Total Messages
- **Feedback stats:** Total Feedback, Average Rating (1-5), With Comments count, Left Email count
- **Feature Usage table:** Sorted most-to-least used (simulation, debrief, offer_analyzer, etc.)
- **Scenario Popularity table:** Which scenario types are most used
- **Recent Feedback table:** Last 10 comments with timestamp, star rating, and comment text (truncated to 80 chars)

**JSON API:** Also available at `GET /api/admin/stats?key=YOUR_KEY` returning raw JSON.

**Is the data there?** Yes, assuming sessions have been run. The `AnalyticsTracker` tracks every API call via `_track()` and `_feature()` helper functions. Feature usage is counted per-category. Session creation, completion, scores, messages, debrief views, playbook generation, offer analysis, challenge completion, email audits, and earnings calculations are all tracked.

**Issue found:** The admin dashboard has no authentication beyond a query parameter key. The key is visible in browser history, server logs, and referrer headers. For a production deployment, this should use a proper auth header or session cookie.

---

## Summary of Findings

### What Works Well
- **Core negotiation loop** is solid. The rule-based engine produces varied, realistic responses based on persona style, pressure level, and transparency. Move classification (anchor, concession, question, BATNA signal, acceptance) works correctly.
- **Scoring system** is well-designed with 6 research-backed dimensions and appropriate weights. Coaching tips are specific and actionable.
- **Debrief reveal** is the product's strongest feature. Exposing the opponent's hidden constraints, reservation price, and move-by-move analysis provides genuine learning value.
- **UI polish** is high. Animations (count-up scores, bubble entry, bar fills), loading states (spinners, skeletons), keyboard shortcuts, toast notifications, print styles, and mobile responsive design are all implemented.
- **Accessibility** is decent: ARIA labels on buttons, role attributes on chat log, keyboard navigation with focus-visible styles.

### Broken or Non-Functional Features
1. **Opponent Tuner sliders have zero effect.** The 6 slider values are sent to the API but the Pydantic model drops them. The persona is determined solely by scenario type and difficulty.
2. **"Business Deal" and "Custom" scenario types silently default to salary.** The dropdown offers options the backend does not support.
3. **Email Audit context field is ignored.** The form collects context but the API call does not send it.
4. **demo_mode flag is ignored.** Sent but not processed.
5. **Frontend earnings calculator is disconnected from the more powerful backend version.** The backend includes retirement multiplier effects that are never surfaced.
6. **Daily challenge always creates salary scenario** regardless of challenge content.
7. **Feedback "thank you" shows on API failure.** False confirmation.

### UX Issues
1. **Privacy claim is misleading.** "Not stored beyond your conversation" but server persists everything to disk.
2. **Score history chart lacks X-axis labels.**
3. **Offer Analyzer market data enrichment unlikely to trigger** due to free-text role input not matching internal keys.
4. **10 scenario types exist but only 4 are exposed** in the frontend dropdown (salary, freelance, business, custom). Rent, medical bill, car buying, scope creep, raise, vendor, counter offer, and budget request personas exist but are unreachable through the UI.

### Architecture Notes
- **Pure Python, no LLM required.** The `RuleBasedSimulator` is a template-pool + decision-tree engine. The abstract `SimulatorBase` class is designed for LLM swap-in.
- **In-memory + file persistence.** Sessions are stored in a dict with file backup. Thread-safe via `threading.Lock`.
- **Rate limiting:** 100 requests/minute per IP, in-memory with periodic cleanup.
- **Security:** HTML escaping via `escapeHtml()` in frontend, UUID4 validation on session IDs, Pydantic input validation, CORS configuration. No authentication for user endpoints.
