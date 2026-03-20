# DealSim UX Psychology Audit

Reviewed: 2026-03-20
Scope: All static/ modules — gamification, learning path, achievements, celebrations, daily challenges, onboarding, scenario cards, quick match, engine peek, stats bar, and the main index.html.

---

## 1. Goal Gradient Effect

**Current state:** The learning path (`learning-path.js`) renders 8 milestones as a horizontal track with completed/current/future states. The XP bar in the stats bar shows level progress. Both are linear and uniform — there is no acceleration as the user approaches a milestone.

**What works:**
- The pulsing animation on the "current" milestone node draws attention to the next goal.
- The XP track in the stats bar gives persistent visibility of progress.

**What is missing:**
- Progress indicators do not accelerate. A user at 90% toward the next level sees the same visual weight as a user at 10%. The goal gradient effect predicts that motivation spikes when the finish line is visible and close.
- The learning path milestones are evenly spaced visually regardless of how close the user is to completion. A user one point away from "Reading the Room" (50+ Information Gathering) sees the same dashed connector as someone who has never tried.

**Recommendations:**
1. **XP bar acceleration cue.** When xpProgress > 0.75, add a subtle glow or color shift to the XP fill bar (e.g., transition from accent to a brighter variant). This signals "you're almost there" without adding text.
2. **Learning path proximity indicator.** For the "current" milestone, show a small text like "2 pts away" or a micro-progress ring inside the circle node, so the user sees concrete distance to the next milestone.
3. **"Almost there" nudge.** When a dimension score is within 5 points of unlocking the next milestone, surface a one-line message on the scorecard: "You're 3 points from unlocking Standing Ground." This converts awareness into motivation.
4. **Endowed progress.** Consider starting the XP bar at 10-15% for new users (award XP just for setting up their first scenario). This exploits the endowed progress effect — people are more likely to complete a task they feel they have already started.

---

## 2. Variable Rewards

**Current state:** The reward schedule is mostly predictable. XP formula: `score * 2 + streak bonus (25) + personal best bonus (100)`. Achievements are fixed milestones. Daily challenges rotate but award a flat +50 XP.

**What works:**
- The "Comeback Kid" achievement (score 70+ after scoring below 30) is a genuinely variable reward — it cannot be planned for, only discovered.
- Different opponent styles per negotiation introduce variability in the experience itself.

**What is missing:**
- Rewards are entirely deterministic. Once a user understands the formula, every session feels the same from a reward standpoint. Variable ratio schedules (unpredictable rewards at unpredictable intervals) are the strongest drivers of habit formation.
- Daily challenges have a fixed bonus value. There is no element of surprise in what you earn.

**Recommendations:**
1. **Random XP multiplier.** On roughly 1-in-5 sessions, apply a 1.5x or 2x XP multiplier with a brief visual ("Double XP!"). The unpredictability creates anticipation. Keep the base rate stable so users do not feel cheated on normal sessions.
2. **Hidden achievements.** Add 3-4 achievements that are not visible in the locked grid — they only appear when unlocked. Examples: "Night Owl" (negotiate after 11 PM), "Speed Demon" (complete a negotiation in under 2 minutes), "Polyglot" (use a non-English greeting). Discovery is itself a reward.
3. **Daily challenge bonus variance.** Instead of flat +50 XP, make it +30 to +80 based on performance quality, with the exact amount revealed only after completion. The uncertainty of "how much will I earn?" drives re-engagement.
4. **Streak surprise rewards.** At streak milestones beyond the 3/7/30 achievements (e.g., streak 5, 12, 20), deliver a surprise micro-reward — a new scenario unlocked, a unique achievement, or a "bonus round" challenge. Announce none of these in advance.

---

## 3. IKEA Effect

**Current state:** Users can customize scenario type, difficulty, target value, context description, and counterpart persona (via the tuner). The theme switcher offers three visual themes. Scenario cards let users choose their "game mode."

**What works:**
- The Full Setup form gives genuine authorship over the negotiation parameters. Users who craft their own context will value the resulting simulation more.
- Three visual themes (Arena, Coach, Lab) allow identity expression.
- The "Tune Counterpart Persona" link hints at deeper customization.

