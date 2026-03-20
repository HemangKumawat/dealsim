# DealSim Conversion Funnel Audit

**Date:** 2026-03-19
**Scope:** Full user journey from landing to retention, based on `static/index.html` and `api/routes.py`

---

## Funnel Map

```
Landing Page ──> Instant Demo (0-signup) ──> Demo Score
     │                                          │
     │                                   "Full Simulation" CTA
     │                                          │
     ▼                                          ▼
 Full Setup Form ──> Chat Negotiation ──> Scorecard
                                              │
                                     ┌────────┼────────┐
                                     ▼        ▼        ▼
                                 Debrief   Playbook  Feedback
                                     │        │
                                     ▼        ▼
                                 Share    Return (History / Daily Challenge)
```

---

## Step 1: Landing Page

**What the user sees first:**
- Badge: "AI-Powered Negotiation Training"
- Headline: "DealSim -- The Flight Simulator for Negotiations"
- Subhead: "Practice any negotiation against a calibrated AI opponent. Get scored. Get better."
- A large "Try a 60-Second Negotiation" CTA (coral glow, full-width)
- Three quick-action cards: Offer Analyzer, Daily Challenge, Earnings Calculator
- Below the fold: Full Simulation Setup form (scenario, target, difficulty, context)

**Time to first interaction:** Under 2 seconds. The instant demo CTA is above the fold and visually dominant. No signup, no email gate.

**Drop-off risk:** LOW. The demo CTA is prominent and zero-friction. The setup form below it could cause decision fatigue ("should I demo or set up a full sim?"), but the visual hierarchy correctly prioritizes the demo.

**Missing CTA:** No social proof. No "10,000 negotiations run" counter, no testimonial, no logo bar. First-time visitors have zero credibility signals.

**Fix:**
- Add a single-line social proof element between the headline and the demo CTA: "2,400+ negotiations practiced this week" (even a placeholder that updates from analytics).
- Add a 3-second auto-playing micro-animation or screenshot of the chat interface to show what the experience looks like before clicking.

---

## Step 2: Instant Demo

**Does it work without signup?** YES. The demo fires `POST /api/sessions` with hardcoded params (salary, $95k target, medium difficulty, canned context). No auth, no email, no account.

**Clicks to start:** TWO. Click "Try a 60-Second Negotiation" on landing, then click "Start Demo" on the demo page.

**Drop-off risk:** MEDIUM. The intermediate "Start Demo" button on `sec-demo` is redundant friction. The user already clicked a CTA that said "Try a 60-Second Negotiation" -- showing them another screen that explains the same thing before they can actually start adds a bounce point.

**Broken flow:** None technically, but the scenario text ("You just got a job offer for $85,000...") is displayed BEFORE the user clicks Start Demo. This is good context-setting but the two-step pattern is unnecessary.

**Fix:**
- Auto-start the demo session when the user navigates to `sec-demo`. Show the scenario text as the first "system message" in the chat, not as a separate card. This collapses two clicks into one.
- If the API call takes time, show a skeleton chat with the scenario text immediately and a typing indicator for the opponent's opening.

---

## Step 3: Full Simulation (Demo to Full Sim Transition)

**Transition path:** After the demo ends, the user sees their score and two buttons: "Full Simulation" (coral, primary) and "Try Again" (outlined, secondary).

**Is context preserved?** NO. Clicking "Full Simulation" navigates to `sec-landing` (the setup form) with all fields empty. The user must re-enter scenario type, target value, difficulty, and context from scratch. The demo's context ($85k offer, market rate, competing offer) is discarded.

**Drop-off risk:** HIGH. This is the single biggest conversion leak in the funnel. The user just completed a demo, got emotionally invested in a score, and now faces a cold form. The momentum dies.

**Fix:**
- Pre-populate the setup form with the demo's parameters when coming from demo: scenario_type=salary, target_value=95000, difficulty=medium, context pre-filled with the demo scenario.
- Better: add a "Continue with a harder version" button that skips the form entirely and starts a 10-round version of the same scenario at hard difficulty.
- Best: after demo score, show a choice card: "Same scenario, more rounds" vs "New scenario" -- both should be one-click starts.

---

## Step 4: Scorecard

**Is the score motivating?** MOSTLY. The score display is well-designed:
- Large circular score with color coding (green 70+, yellow 40-69, red <40)
- Count-up animation creates anticipation
- Labels ("Outstanding", "Strong Performer", "Developing", "Needs Practice") give emotional framing
- "Money Left on the Table" yellow card creates a visceral dollar-amount hook

