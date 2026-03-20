# DealSim UX Review - Week 2
**Date:** 2026-03-19
**Reviewer lens:** Behavioral psychology / UX design
**File reviewed:** `static/index.html` (2,102 lines, single SPA)

---

## 1. First-Time User Experience

### Time to First Interaction: ~3-5 seconds (P1)

The landing page loads with a badge, headline, subheadline, four quick-action cards, and a full setup form all visible at once. A first-time user sees the value proposition ("Flight Simulator for Negotiations") quickly, but faces a **decision paralysis** problem: four quick-action cards PLUS a full form below them. The eye has no single dominant call to action.

**The "Instant Demo" card is the most important element for a first-time user** but it sits in a 4-card grid at equal visual weight with Offer Analyzer, Daily Challenge, and Earnings Calculator. A new user does not know what any of these are yet.

- **P0** The Instant Demo should be visually dominant for first-time visitors. Consider: hero-level CTA ("Try a 60-second negotiation - no signup") with the setup form collapsed behind a "Custom Scenario" toggle. The current layout asks first-timers to fill out a form before they understand what the product does.
- **P1** The four action cards use abstract labels ("Offer Analyzer", "Earnings Calc") that mean nothing to someone who just arrived. Add one-line descriptions under each, e.g., "Paste an offer, get leverage points."
- **P2** No onboarding tooltip or guided tour. A first-time user gets zero explanation of what a "Target Outcome" means in context.

### "Aha Moment": Delayed (P0)

The aha moment should be: "I just negotiated with an AI and it told me what I did wrong." Currently this requires either (a) clicking Instant Demo then completing 3 exchanges, or (b) filling out the setup form and going through a full simulation. Path (a) is the fastest route at roughly 90 seconds. Path (b) takes 3+ minutes of setup before the user sees any AI interaction.

- **P0** The Instant Demo is the right vehicle for the aha moment, but it requires a click to navigate to a separate section, then another click to "Start Demo." That is two clicks before any value. Consider auto-starting the demo scenario on a single button press from the landing page, or showing the demo scenario inline.

---

## 2. Emotional Design

### Scorecard Emotional Arc: Mostly Right (P1)

The scorecard uses a traffic-light color system (emerald/yellow/coral) with labels "Outstanding," "Strong Performer," "Developing," "Needs Practice." The score pops in with a satisfying animation (`scorePop`). This is well-designed.

**Issues:**
- **P1** "Needs Practice" for sub-40 scores is appropriately gentle, but the large coral-colored number with no positive framing could feel demoralizing. Add a single line of encouragement below low scores: "Most people score 30-50 on their first try. Each session builds real skill."
- **P1** The dimension bars show raw numbers without context. A user who scores 35 on "BATNA Usage" does not know if that is fixable in one conversation or a deep skill gap. Consider adding micro-labels ("Common gap - try mentioning alternatives early").
- **P2** The coaching tips are text-only. A single highlighted "Focus on this next time" tip, visually separated from the rest, would create a clearer action takeaway.

### "Money Left on Table": Strong but Needs Guardrails (P1)

- **P1** The yellow `$X,XXX` number creates urgency effectively. However, when the AI opponent's hidden reservation price is generous and the gap is large, the number can feel crushing rather than motivating. Add a percentile or comparison: "You captured 72% of the available value" reframes the same information as partial success rather than pure loss.
- **P2** The static text "You could have negotiated up to this much more" does not change based on the actual amount. A $500 difference and a $15,000 difference get the same framing. Dynamic copy would help: "$500 - nearly there" vs "$15,000 - significant room to improve."

### Debrief Framing: Empowering (Good)

The "What They Were Thinking" section and move-by-move analysis are well-structured. Revealing the AI's internal reasoning creates a coach-like dynamic rather than a judge-like one. The back-to-scorecard navigation is clear.

---

## 3. Friction Points & Drop-Off Risks

### Setup Form: Too Much for Cold Traffic (P0)

The landing form asks for: Scenario Type (dropdown), Target Outcome (number), Difficulty (3 buttons), Describe the Situation (textarea, 4 rows), plus an optional Opponent Tuner link. This is **five fields before the user has experienced any value**.

- **P0** The biggest drop-off risk is this form. A user who clicked "Full Simulation Setup" must provide a target number and describe a situation. Many users will not know what to write in the context field and will bounce. Provide 3-4 clickable scenario templates ("Salary negotiation - you got an offer for $85k", "Freelance rate - client wants a discount") that auto-fill the form.
- **P1** "Your Target Outcome (e.g. 95000 for a salary)" - the parenthetical hint is helpful but the field accepts any number with no validation feedback. Entering "95000" vs "$95,000" vs "ninety five" all hit the same `type="number"` field. Add a currency prefix or format hint inside the input.
- **P2** The "Tune Opponent Persona" link navigates to a full separate section with 6 sliders. This is a power-user feature buried in the setup flow. It should be a collapsible panel within the form, not a section switch.