**What is missing:**
- Customization options exist but are not celebrated. The system does not acknowledge that the user built something.
- There is no persistent trace of user-created configurations. Each session is ephemeral.
- The profile is entirely system-managed (XP, level, streak). Nothing in the profile reflects the user's choices or identity.

**Recommendations:**
1. **Named scenario saves.** Let users save custom scenario configurations with a name (e.g., "My annual review prep"). Stored in localStorage alongside the profile. Seeing a list of their own scenarios creates ownership.
2. **"Your scenario" language.** When a user fills in the Full Setup form and starts a negotiation, the chat header could say "Your Salary Negotiation" rather than just "Salary Negotiation." Possessive language triggers the endowment effect.
3. **Custom avatar or initials.** Let users set their initials or pick an emoji avatar that appears in the chat view. Minimal effort to implement, but it personalizes every session.
4. **Strategy notes.** After the scorecard, offer a text field: "What would you do differently next time?" Save this note and surface it when the user starts the same scenario type again. The note is something they created, making the return visit feel like continuing their own work.

---

## 4. Peak-End Rule

**Current state:** Experiences are judged by their most intense moment and the final moment. The current peak moment is the score reveal (scorePop animation, score circle). The ending moment is a "Try Again" button followed by a quiet italic quote.

**What works:**
- The score pop animation is well-crafted — scale bounce with cubic-bezier easing creates a satisfying reveal.
- The level-up card from celebrations.js is a solid peak moment (slides up from bottom, shows level number with XP count).
- The first-session message ("You're already ahead of most people who never practice") is emotionally calibrated.

**What is missing:**
- The ending is weak. After the scorecard, the final visible elements are "Submit Feedback" and a generic "Try Again" button. The last thing the user sees is a request for something (feedback), not a gift.
- Peak moments are capped at one per session (`shownThisSession` flag in celebrations.js). This is appropriate for avoiding clutter, but it means that a session with both a level-up AND a personal best only celebrates the level-up.
- The demo ending is particularly flat: a score number, a verdict, and two buttons.

**Recommendations:**
1. **End on a positive reframe.** Replace the final element on the scorecard. Instead of ending with "Try Again," end with a personalized insight: "You used anchoring 40% more effectively than your first session" or "Your emotional control improved by 12 points this week." Make the last impression about growth, not repetition.
2. **Demo ending upgrade.** The 60-second demo is the most likely first experience. After the demo score, add one specific, concrete piece of feedback: "You opened by [specific thing they did] — here's what a master negotiator would do differently: [one sentence]." This creates a peak moment from learning, not just a number.
3. **Compound celebrations.** Allow the personal best shimmer to co-occur with a level-up card, since they occupy different screen regions (bottom card vs. inline text). Two simultaneous micro-celebrations for an exceptional session will create a stronger peak.
4. **Session-end summary micro-card.** Before "Try Again," show a compact card: "This session: +180 XP | New personal best | 1 achievement unlocked." This creates a concrete, positive final impression that summarizes accomplishment.

---

## 5. Loss Aversion

**Current state:** The app uses some loss framing. The "Money Left on the Table" display (yellow, prominent, with a dollar amount) is pure loss framing — it tells users what they failed to capture. Streak resets (gap of 2+ days resets to 1) are a loss. Win/loss classification (score >= 60 = win, else loss) labels sessions as losses.

**What works:**
- The "Money Left on the Table" concept is psychologically powerful and contextually appropriate for a negotiation trainer. Negotiators need to understand opportunity cost.

**What is problematic:**
- The streak reset mechanic punishes absence without nuance. Missing one day destroys a 29-day streak identically to missing 10 days. This can trigger frustration and abandonment rather than re-engagement.
- Win/loss binary at 60 is harsh for new users. A score of 55 on a third attempt is real progress but gets labeled a "loss."
- The "Money Left on the Table" framing, while educational, could be reframed to also show what was captured. Pure loss framing risks discouraging beginners.