**Drop-off risk:** MEDIUM. The scorecard has too many CTAs competing for attention:
1. Debrief & Reveal button
2. Playbook button
3. Feedback form (5 stars + comment + email)
4. Share Your Score button
5. Try Again button

Five actions on one screen creates decision paralysis. The feedback form is especially problematic -- it sits between the high-value actions (debrief/playbook) and the re-engagement action (try again).

**Missing CTA:** No "Beat your score" framing. No comparison to average scores. No streak counter.

**Fix:**
- Reorder the scorecard: Score display > Money Left on Table > Debrief CTA (primary, full-width) > Try Again (secondary). Move feedback to a delayed modal (already implemented but also duplicated inline).
- Remove the inline feedback form entirely. The modal trigger at 15 seconds post-score (line 1637) is sufficient and less intrusive.
- Add "Average score: 52" or "Top 30% of negotiators" to create competitive motivation.
- Add "You improved by +12 points since last time" when history exists.

---

## Step 5: Debrief ("What They Were Thinking")

**Does it create the aha moment?** YES, strongly. The debrief reveals:
- Opponent's hidden target price and reservation price
- Opponent's pressure points
- Hidden constraints the user did not know about
- Outcome grade
- Move-by-move analysis with "missed opportunity" callouts
- Best move and biggest mistake identification
- Key moments

This is the highest-value content in the entire product. Seeing "their target was $X and you settled at $Y" is the kind of insight that makes users say "I need to try again."

**Drop-off risk:** LOW for users who reach this screen. The content is inherently engaging.

**Broken flow:** The debrief is gated behind a button click on the scorecard. Users who skip it miss the product's core value proposition.

**Fix:**
- Auto-expand the "Money Left on Table" and "What They Were Thinking" summary directly on the scorecard (collapsed/teaser with "See full debrief" to expand). Do not require a separate page navigation.
- The debrief data is already fetched asynchronously on scorecard render (line 1622). Use this to inject a 2-3 line teaser directly into the scorecard: "They were willing to go up to $X. You left $Y on the table."

---

## Step 6: Playbook

**Is it clearly positioned as worth paying for?** NO. The playbook is currently free, identical in access to the debrief. It contains:
- Style profile ("Your Negotiation Style")
- Strengths and weaknesses
- Prioritized recommendations with categories
- Practice scenarios

This content is high-value but not differentiated from the free experience. There is no paywall, no premium tier, no upsell.

**Drop-off risk:** N/A (no paywall exists).

**Fix:**
- The playbook is the natural paywall insertion point. Free users should see the first 2 items (style profile + strengths) and a blurred/locked section for recommendations and practice scenarios.
- CTA: "Unlock your full playbook -- $4.99" or "Get unlimited playbooks with DealSim Pro."
- The print/copy buttons signal high perceived value. Keep these for paid users.

---

## Step 7: Share

**Can users share their results?** YES, via clipboard copy. `shareScore()` constructs a text string: "I scored X/100 on DealSim's negotiation simulator! [outcome]. [money left]. Try it: [URL]"

**Is it frictionless?** PARTIALLY. It copies to clipboard and shows a toast, but there are no direct share-to-platform buttons (Twitter/X, LinkedIn, WhatsApp). For a product targeting professionals, LinkedIn share is particularly important.

**Missing:** No shareable image/card. A visual scorecard image (canvas-rendered or server-generated) would be far more shareable than plain text. No unique share URL (e.g., `dealsim.com/score/abc123` that shows a public scorecard).

**Fix:**
- Add LinkedIn and Twitter/X share buttons with pre-filled text and the site URL.
- Generate a score card image (use canvas or a server endpoint) that shows the score, outcome, and "Money Left on Table" in a branded format.
- Create a `/share/{id}` route that renders a public-facing mini scorecard (server-side rendered, works as a link preview).

---

## Step 8: Return Mechanisms

**What pulls users back?**

| Mechanism | Implemented | Effective |
|-----------|------------|-----------|
| Score History (localStorage) | Yes | Weak -- no push/pull, user must remember to visit |
| Daily Challenge | Yes | Moderate -- new challenge daily, but no notification |
| Streak tracking | No | Missing entirely |
| Email capture | Yes (feedback form) | Weak -- optional, no drip campaign |
| Push notifications | No | Missing |
| Score comparison/leaderboard | No | Missing |

**Drop-off risk:** HIGH. There is no active re-engagement mechanism. The daily challenge exists but has no notification system. Score history is passive (localStorage only, no server persistence).

