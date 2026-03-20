# DealSim Care Audit

**Audited files:** `index.html`, `concept-a-arena.html`, `concept-b-coach.html`, `concept-c-lab.html`, `privacy.html`
**Date:** 2026-03-19
**Standard:** "Make users feel genuinely cared for and loved."

---

## Part 1: Dark Pattern Detection

### PASSED (not present in index.html -- the production app)

| Pattern | Status | Notes |
|---|---|---|
| Confirmshaming | CLEAN | No guilt-trip language on decline buttons. "Try Again" and "Full Simulation" are neutral. |
| Hidden costs | CLEAN | No pricing exists yet. No surprise requirements after starting. |
| Roach motel | CLEAN | Users can leave any section freely. No account creation required. No login wall. |
| Forced continuity | CLEAN | No subscription mechanism. No auto-enroll. |
| Misdirection | CLEAN | Visual hierarchy is honest. CTAs match their labels. |
| Privacy zuckering | CLEAN | Email field in feedback is explicitly marked "(optional)". No pre-checked consent boxes. |
| Bait and switch | CLEAN | Demo delivers what it promises -- a 3-move negotiation. |
| Trick questions | CLEAN | No double-negatives or confusing opt-in/opt-out language. |

### FLAGGED (present in concept pages)

| Pattern | Status | Location | Severity |
|---|---|---|---|
| Fake social proof | FLAGGED | `concept-a-arena.html` line 713 | HIGH |
| Fake urgency | FLAGGED | `concept-a-arena.html` lines 717, 836 | MEDIUM |
| Streak guilt | FLAGGED | `concept-a-arena.html` line 730 | LOW |

**Detail on each:**

#### 1. Fake Social Proof (concept-a-arena.html)
```html
<strong id="live-count">2,847</strong> negotiations completed today
```
The counter starts at 2,847 and increments randomly every 2.8 seconds (`count += Math.floor(Math.random() * 3)`). This is a fabricated number with no backend data source. It creates a false impression of activity. This is textbook fake social proof.

**Recommendation:** Remove entirely, or connect to a real endpoint that returns actual session counts. If the product is early-stage with low usage, showing a real small number ("47 negotiations today") is more honest and builds trust over time.

#### 2. Fake Urgency (concept-a-arena.html)
```html
Today's challenge expires in <span class="countdown-val" id="countdown">4h 23m 07s</span>
```
The countdown starts at a fixed 4h23m07s on every page load and counts down to zero. It is not tied to any actual expiration. It resets on refresh. This is a fake scarcity timer.

**Recommendation:** Either tie the countdown to a real daily reset time (midnight UTC, synced with server) or remove it. The daily challenge concept is good -- the countdown should be real.

#### 3. Streak Guilt (concept-a-arena.html)
```
"Don't break it!" (under 7-day streak)
```
This is a mild guilt-based retention mechanism. It frames not returning as a loss (loss aversion). Mild, but misaligned with "genuine care."

**Recommendation:** Replace with positive framing: "7 days strong!" or "You're building a habit." The streak mechanic itself is fine -- the guilt language is not.

---

## Part 2: Genuine Care Signals

### 1. Error States

**Current state: ADEQUATE, with room for warmth.**

Error messages are functional and blame-neutral. They never say "you did something wrong." Examples:
- `"Could not connect to server. Please check if the API is running."` -- correctly blames the system, not the user.
- `"Connection lost. Check your internet and try again."` -- neutral.
- `"Could not retrieve scorecard. Check your connection."` -- neutral.

**Gap:** Error messages are terse and technical. They lack warmth. No error state says "Don't worry" or "Your progress is safe." A user mid-negotiation who hits a connection error will feel anxious about losing their work.

**Care score: 5/10**

### 2. Empty States

**Current state: GOOD.**

The Score History empty state is well done:
```
"No scores yet"
"Complete a negotiation to see your progress here."
[Try a quick demo ->]
```
This is welcoming, non-judgmental, and provides a clear next action. The debrief empty state ("Complete a negotiation to see the debrief") is similarly clear.

The Coach concept (`concept-b-coach.html`) has an excellent onboarding empty state: "Welcome! Let's find your starting point" -- this is warm and sets the right tone.

**Care score: 7/10**

### 3. Loading States

**Current state: GOOD.**

- Buttons show spinners and change text during loading ("Starting..." / "Analyzing..." / "Scoring...").
- The debrief section shows animated skeleton placeholders during load.
- Chat shows a three-dot typing indicator while the AI responds.
- These are informative and reduce uncertainty.

**Gap:** No loading state tells the user what is happening. "Analyzing..." could be "Comparing against 6 scoring dimensions..." or "Building your opponent's strategy..." -- this would make the wait feel purposeful.