### Chat Section: Low Friction (Good)

The chat interface is clean. Enter to send, Shift+Enter for newline, typing indicator, round counter, and an "End & Score" button. Minimal cognitive load. This is the strongest UX section.

- **P1** No indication of recommended conversation length. A user might send 2 messages or 20. Add a subtle nudge after 3-4 rounds: "You can continue or end and get scored."
- **P2** The "End & Score" button is small and positioned in the header. Users deep in conversation might miss it. Consider a floating prompt after round 5+.

### Offer Analyzer: Validation Gap (P1)

- **P1** The form requires "Full Offer Details" (textarea) but silently accepts empty Role, Salary, Bonus, Equity, and Location fields. If a user only pastes text and leaves the structured fields blank, the analysis quality may suffer. Either make key fields required or add a "For best results, fill in the salary" hint.
- **P2** The "Practice Negotiating This Offer" button at the bottom of analysis results is a strong conversion funnel, but it auto-fills the setup form and navigates away. The user loses their analysis view. Consider opening the setup in a modal or keeping the analysis accessible.

### Navigation: Confusing Section Proliferation (P1)

- **P1** The nav bar shows: Setup, Demo, Offers, Audit, Calculator, History. The mobile menu adds Opponent Tuner and Daily Challenge. That is 8 sections for what is fundamentally a 3-step product (setup, negotiate, review). New users do not need to see Audit, Calculator, or History until they have completed at least one session. Consider progressive disclosure: show only Demo and Setup initially, reveal other tools after the first completed negotiation.
- **P1** The desktop nav does not include "Opponent Tuner" or "Daily Challenge" but the mobile menu does. This inconsistency means features are discoverable on mobile but invisible on desktop.

---

## 4. Retention Mechanics

### Score History: Present but Passive (P1)

Score history is stored in localStorage and rendered as a line chart + list. This is functional but does not create a "pull" to return.

- **P1** No streak counter or session frequency indicator. Adding "3-day streak" or "5 negotiations completed" creates variable-ratio reinforcement. This is the single cheapest retention feature to add.
- **P1** No comparison to previous score. When a user completes their second negotiation, the scorecard should say "Score: 62 (up 14 from your last session)." This turns an abstract number into a progress signal.
- **P2** The chart is custom-drawn on canvas, which is clean, but it has no hover/click interaction. Users cannot tap a dot to see that session's details.

### Daily Challenge: Good Concept, Weak Hook (P1)

- **P1** Only 7 challenges exist in `DAILY_CHALLENGES`. After a week, they repeat. The deterministic index `(year*1000 + month*31 + date) % 7` means a returning user on day 8 sees the same challenge as day 1. This kills the "come back tomorrow" motivation. Expand to 30+ challenges or add procedural variation.
- **P1** "Challenge completed today!" is shown but there is no reward, badge, or score comparison. The completion state is binary (done/not done). Show the score achieved and a "beat your score" option.
- **P2** Daily Challenge is only discoverable via the landing page cards or mobile menu. No push mechanism (email, notification) exists to bring users back.

### Missing: Session Summary / Shareable Result (P0)

- **P0** After a negotiation, there is no way to share results. A shareable scorecard image ("I scored 78 on DealSim - try it") is the single highest-impact viral loop for a product like this. Even a "Copy result" text button would help.

---

## 5. Missing QoL Features (Quick Wins)

### P0 (Fix Before Launch)

1. **Scenario templates on the setup form.** Three clickable cards that pre-fill the form. Eliminates the blank-textarea problem. (~4 hours)
2. **"First time? Try the 60-second demo" prominent CTA** above or instead of the form for users with no localStorage history. (~2 hours)
3. **Share/copy scorecard result.** Text-based at minimum: "I scored 78/100 on DealSim's salary negotiation sim." (~3 hours)
4. **Loading state for demo start.** Clicking "Start Demo" calls the API but shows no loading indicator. On slow connections, the user sees nothing happening. (~30 min)

### P1 (Fix Week 1)

5. **Score delta on scorecard.** "62 (+14 from last session)" when history exists. (~1 hour)
6. **Tooltips on dimension bars.** Hover/tap to see "BATNA Usage: How well you leveraged your alternatives." (~2 hours)
7. **Session count badge.** "Negotiation #4" shown somewhere persistent. (~1 hour)
8. **Empty state for playbook/debrief when accessed directly.** Currently shows stale placeholder text. Should show "Complete a negotiation first" with a CTA button. (~1 hour)
9. **Form auto-save.** If a user partially fills the setup form and navigates away (to Offer Analyzer, etc.), their text is lost on return. Save to sessionStorage. (~1 hour)
10. **Error recovery in chat.** "Connection error. Is the API running?" is a developer message, not a user message. Replace with "Something went wrong. Try sending again." with a retry button. (~1 hour)