**Recommendations:**
1. **Reframe "Money Left on the Table" as a dual display.** Show both: "You captured: $X" (in green, prominent) and "Available: $Y" (in muted yellow, smaller). Lead with the gain. The loss information is still there for advanced users, but beginners see their achievement first.
2. **Streak freeze or grace period.** Allow one "grace day" per week where missing a day does not break the streak. This prevents the devastating loss of a long streak due to one busy day. Streaks that survive a grace day feel even more valuable (effort justification).
3. **Replace win/loss binary with progress framing.** Instead of wins and losses, track "sessions above personal average" vs. "sessions below." A score of 55 that beats the user's previous average of 45 is reframed as growth. The win rate stat in the stats bar could become "improvement rate."
4. **Streak-at-risk nudge (gain frame).** When the user's streak is active and they have not played today, a gentle notification: "Your 5-day streak is still alive — one quick session to keep it going." Frame as preserving something valuable, not as "you'll lose it."

---

## 6. Social Proof

**Current state:** There is zero social proof anywhere in the application. No user counts, no testimonials, no "X people completed this scenario," no leaderboards, no community signals.

**What works:**
- The absence of fabricated numbers is honest and respects users. This is the right instinct.

**What is missing:**
- Real social proof is entirely absent. For a tool asking users to practice a vulnerable skill (negotiation), knowing that others are doing it too reduces the psychological barrier to starting.
- No indication that the tool has been used by real people.

**Recommendations:**
1. **Aggregate, anonymized stats (real data only).** If the backend tracks total sessions, display a genuine counter: "12,847 negotiations practiced" — but ONLY if this number is real. Never fabricate. If the app is early-stage, skip this until there is real data worth showing.
2. **Scenario popularity indicator.** On each scenario card, show "Most practiced" or "Popular this week" badges based on actual usage data. This helps new users choose and signals that the community values the tool.
3. **Post-session social comparison (opt-in).** After scoring, offer: "Your score of 72 is above average for this scenario." Only show this if you have real aggregate data. Fabricated comparisons destroy trust permanently.
4. **Testimonial section on landing page.** If real users have given positive feedback (via the feedback form), curate 2-3 genuine quotes with first name and context (e.g., "Sarah, job candidate"). Only real testimonials. The feedback collection mechanism already exists — route the best responses here.

---

## 7. Reciprocity

**Current state:** The app gives substantial free value before asking for anything. The entire simulation is free, requires no account, and stores nothing server-side. The demo is instant. The scorecard, coaching tips, debrief, and playbook are all provided without cost.

**What works well:**
- The value-first approach is strong. Users receive scoring, coaching tips, a debrief, move-by-move analysis, and a printable playbook — all before any ask.
- "No setup, no account required" is prominently stated and genuinely delivered.
- The feedback request comes after the full experience, not before. This is textbook reciprocity: give first, then ask.
- Privacy messaging ("Each session is private and not stored") builds trust.

**What could be enhanced:**
- The free value is not explicitly framed as a gift. Users may not consciously register how much they received for free.
- The engine-peek ("How does it work?") gives away the methodology for free — this is a trust-builder that could be surfaced more prominently.

**Recommendations:**
1. **Value summary before feedback ask.** Before the feedback section on the scorecard, add a subtle line: "You just received a score across 6 dimensions, 3 coaching tips, and a full debrief — all free and private. If you have 30 seconds, we'd love to hear how it went." This makes the reciprocity exchange explicit without being manipulative.
2. **Surface the engine-peek earlier.** Move "How does it work?" from below the form to a more visible position, or auto-expand it for first-time visitors. Transparency is a gift that builds trust and triggers reciprocity.
3. **Post-playbook ask.** The playbook is the highest-value deliverable (printable, actionable). After generating it, this is the optimal moment to ask for a share or testimonial — not before. Currently the share button is on the scorecard, before the playbook. Consider adding a share prompt after the playbook generation.

---

## 8. Zeigarnik Effect

**Current state:** Several mechanisms create open loops. The learning path shows future milestones as grayed-out nodes. Locked achievements show "???" instead of unlock dates. The daily challenge card shows a countdown timer to reset. Incomplete scenario coverage is tracked (played checkmarks on scenario cards).