**Fix (priority order):**
1. Add a streak counter on the landing page: "3-day streak" with a fire emoji. Track in localStorage. This is the single cheapest retention mechanism.
2. After the email is captured in feedback, trigger a "Your daily challenge is ready" email at 9 AM. This requires a backend email service but is the highest-ROI retention feature.
3. Add "Challenge a friend" -- generate a share link that includes the scenario, so the friend negotiates the same scenario and scores are compared.
4. Show "Your best: 78, Average: 52" on the landing page when history exists.

---

## Step 9: Upgrade / Paywall

**Where is the paywall?** NOWHERE. The entire product is free. Every feature -- demo, full sim, debrief, playbook, offer analyzer, email audit, earnings calculator, daily challenges -- is accessible without payment.

**Is this the right moment?** The product currently has no monetization layer at all. This means either it is pre-revenue (intentional) or the paywall has not been implemented yet.

**Optimal paywall placement (if implementing):**

| Gate point | What is locked | Conversion logic |
|-----------|---------------|-----------------|
| After 3rd session | Full debrief + playbook | User has experienced value, formed habit |
| Playbook section | Recommendations + practice scenarios | Tease style profile free, lock actionable content |
| Offer Analyzer | Counter strategies | Show components free, lock counter strategies |
| Daily Challenge scoring | Detailed breakdown | Show total score free, lock criterion-by-criterion |

**Fix:**
- Implement a session counter (`dealsim_session_count` already exists in localStorage, line 1634). After session 3, show a soft gate: "You've completed 3 negotiations. Unlock unlimited sessions + full playbooks for $9/month."
- Keep the demo permanently free. Keep the first full simulation free. Gate at session 3+.
- The earnings calculator should always be free -- it is a top-of-funnel awareness tool that motivates negotiation practice.

---

## Step 10: Feedback Modal

**Trigger timing:** The feedback modal fires 15 seconds after the scorecard renders, but ONLY on the 2nd+ session (line 1636: `if (sessionCount >= 2)`).

**Is this the right time?** MOSTLY. Triggering after the 2nd session means the user has shown commitment. 15 seconds gives them time to absorb their score. However:

**Issues:**
- The inline feedback form on the scorecard AND the modal are redundant. Both ask for stars + comment. A user who submits inline feedback will still get the modal popup 15 seconds later.
- The modal has no dismiss-and-don't-ask-again mechanism. It will trigger every session after the 2nd.
- The feedback form asks for email but does not explain what it will be used for ("Email for updates" is vague).

**Fix:**
- Remove the inline feedback form from the scorecard. Keep only the modal, triggered at 15 seconds after the 2nd session.
- After the user submits feedback once via the modal, set `localStorage.setItem('dealsim_feedback_given', 'true')` and stop showing the modal. If you want ongoing feedback, re-trigger only after every 5th session.
- Change "Email for updates" to "Get your playbook by email (we send 1 tip per week, unsubscribe anytime)." This frames the email capture as value delivery, not data collection.

---

## Summary: Top 5 Conversion Fixes by Impact

| Priority | Fix | Funnel stage | Expected impact |
|---------|-----|-------------|----------------|
| 1 | Pre-populate setup form from demo context | Demo -> Full Sim | Eliminates the biggest drop-off point |
| 2 | Auto-start demo (remove intermediate "Start Demo" click) | Landing -> Demo | Reduces time-to-value by 3-5 seconds |
| 3 | Inject debrief teaser into scorecard (no separate page) | Scorecard -> Debrief | Ensures every user sees the aha moment |
| 4 | Add streak counter + "beat your score" on landing | Return visits | Only zero-cost retention mechanism |
| 5 | Add social proof line below headline | Landing page | Builds trust for first-time visitors |

---

## Revenue Readiness Assessment

The product is feature-complete for a free tier but has zero monetization infrastructure. Before adding a paywall:

1. The session counter exists (`dealsim_session_count`) but is only used for feedback timing. Repurpose it as a gate trigger.
2. User identity does not exist. `user_id` is optional and empty by default. A paywall requires either accounts or a payment-per-session model.
3. The API has no auth middleware. All endpoints are open. A paywall on the frontend alone is trivially bypassable.
4. Server-side session storage appears to be in-memory (no database referenced in routes). Sessions do not persist across server restarts, making subscription tracking impossible without a persistence layer.

**Recommendation:** Ship the free product, measure activation (demo starts, full sim completions, debrief views), and add monetization after confirming the core loop works. The funnel structure is sound -- the gaps are in conversion optimization, not architecture.