**Care score: 7/10**

### 4. Failure Recovery

**Current state: PARTIAL.**

- If a message send fails, the user can try again -- the input is not cleared on error.
- Session state is held in memory -- if the browser tab stays open, conversation continues.
- Demo mode properly resets on retry.

**Gap:** If the browser tab closes or refreshes mid-negotiation, all progress is lost. There is no localStorage backup of in-progress sessions. No warning on accidental navigation ("You have an active negotiation -- leave?"). This is the single biggest care gap in the product.

**Care score: 4/10**

### 5. Score Presentation

**Current state: GOOD -- one exception.**

Low score framing in the demo:
- Score >= 70: "Strong start! Try a full simulation for deeper practice."
- Score >= 40: "Decent showing. A full sim will help sharpen your technique."
- Score < 40: "Room to grow. The full simulation offers detailed coaching."

This is encouraging at all levels. "Room to grow" is the right framing for low scores. The main scorecard uses "Needs Practice" for low scores -- also acceptable, though slightly less warm.

"No deal reached -- but you still learned from the experience." -- this is a genuinely caring line. It reframes failure as learning.

**Gap:** The "Money Left on the Table" section (line 511: "You could have negotiated this much more.") can feel like a punch to someone who already scored low. The framing is slightly accusatory ("you could have").

**Care score: 7/10**

### 6. Feedback Collection

**Current state: GOOD.**

- Star rating with descriptive labels ("Not useful" through "Extremely useful").
- Comment field is clearly "(optional)".
- Email field is clearly "(optional)".
- After submission: "Thank you for your feedback! This helps us improve DealSim."

The Coach concept has delightful emoji-based feedback. The Lab concept frames feedback as "Help calibrate the engine" -- positioning the user as a collaborator, not a complaint-filer.

**Gap:** The feedback modal appears automatically 15 seconds after the 2nd session. While this is unobtrusive, it is unsolicited. Some users will find it annoying. The modal is easy to close (Escape, click overlay, X button), which mitigates this.

**Care score: 7/10**

### 7. Privacy Respect

**Current state: EXCELLENT.**

This is the strongest care signal in the product:
- No cookies at all.
- No Google Fonts (GDPR-safe, noted in the HTML comment).
- No third-party analytics or tracking pixels.
- Privacy page is thorough, citing specific GDPR articles.
- Data stored in Frankfurt, Germany (EU).
- Session IDs are "random, non-trackable."
- Score history is localStorage only -- never leaves the browser.
- The landing page states: "Each session is private and not stored beyond your conversation."

**Care score: 9/10**

### 8. Microinteractions

**Current state: GOOD.**

- Score numbers animate with a count-up effect (satisfying).
- Score circle does a "pop" animation on reveal.
- Chat bubbles slide up with `bubbleIn` animation.
- Progress bars fill with animation.
- Buttons have a subtle press effect (`scale(0.97)` on active).
- Disabled buttons show clear visual state.
- Toast notifications for copy actions, resets, etc.
- Focus ring styling for keyboard navigation.
- Custom scrollbar that matches the design.

**Gap:** No success sound or haptic feedback. No confetti or celebration on high scores. The Coach concept has a "Skill Garden" metaphor that is delightful -- this kind of warm metaphor is absent from the main app.

**Care score: 7/10**

### 9. Inclusive Language

**Current state: GOOD.**

- "Get scored. Get better." -- simple, accessible.
- Scenario types cover a range of situations (salary, freelance, rent, medical bills, car buying) -- not just corporate negotiation.
- No gendered language.
- No jargon without context.
- Difficulty levels are straightforward: Easy / Medium / Hard.
- ARIA labels are present on interactive elements.

**Gap:** The word "opponent" frames the counterpart adversarially. In collaborative negotiation pedagogy, "counterpart" is preferred. The Arena concept doubles down on competitive framing ("Choose Your Battle," "Quick Match," "Ranked Match") which is fun but alienating to non-competitive personalities.

**Care score: 7/10**

### 10. Exit Experience

**Current state: POOR.**

There is no exit experience. When users close the tab, there is no goodbye. When they finish a session, the only options are "Try Again" or "Full Simulation." There is no:
- "Great session! Come back anytime."
- "Your skills are improving" (for returning users).
- Browser notification asking if they want to save or export their results before leaving.
- Email digest option for their session history.

The Daily Challenge has a small exit note: "Come back tomorrow for a new one." This is the only warm exit moment in the entire product.

**Care score: 3/10**

---

## Part 3: Care Enhancement Recommendations

### 1. Warm error messages (index.html, JS error handlers)

**Where:** `appendSystemMsg()` calls throughout the JavaScript.

