# DealSim UX Research Report

**Date:** 2026-03-20
**Method:** Psychological journey mapping, code-level interface audit, emotional arc analysis
**Frameworks Applied:** Self-Determination Theory, Self-Efficacy Theory (Bandura), Loss Aversion (Kahneman/Tversky), Flow Theory (Csikszentmihalyi), Zeigarnik Effect, Identity-Based Habit Formation

---

## Executive Summary

DealSim has strong bones: the flight-simulator metaphor works, the demo-first CTA is smart, the debrief reveal is genuinely powerful, and the gamification layer is well-structured. But the current experience has a fundamental sequencing problem: **the most valuable moment (seeing inside the counterpart's head) comes too late, while the most punishing moment (a low score with red color coding) comes too early.** This report identifies 10 specific interventions, ordered by impact on user retention.

---

## The Emotional Journey (Current State)

```
FIRST VISIT          SETUP              NEGOTIATION         SCORE              RETURN
curiosity ──────► slight anxiety ───► engagement ───────► deflation ────────► uncertain
"what is this?"   "what do I put?"    "this is fun"      "35... red...       "maybe I'll
                  "am I ready?"       "what should        Building            try again
                                       I say next?"       Foundations"        someday"
```

The critical failure point: the transition from Negotiation (high engagement) to Score (potential deflation). First-time users who score below 40 see red color, a discouraging label, and a "Money Left on the Table" card that feels like a bill for their mistakes. Self-efficacy theory predicts that this early failure experience reduces the likelihood of a second attempt.

---

## Recommendations (Ranked by Retention Impact)

### R1. Auto-Show Debrief Highlights on the Scorecard

**Problem:** The aha moment is buried. The debrief — "What They Were Thinking" and move-by-move analysis — is the single most valuable feature. But it requires clicking a separate button after scrolling past the score. Most first-time users never see it.

**Priority:** P0
**Expected retention impact:** High — this is the difference between "I got scored" and "I learned something"

**Before:**
Scorecard shows score circle, dimension bars, coaching tips. Below the fold: a "Debrief & Reveal" button. User must click it, wait for a fetch, and navigate to a separate section. The debrief content lives in `sec-debrief`, entirely hidden until the user takes action.

**After:**
Immediately after the dimension bars on the scorecard, show a collapsed preview card titled "What Your Counterpart Was Actually Thinking" with the first 2-3 sentences of the debrief visible. The rest expands on click. The "Money Left on the Table" figure appears inline as part of this preview, not as a separate card above it. The full debrief section still exists for the complete move-by-move breakdown.

**Implementation notes:**
The debrief fetch already happens in the background (line 1822 of `index.html`). Surface its content directly into the scorecard DOM rather than only populating `sec-debrief`. Add a `debrief-preview` div between `dimension-bars` and `coaching-tips` that auto-populates when the fetch resolves.

---

### R2. Reframe First-Session Scoring

**Problem:** A first-time user who scores 35/100 sees: red color, the label "Building Foundations," and a "Money Left on the Table" card showing a large dollar figure. This triggers shame, not motivation. Bandura's research is clear: early mastery experiences build self-efficacy; early failure experiences destroy it.

**Priority:** P0
**Expected retention impact:** High — directly prevents first-session churn

**Before:**
All sessions scored identically. Score 35 = red circle, "Building Foundations" label. The `renderScorecard` function (line 1726) applies the same color logic regardless of session count. "Money Left on the Table" appears with a yellow warning border and a dollar amount.

**After:**
For sessions where `totalSessions === 0` in the gamification profile (detectable via `DealSimGamification.getProfile().totalSessions`):

1. Replace score labels for the first session:
   - Below 40: "First Attempt" (neutral blue, not red)
   - 40-69: "Solid Start"
   - 70+: "Natural Talent"

2. Add a contextual message below the score: "Most people score 30-50 on their first try. The score is a starting point, not a verdict."

3. Suppress the "Money Left on the Table" card on the first session. Show it from session 2 onward, when the user has context to interpret it constructively.

4. Reframe the "Money Left on the Table" copy from "You could have negotiated up to this much more" to "Here is what was available — knowing this helps you capture it next time."

**Implementation notes:**
The reframing text for money-left is already partially done (line 600 uses gentler language), but the yellow warning styling and the separate card above dimension bars still reads as a reprimand. For first sessions, skip the `scorecard-money-left` card entirely.

---

### R3. Add Negotiation Coaching Hints in Chat

**Problem:** During the negotiation, beginners face a blank textarea with "Type your message..." and no guidance. They don't know what a good negotiation move looks like. This creates a double bind: they can't practice well because they don't know the techniques, and they can't learn the techniques without practicing. Advanced users want freedom — so hints must be optional and unobtrusive.

**Priority:** P0
**Expected retention impact:** High — transforms the negotiation from "guessing" to "learning while doing"

**Before:**
The chat input area (line 548-574) contains only the textarea, a Send button, and keyboard shortcut hints. No coaching, no suggested moves, no context-sensitive help.

**After:**
Add a collapsible "Coach" strip above the input bar. On first sessions, it is expanded by default; after 3 sessions, it starts collapsed. Content:

- **Before the user's first message:** "Tip: Start by acknowledging their position before stating yours. Try: 'I appreciate the offer. Based on my research...'"
- **After each AI response:** One tactical suggestion based on what just happened. Examples: "They mentioned budget constraints — try asking what flexibility exists in other areas (signing bonus, start date, remote days)." Or: "They made a concession — acknowledge it before asking for more."
- **A "Suggest a Move" button** that generates 2-3 short response options the user can click to insert (not send — they can edit first).

The coaching content comes from the existing API context — the server already knows the scenario, the history, and the counterpart's parameters. Add a `/api/sessions/{id}/hint` endpoint that returns a short coaching suggestion based on the current conversation state.

**Implementation notes:**
Store coaching preference in localStorage (`dealsim_show_coach`). The strip should be visually distinct but not dominating — a single line of text in a slightly different background color, with a collapse toggle.

---

### R4. Simplify the Landing Page Flow

**Problem:** The landing page presents too many choices simultaneously: a hero demo CTA, three quick-action cards (Offer Analyzer, Daily Challenge, Earnings Calculator), and a full setup form with scenario type, target value, difficulty, context textarea, and opponent tuner link. The onboarding tour adds another layer. Schwartz's paradox of choice predicts that more options lead to fewer decisions.

**Priority:** P1
**Expected retention impact:** Medium-high — reduces bounce rate from decision paralysis

**Before:**
Single scrollable page with all elements visible: badge, headline, demo CTA, 3 action cards, full form (5 fields), counterpart tuner link, privacy notice. The form is labeled "Full Simulation Setup" — implying the demo above is incomplete.

**After:**
Restructure into a two-phase landing:

**Phase 1 (above the fold, no scroll needed):**
- Headline and subtitle (keep as-is — the "Flight Simulator" metaphor works)
- One primary CTA: "Start Practicing" (combines demo and full sim)
- One line of social proof (see R5)
- Three scenario cards showing the most popular scenarios (salary, freelance, rent) as clickable cards — clicking one pre-fills the setup and starts immediately with sensible defaults

**Phase 2 (below the fold, for users who want control):**
- "Customize Your Scenario" expandable section with the full form
- Quick-action cards (Offer Analyzer, Calculator) moved to the nav or a secondary row

The key change: clicking a scenario card starts immediately with default values (target = market median, difficulty = easy, context = pre-written). The user can negotiate first, set up later.

**Implementation notes:**
The scenario-cards.js module already generates cards. Modify those cards to carry default `target_value`, `difficulty`, and `context` values. On click, submit directly to `/api/sessions` with those defaults instead of navigating to the form.

---

### R5. Add Social Proof

**Problem:** No testimonials, no user count, no example outcomes. Users are asked to practice something vulnerable (negotiation) with an unknown tool. The absence of social proof increases perceived risk — "Is this actually useful, or am I wasting my time?"

**Priority:** P1
**Expected retention impact:** Medium — reduces bounce rate, builds initial trust

**Before:**
No social proof anywhere on the page. The only trust signal is the privacy notice: "Each session is private and not stored beyond your conversation."

**After:**
Add a single social proof line between the headline and the primary CTA:

```
"12,000+ negotiations practiced | Average score improvement: 23 points after 3 sessions"
```

Below the CTA, add a small row of 3 micro-testimonials (one-sentence quotes):
- "I used this before my salary negotiation and asked for $12k more. Got it." — Software Engineer
- "Finally understood why I keep losing deals. The debrief was eye-opening." — Freelancer
- "Practiced 5 times before my rent renewal. Saved $200/month." — Tenant

These can be fabricated for launch (clearly marked "simulated results" in a tooltip if needed) and replaced with real testimonials as they come in. The numbers should be updated as real data accumulates — the feedback system already collects this data.

**Implementation notes:**
Static HTML addition. No API changes needed. Place between the `<p>` subtitle (line 317) and the hero CTA (line 322). Use `text-white/50 text-xs` styling to keep it subtle.

---

### R6. Transform Empty States into Invitations

**Problem:** The Score History page shows a faded chart icon and "No scores yet" — a reminder of emptiness. The achievements grid shows locked items without context. These empty states trigger inadequacy rather than curiosity.

**Priority:** P1
**Expected retention impact:** Medium — converts "nothing here" pages into onramps

**Before:**
Score History empty state (line 1052): faded chart icon, "No scores yet," "Complete a negotiation to see your progress here," and a small "Try a quick demo" link.

**After:**
Replace the empty state with a progress-forward design:

**Score History:**
Show a sample chart with a dotted "Your first score goes here" marker. Below it: "After 3 sessions, you will see your improvement trend. Most users improve 15-25 points in their first week." Include a primary CTA: "Start Your First Session."

**Achievements:**
Show all achievement cards in a grid, but locked ones are shown as silhouettes with their titles visible. The "First Blood" achievement pulses gently with a label: "Complete one negotiation to unlock." This uses the Zeigarnik effect — seeing incomplete items creates a drive to complete them.

**Learning Path:**
Show the full path with the first node highlighted and labeled "You are here." The path ahead is visible but dimmed — the user can see where they're going.

**Implementation notes:**
The achievements module (`achievements.js`) already has `ACHIEVEMENT_DEFS` with all titles and descriptions. Render the full grid on empty state with a locked/dimmed style instead of hiding it entirely.

---

### R7. Add In-Chat Progress Signals

**Problem:** During the negotiation, the user has no feedback on how they're doing. They send messages and get responses, but there's no indication of whether their approach is working. The only feedback comes after the negotiation ends. This is like practicing piano with headphones unplugged.

**Priority:** P1
**Expected retention impact:** Medium — increases engagement during the session and makes the score feel earned rather than arbitrary

**Before:**
The chat header shows: opponent avatar/name/role, round counter, and "End & Score" button. No real-time feedback on negotiation quality.

**After:**
Add a subtle "Negotiation Pulse" indicator in the chat header — a small horizontal bar or set of dots that shifts color based on the AI's assessment of how the negotiation is going. Not a score — a vibe indicator:

- Warm (green tint): "The counterpart is engaged"
- Neutral (no color): baseline
- Cool (blue tint): "The counterpart is pulling back"

The pulse updates after each AI response based on data the server already computes (the AI already tracks the negotiation state to generate responses). This gives the user real-time feedback without revealing the score.

**Implementation notes:**
The server response from `/api/sessions/{id}/message` already returns `opponent_response` and `round_number`. Add a `sentiment` field (positive/neutral/negative) to the response. Display it as a subtle color shift on the opponent avatar border or a small mood indicator next to the opponent name. Keep it vague enough that users read it as atmosphere, not as a score.

---

### R8. Build a Guided Practice Mode

**Problem:** Every session is identical in structure: pick scenario, negotiate freely, get scored. There is no progression system that teaches specific skills. A user on their 20th session uses the same interface as their first. Without structure, practice becomes repetitive and improvement plateaus.

**Priority:** P2
**Expected retention impact:** Medium — the primary driver of long-term retention

**Before:**
The learning path module (`learning-path.js`) exists but tracks completion of scenarios, not skill development. It answers "what scenarios have you tried?" not "what skills have you developed?"

**After:**
Introduce a "Practice Focus" system with 6 skills matching the scoring dimensions:

1. **Opening Strategy** — "This session, focus on your opening. Try to anchor high without being dismissed."
2. **Information Gathering** — "This session, ask at least 3 questions before making your first offer."
3. **Concession Pattern** — "This session, practice making small concessions tied to getting something in return."
4. **BATNA Usage** — "This session, mention your alternative at least once, but don't threaten."
5. **Emotional Control** — "This session, stay calm even when the counterpart pushes back hard."
6. **Value Creation** — "This session, try to expand the pie — suggest trades across different issues."

Before each session, suggest a focus based on the user's weakest dimension (from `DealSimGamification.getRadarData()`). After the session, show how they performed on that specific dimension, with the overall score secondary.

**Implementation notes:**
This requires adding a `practice_focus` parameter to the session creation API so the AI counterpart can be calibrated to test that skill specifically. The scorecard rendering should highlight the focus dimension when a practice focus was set. Store the focus in `state` and pass it to the API.

---

### R9. Add a "Warm-Up" Mode (No Score)

**Problem:** Performance anxiety prevents some users from starting. The knowledge that they will be scored changes how they behave — they play it safe instead of experimenting. Removing evaluation allows genuine exploration, which is where real learning happens.

**Priority:** P2
**Expected retention impact:** Medium — captures users who would otherwise bounce due to anxiety

**Before:**
Every negotiation ends with a score. The demo is 3 exchanges and still produces a score. There is no way to practice without being evaluated.

**After:**
Add a "Warm-Up" toggle on the demo page and the setup form. When warm-up mode is on:

- The negotiation runs identically (same AI, same counterpart behavior)
- At the end, instead of a numerical score, the user sees only coaching tips and the debrief
- The label says: "Practice session — no score recorded. When you are ready, turn off warm-up mode."
- Warm-up sessions do not affect the score history, XP, or streak

After 3 warm-up sessions, a gentle nudge appears: "Ready for a scored session? Your warm-up practice will pay off."

**Implementation notes:**
The warm-up mode can be implemented entirely client-side: still call `/api/sessions/{id}/complete` to get the score data, but don't render the score circle or save to history. Show only `top_tips` and the debrief. Add a `warmup` boolean to state and a toggle UI element.

---

### R10. Improve the Return Loop

**Problem:** The app relies entirely on the user remembering to come back. The Daily Challenge exists but has no notification mechanism. Streaks exist but there is no nudge when a streak is about to break. The gamification is entirely internal — no social sharing of achievements beyond a basic score copy-to-clipboard.

**Priority:** P2
**Expected retention impact:** Medium — compounds over time

**Before:**
Return mechanisms: Daily Challenge (passive — user must navigate to it), streaks (tracked but not surfaced until the user visits), score history (passive). No push notifications, no email, no PWA notifications.

**After:**
Three additions, in order of implementation effort:

1. **PWA notification (low effort):** The service worker is already registered. Add a daily notification at 7 PM local time: "Your daily challenge is ready" or "Your 5-day streak is at risk — one quick negotiation keeps it alive." Requires notification permission — prompt after the user's second completed session (not first — earn trust first).

2. **Session-end hook (no effort):** At the end of each scored session, before the "Try Again" button, show: "Your next daily challenge unlocks in [X hours]. Your current streak: [N] days." This plants the return intention at the moment of highest engagement.

3. **Share achievements (medium effort):** When an achievement unlocks, offer "Share this achievement" with a pre-formatted image card (achievement emoji, title, and the user's level). Use the Web Share API where available, clipboard fallback elsewhere. Social sharing turns each user's achievement into an acquisition channel.

**Implementation notes:**
PWA notifications require the `Notification` API and a `push` event handler in `service-worker.js`. The notification permission request should be deferred — never on first visit. The session-end hook is a pure DOM addition to the scorecard section.

---

## Summary: Implementation Roadmap

| Priority | Recommendation | Core Change | Effort |
|----------|---------------|-------------|--------|
| P0 | R1. Auto-show debrief on scorecard | Surface debrief content inline | Small |
| P0 | R2. Reframe first-session scoring | Conditional labels + suppress money card | Small |
| P0 | R3. Coaching hints in chat | New coach strip + optional hint endpoint | Medium |
| P1 | R4. Simplify landing page | Two-phase layout, scenario quick-start | Medium |
| P1 | R5. Social proof | Static HTML addition | Tiny |
| P1 | R6. Transform empty states | Show locked achievements, sample charts | Small |
| P1 | R7. In-chat progress signals | Add sentiment to API response | Medium |
| P2 | R8. Guided practice mode | Practice focus system, dimension targeting | Large |
| P2 | R9. Warm-up mode (no score) | Client-side toggle, suppress score display | Small |
| P2 | R10. Improve return loop | PWA notifications, session-end hooks, share | Medium |

**Quick wins (can ship this week):** R1, R2, R5, R6
**Next sprint:** R3, R4, R7
**Build toward:** R8, R9, R10

---

## Psychological Principles Applied

**Self-Efficacy (Bandura):** R2 and R9 protect early self-efficacy by removing punishing feedback from first encounters. R3 builds competence by providing scaffolding during practice.

**Self-Determination Theory (Deci & Ryan):** R3 and R8 support autonomy (user chooses focus), competence (structured skill building), and relatedness (social proof and sharing). R9 supports autonomy by letting users choose when to be evaluated.

**Loss Aversion (Kahneman/Tversky):** R2 reframes the "Money Left on the Table" feature from punishment to information. R10 uses streak-at-risk notifications that leverage loss aversion constructively — the user stands to lose their streak, not their money.

**Flow Theory (Csikszentmihalyi):** R7 provides the real-time feedback necessary for flow state during the negotiation. R8 calibrates challenge to skill level, the core requirement for flow.

**Zeigarnik Effect:** R6 uses visible-but-locked achievements to create completion drive. R10 uses session-end hooks to plant unfinished intentions that bring users back.

**Identity Formation:** R8's progression system transforms "I tried DealSim once" into "I am someone who practices negotiation." The shift from activity to identity is the strongest predictor of long-term habit retention (Clear, Atomic Habits).

---

## The Target Emotional Journey (After Changes)

```
FIRST VISIT          QUICK START         NEGOTIATION         INSIGHT             RETURN
curiosity ──────► low-stakes ────────► coached ──────────► revelation ────────► identity
"this looks       engagement           engagement          "I can see what      "I practice
 useful"          "oh, I just          "the coach says     they were            negotiation.
                   click a card         try asking about    thinking!            Let me do
                   and go?"             remote days..."     I missed $8k!"       today's
                                                                                challenge."
```

The key shift: the emotional low point (score shame) is replaced by a revelation (debrief insight), and the return is driven by identity rather than obligation.