**What works:**
- Locked achievements with "???" create genuine curiosity. The user can see the title and emoji but not the unlock condition — this is well-calibrated mystery.
- The learning path with future milestones as faded nodes creates a visual "unfinished journey" that nags productively.
- Scenario cards showing which scenarios have been played (checkmark) implicitly highlight which ones have NOT been played.

**What could create anxiety:**
- The streak display can create unhealthy obligation. A visible "0 days" streak after a break feels like a failure marker rather than an invitation.
- The stats bar is always visible (sticky), which means progress metrics are always in view. For some users, constant exposure to their stats creates performance anxiety rather than healthy motivation.

**Recommendations:**
1. **"Unfinished" framing for scenarios.** Add a counter below the scenario row: "7 of 10 scenarios explored." This converts implicit incompleteness into an explicit, trackable goal. The Zeigarnik effect is strongest when the task boundary is clear.
2. **Dimension gap highlighting.** On the radar chart, gently highlight the lowest-scoring dimension with a tooltip: "Your biggest growth opportunity: Value Creation (42/100)." This creates a specific open loop that the user can close in their next session.
3. **Soften the streak display after a break.** When the streak is 0 or 1 after a reset, show "Welcome back" instead of "0 days." The Zeigarnik effect should create healthy curiosity ("I want to get back to my streak"), not shame.
4. **Session-start reminder of open loops.** When a returning user lands on the home page, show one line: "Last time you scored 65 on Salary Negotiation — ready to beat it?" This activates the Zeigarnik effect from the previous incomplete experience (they could have scored higher) and creates natural motivation for the next session.

---

## Cross-Cutting Observations

### Onboarding psychology
The onboarding tour (`onboarding.js`) is well-designed psychologically. The "friend showing you around" philosophy is stated in the code comments and delivered in the implementation. Three steps, skip is always available, and completion is permanent. This respects autonomy and avoids reactance (the tendency to resist when feeling controlled).

One addition: the final step says "Make it yours" (theme switching). This is the IKEA effect applied to first impressions. Letting users customize something immediately creates investment.

### Celebration restraint
The celebrations module limits itself to one celebration per session and uses GPU-accelerated animations only. It respects `prefers-reduced-motion`. This restraint is psychologically sound — over-celebration devalues the signal. The priority hierarchy (levelUp > firstSession > highScore > personalBest) ensures the most meaningful event gets the spotlight.

### Missing: Commitment and Consistency
The app does not leverage commitment and consistency. Users never make a declaration of intent ("I want to improve my anchoring skill" or "I'm preparing for a real negotiation on Friday"). Adding a simple goal-setting step would create a commitment that drives consistent return visits. A one-line text field on the landing page — "What are you preparing for?" — stored in localStorage, would anchor the user's purpose and make each session feel purposeful rather than recreational.

### Missing: Implementation Intentions
Related to commitment: the app never asks "when will you practice next?" Research on implementation intentions shows that specifying when/where/how dramatically increases follow-through. After a session, a lightweight prompt — "When do you want to practice again? Tomorrow / In 3 days / This weekend" — would increase return rates. No push notifications needed; just the act of choosing a time creates the intention.

---

## Priority Ranking

Ordered by expected impact on user retention and engagement:

1. **Goal Gradient acceleration cues** (XP bar glow, milestone proximity) — low effort, high psychological impact
2. **Peak-End optimization** (end on growth insight, not "Try Again") — medium effort, shapes lasting memory of the experience
3. **Variable reward introduction** (random XP multiplier, hidden achievements) — medium effort, strongest driver of habit formation
4. **Loss Aversion reframing** (dual display for money, streak grace period) — medium effort, prevents beginner discouragement
5. **Zeigarnik open loops** (scenario counter, dimension gap highlight, session-start reminder) — low effort, drives return visits
6. **IKEA Effect deepening** (named saves, possessive language, custom avatar) — medium effort, increases perceived value
7. **Social Proof introduction** (real aggregate stats only) — depends on having real data
8. **Reciprocity framing** (value summary before ask) — low effort, incremental improvement