**Current:**
```
"Connection lost. Check your internet and try again."
```
**Replace with:**
```
"Connection hiccup -- don't worry, your conversation is still here. Check your internet and try again."
```

**Current:**
```
"Could not retrieve scorecard. Check your connection."
```
**Replace with:**
```
"We couldn't load your scorecard just yet. Your session is saved -- try again in a moment."
```

### 2. Money-on-table reframe (index.html, line 511)

**Where:** Scorecard "Money Left on the Table" section.

**Current:**
```
"You could have negotiated this much more."
```
**Replace with:**
```
"Here's what was available -- knowing this helps you capture it next time."
```

### 3. Session protection (index.html, new feature)

**Where:** Add to `window.onbeforeunload` handler.

**Add:**
```javascript
window.addEventListener('beforeunload', (e) => {
  if (state.sessionId && document.getElementById('sec-chat').classList.contains('active')) {
    e.preventDefault();
    e.returnValue = 'You have an active negotiation. Your progress will be lost if you leave.';
  }
});
```

### 4. Loading state personality (index.html, `setStartLoading`)

**Where:** Button text during loading states.

**Current:** `"Starting..."`
**Replace with rotating messages:**
```
"Building your opponent's strategy..."
"Setting up the negotiation room..."
"Calibrating difficulty..."
```

### 5. Warm exit moment (index.html, scorecard section)

**Where:** After the "Try Again" button in the scorecard section (line 586).

**Add after the button:**
```html
<p class="text-center text-white/40 text-xs mt-6 italic">
  Every negotiation you practice makes the real ones easier. See you next time.
</p>
```

### 6. Returning user recognition (index.html, DOMContentLoaded)

**Where:** Landing page, on load.

**Add logic:** If `localStorage` has previous scores, show a small welcome-back line:
```html
<p class="text-center text-white/50 text-sm mb-4">
  Welcome back -- you've completed <span class="text-white font-semibold">X</span> negotiations so far.
  Your best score: <span class="text-coral font-semibold">Y</span>.
</p>
```

### 7. "Needs Practice" label softening (index.html, `renderScorecard`)

**Where:** Score label for scores below 40 (line 1583).

**Current:** `"Needs Practice"`
**Replace with:** `"Building Foundations"`

This reframes a low score as progress rather than deficiency.

### 8. Streak framing fix (concept-a-arena.html, line 730)

**Where:** Stats bar streak label.

**Current:** `"Don't break it!"`
**Replace with:** `"7 days strong"`

### 9. Remove fake live counter (concept-a-arena.html, lines 711-714 and 1284-1293)

**Where:** Hero section live counter and its JavaScript.

**Action:** Delete the `<div class="live-counter">` block and the `liveCounter()` function entirely. Replace with nothing -- or with a real metric from the server when available.

### 10. Feedback modal opt-in (index.html, line 1642)

**Where:** Auto-triggering feedback modal after 15 seconds.

**Current behavior:** Modal appears automatically after the 2nd session.

**Replace with:** A small, non-modal prompt at the bottom of the scorecard:
```html
<p class="text-center text-white/40 text-xs mt-4">
  Got 30 seconds? <button onclick="openFeedbackModal()" class="text-coral hover:text-coral-light underline underline-offset-2 transition-colors">Share your thoughts</button> -- it shapes what we build next.
</p>
```
Remove the `setTimeout(() => { openFeedbackModal(); }, 15000)` auto-trigger. Let users choose when to give feedback.

---

## Summary Scorecard

| Dimension | Score | Priority |
|---|---|---|
| Dark pattern freedom (main app) | 9/10 | Maintain |
| Dark pattern freedom (concept pages) | 5/10 | Fix fake counter and countdown |
| Error states | 5/10 | Add warmth |
| Empty states | 7/10 | Good |
| Loading states | 7/10 | Add personality |
| Failure recovery | 4/10 | Add session protection |
| Score presentation | 7/10 | Soften edges |
| Feedback collection | 7/10 | Make modal opt-in |
| Privacy respect | 9/10 | Excellent |
| Microinteractions | 7/10 | Good |
| Inclusive language | 7/10 | Consider "counterpart" over "opponent" |
| Exit experience | 3/10 | Biggest gap -- add warm exits |

**Overall care score: 6.4/10**

The product's strongest care signal is its privacy posture -- genuinely best-in-class, with no cookies, no third-party tracking, EU-only data storage, and transparent GDPR compliance. The biggest care gap is the exit experience and failure recovery: users who lose progress mid-session or leave the app get nothing warm from the product.

The concept pages (especially Arena) contain dark patterns that contradict the care philosophy. The main production `index.html` is clean. If the Arena concept influences the production build, the fake counter and fake countdown must not make it in.