### P2 (Nice to Have)

11. **Keyboard shortcut hints** beyond the chat input. E.g., Escape to go back.
12. **Confetti or micro-animation** on scores above 80. Reinforces high performance.
13. **"What would you have done differently?" prompt** after debrief. Metacognitive reflection improves learning transfer.
14. **Print stylesheet for scorecard**, not just playbook. Users may want to print their full results.

---

## 6. Accessibility

### Color Contrast (P0)

- **P0** Body text uses `text-white/60` (approximately `rgba(255,255,255,0.6)`) on `#1a1b4b` background. This yields a contrast ratio of roughly 4.2:1, which barely passes WCAG AA for normal text but fails for small text (the `text-xs` and `text-sm` elements throughout). Labels like "Tap a star to rate" at `text-white/40` (~2.8:1) fail WCAG AA entirely. Raise all body text to at least `text-white/70` and all secondary text to `text-white/50` minimum.
- **P0** The coral color (`#f95c5c`) on navy background (`#1a1b4b`) has a contrast ratio of approximately 4.5:1, which passes AA for large text but fails for the small `text-sm` error messages and labels that use it. Ensure coral-on-navy is only used for large/bold text or increase the coral brightness for small text.
- **P1** Score color coding (emerald/yellow/coral) conveys meaning through color alone. Add text labels or icons for colorblind users. The label text ("Outstanding", "Developing") partially addresses this, but the dimension bars rely purely on color.

### Keyboard Navigation (P1)

- **P1** Difficulty selector buttons (`diff-btn`) use `onclick` handlers on `<button>` elements, which is keyboard-accessible. Good.
- **P1** Star rating buttons are keyboard-focusable but have no visible focus indicator beyond the browser default. Add a focus ring style.
- **P1** Section navigation is entirely click-driven with no keyboard shortcuts. Tab order flows through nav links, which is acceptable but not optimal. The chat input correctly focuses after actions.
- **P2** The mobile menu hamburger button is keyboard-accessible. The menu dismiss (clicking outside) is not — add Escape key handler.

### Screen Reader Compatibility (P1)

- **P1** No ARIA labels on interactive elements. The star rating buttons are just Unicode star characters with no `aria-label`. A screen reader would announce "star star star star star" with no context. Add `aria-label="Rate 1 out of 5"` etc.
- **P1** The difficulty selector has no `role="radiogroup"` or `aria-pressed` states. Screen readers cannot distinguish selected from unselected.
- **P1** Section switching (`showSection`) does not announce the new content. Add `aria-live` regions or manage focus to the new section heading.
- **P1** Chat messages have no `role="log"` or `aria-live="polite"` on the container. New messages from the AI opponent will not be announced.
- **P2** The score circle animation (`score-pop`) has no `aria-label`. The score number inside it is readable but the surrounding context (color, label) should be grouped with `aria-describedby`.

### Mobile Responsiveness (P1)

- **P1** The layout uses responsive Tailwind classes (`sm:` breakpoints) throughout. Grid goes from 2-col to 4-col on desktop for action cards, which is good. However, the setup form textarea and the chat messages area have no max-width constraint on very wide screens beyond `max-w-2xl` / `max-w-3xl`, which is acceptable.
- **P1** The Offer Analyzer's 2-column grid (`grid-cols-2`) does not collapse on very narrow screens (below 375px). Inputs could overflow. Add `grid-cols-1 sm:grid-cols-2`.
- **P2** Chat bubbles use `max-w-[75%] sm:max-w-[60%]` which is fine, but on very small screens, the text becomes cramped. Consider `max-w-[85%]` on mobile.
- **P2** Range slider thumb size (18px) is small for touch targets. WCAG recommends 44px minimum touch target. Increase to at least 24px with a larger hit area.

---

## Summary: Top 5 Priorities Before Launch

| # | Issue | Priority | Impact | Effort |
|---|-------|----------|--------|--------|
| 1 | Instant Demo should be the hero CTA, not buried in a grid | P0 | Halves bounce rate for new visitors | 4h |
| 2 | Setup form needs clickable scenario templates | P0 | Eliminates blank-form drop-off | 4h |
| 3 | Color contrast failures on secondary text | P0 | Legal/accessibility compliance | 2h |
| 4 | Shareable scorecard result | P0 | Only viral mechanism the product has | 3h |
| 5 | Demo "Start" button has no loading state | P0 | Users think click did nothing | 30m |
