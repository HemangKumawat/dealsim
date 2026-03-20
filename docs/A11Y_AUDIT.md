# DealSim Accessibility (a11y) Audit — WCAG 2.1 AA

**File audited:** `static/index.html` (2642 lines)
**Date:** 2026-03-19
**Standard:** WCAG 2.1 Level AA

---

## Summary

DealSim has a solid accessibility foundation — `lang="en"`, `role` attributes on navigation and live regions, `aria-label` on inputs, keyboard-friendly `focus-visible` styles, and `role="alert"` on error messages. However, several gaps remain that would fail WCAG 2.1 AA conformance. This audit lists every issue found, grouped by category.

**Counts:** 7 Critical, 11 Major, 8 Minor

---

## 1. Semantic HTML

### 1.1 Sections lack landmark roles
- **Severity:** Major
- **WCAG:** 1.3.1 Info and Relationships
- **Location:** Lines 216, 357, 430, 492, 595, 669, 742, 824, 932, 965, 1006, 1075 — all `<section>` elements
- **Issue:** `<section>` elements have no `aria-label` or `aria-labelledby`, so screen readers cannot distinguish them. The SPA has 12 sections; a screen reader user navigating by landmark hears "region" twelve times with no way to tell them apart.
- **Fix:** Add `aria-label` to each section matching its purpose:
  ```html
  <section id="sec-landing" aria-label="Simulation setup" ...>
  <section id="sec-chat" aria-label="Negotiation chat" ...>
  <section id="sec-scorecard" aria-label="Scorecard results" ...>
  ```

### 1.2 No `<main>` landmark
- **Severity:** Major
- **WCAG:** 1.3.1 Info and Relationships
- **Location:** Body (line 172)
- **Issue:** The page has `<nav>` and `<footer>` but no `<main>`. Screen reader users cannot jump to main content.
- **Fix:** Wrap all `<section>` elements in `<main id="main-content">`.

### 1.3 Heading hierarchy gaps
- **Severity:** Major
- **WCAG:** 1.3.1 Info and Relationships
- **Location:** Lines 604, 706, 833, 936 — `<h2>` elements containing emoji prefixes; lines 625, 633, 642, 711, etc. — `<h3>` used inside cards without a parent `<h2>` in the same semantic group
- **Issue:** Multiple `<h2>` tags appear in hidden sections simultaneously. When a section becomes active, the heading hierarchy jumps. Also, some sections skip from `<h2>` to `<h3>` without clear nesting.
- **Fix:** Ensure each active section presents a clean h1->h2->h3 hierarchy. Consider making the main page title an `<h1>` and section titles `<h2>`.

### 1.4 Lists used for star ratings lack list semantics
- **Severity:** Minor
- **WCAG:** 1.3.1 Info and Relationships
- **Location:** Lines 549, 1135 — star rating buttons in a `<div>` with `role="radiogroup"`
- **Issue:** These are semantically correct as radiogroups, but each star button lacks `role="radio"` — they only have `aria-label`.
- **Fix:** Add `role="radio"` to each star button:
  ```html
  <button role="radio" aria-checked="false" onclick="setRating(1)" ...>
  ```

---

## 2. ARIA

### 2.1 Difficulty radio buttons: keyboard arrow-key navigation missing
- **Severity:** Critical
- **WCAG:** 2.1.1 Keyboard
- **Location:** Lines 303-313 — `role="radiogroup"` with three buttons having `role="radio"`
- **Issue:** Custom `role="radiogroup"` requires arrow-key navigation between options per WAI-ARIA authoring practices. Currently only Tab works, which is incorrect for a radiogroup. A keyboard user pressing arrow keys gets nothing.
- **Fix:** Implement arrow-key navigation with `roving tabindex` pattern. Only the selected radio should have `tabindex="0"`; others should have `tabindex="-1"`. Arrow keys should cycle through options and update `aria-checked`.

### 2.2 Star rating radiogroups: same arrow-key issue
- **Severity:** Critical
- **WCAG:** 2.1.1 Keyboard
- **Location:** Lines 549-554 (scorecard feedback), lines 1135-1140 (modal feedback)
- **Issue:** Same problem as 2.1. `role="radiogroup"` requires arrow-key navigation, which is not implemented.
- **Fix:** Same roving tabindex solution as 2.1.

### 2.3 Chat messages area lacks `aria-label`
- **Severity:** Minor
- **WCAG:** 4.1.2 Name, Role, Value
- **Location:** Line 459 — `<div id="chat-messages" role="log" aria-live="polite">`
- **Issue:** The `role="log"` region has no `aria-label` to identify it. Screen readers will say "log" with no context.
- **Fix:** Add `aria-label="Chat messages"`.

### 2.4 Demo chat messages area has no `role="log"` or `aria-live`
- **Severity:** Critical
- **WCAG:** 4.1.3 Status Messages
- **Location:** Line 387 — `<div id="demo-messages" ...>`
- **Issue:** Unlike the main chat (which has `role="log"` and `aria-live="polite"`), the demo chat area has neither. New demo messages are completely invisible to screen readers.
- **Fix:** Add `role="log" aria-live="polite" aria-label="Demo chat messages"` to `#demo-messages`.

### 2.5 Demo typing indicator has no `aria-label`
- **Severity:** Minor
- **WCAG:** 4.1.3 Status Messages
- **Location:** JS line ~1982 — `appendDemoTyping()` function
- **Issue:** Unlike the main chat typing indicator (which has `aria-label="Opponent is typing"`), the demo version omits the label.
- **Fix:** Add `wrapper.setAttribute('aria-label', 'Opponent is typing');` in `appendDemoTyping()`.

### 2.6 Score updates not announced to screen readers
- **Severity:** Critical
- **WCAG:** 4.1.3 Status Messages
- **Location:** Lines 497-504 — score display area; line 411 — demo score
- **Issue:** When a negotiation completes and scores appear (both full sim and demo), there is no `aria-live` region to announce the result. The score count-up animation is purely visual.
- **Fix:** Wrap score displays in `aria-live="polite"` containers or add `role="status"` to the score number elements.

### 2.7 Earnings calculator results not announced
- **Severity:** Major
- **WCAG:** 4.1.3 Status Messages
- **Location:** Lines 1045-1063 — calculator results area
- **Issue:** As the user types numbers, results update in real time but are not announced to screen readers.
- **Fix:** Add `aria-live="polite"` to the results container `<div class="bg-navy-dark rounded-xl ...">` at line 1045.

### 2.8 `<canvas>` chart has no text alternative
- **Severity:** Major
- **WCAG:** 1.1.1 Non-text Content
- **Location:** Line 941 — `<canvas id="history-chart">`
- **Issue:** The score history chart is drawn on a `<canvas>` with no fallback text. Screen readers get nothing.
- **Fix:** Add descriptive fallback text inside the canvas element and an `aria-label`:
  ```html
  <canvas id="history-chart" height="200" class="w-full" role="img" aria-label="Score history line chart">
    Your score history chart. Use the score list below for details.
  </canvas>
  ```

---

## 3. Keyboard Navigation

### 3.1 Home logo uses `onclick` + `onkeydown` instead of a link
- **Severity:** Minor
- **WCAG:** 2.1.1 Keyboard
- **Location:** Line 181 — `<div ... onclick="goHome()" role="button" tabindex="0" onkeydown="if(event.key==='Enter')goHome()">`
- **Issue:** The div handles Enter but not Space (both are expected for `role="button"`). Also, using a `<div>` instead of a `<button>` or `<a>` means it does not participate in the accessibility tree as cleanly.
- **Fix:** Either change to `<button>` or add Space key handling:
  ```html
  onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();goHome()}"
  ```

### 3.2 Focus not managed on SPA section transitions
- **Severity:** Critical
- **WCAG:** 2.4.3 Focus Order
- **Location:** JS line ~1223 — `showSection()` function
- **Issue:** When sections change, focus stays on the button that triggered the navigation (or worse, on a now-hidden element). Screen reader users have no indication that the page content changed. The function scrolls to top but does not move focus.
- **Fix:** After showing a new section, move focus to the section heading or the section itself:
  ```js
  function showSection(id) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const el = document.getElementById(id);
    if (el) {
      el.classList.add('active');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      const heading = el.querySelector('h1, h2');
      if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus(); }
    }
    closeMobileMenu();
  }
  ```

### 3.3 Modal focus trap missing
- **Severity:** Critical
- **WCAG:** 2.4.3 Focus Order
- **Location:** Lines 1126-1154 — feedback modal
- **Issue:** When the feedback modal opens, focus is not moved into it, and Tab can escape to elements behind the modal overlay. Escape closes it (good), but there is no focus trap.
- **Fix:** On modal open, move focus to the first interactive element. Trap Tab within the modal. On close, return focus to the element that triggered the modal.

### 3.4 Slider range inputs not keyboard-announced
- **Severity:** Minor
- **WCAG:** 4.1.2 Name, Role, Value
- **Location:** Lines 846, 859, 872, 885, 898, 911 — range inputs in Opponent Tuner
- **Issue:** The range inputs have `aria-label` (good) but the current value display is in a separate `<span>`. Screen readers will read the native slider value but not the friendly label endpoints ("Friendly" to "Hardball").
- **Fix:** Add `aria-valuetext` dynamically. For example, for aggressiveness at 50: `aria-valuetext="50 — between Friendly and Hardball"`.

---

## 4. Color Contrast

### 4.1 `text-white/60` on dark navy background
- **Severity:** Major
- **WCAG:** 1.4.3 Contrast (Minimum) — requires 4.5:1 for normal text
- **Location:** Throughout — lines 233, 364, 437, 605, 707, 749, 834, 937, 972, 1013, 1082, and many more
- **Issue:** `text-white/60` is `rgba(255,255,255,0.6)` on `#1a1b4b` (navy). Effective color is approximately `#8c8daa` on `#1a1b4b`. Contrast ratio is approximately **3.5:1**, which fails the 4.5:1 minimum for normal-sized text.
- **Fix:** Increase to `text-white/70` minimum (approx 4.5:1) or `text-white/80` for comfortable reading. For text at 14px+ bold or 18px+, the 3:1 large-text threshold applies, so larger bold text at `/60` may pass.

### 4.2 `text-white/30` on dark navy
- **Severity:** Major
- **WCAG:** 1.4.3 Contrast (Minimum)
- **Location:** Lines 346, 480-483, 847, 860, 873, 886, 899, 912, 944-946, 978, 1065 — slider endpoint labels, helper text, timestamps
- **Issue:** `text-white/30` on `#1a1b4b` has a contrast ratio of approximately **1.8:1**. This fails even the 3:1 large-text threshold.
- **Fix:** These are informational (not decorative). Raise to at least `text-white/60` for large text or `text-white/70` for small text. If truly decorative, mark with `aria-hidden="true"`.

### 4.3 `text-white/20` for unselected star buttons
- **Severity:** Major
- **WCAG:** 1.4.3 Contrast (Minimum)
- **Location:** Lines 550-554, 1136-1140
- **Issue:** Unselected stars at `text-white/20` on navy are nearly invisible at approximately **1.4:1** contrast. These are interactive elements.
- **Fix:** Use at least `text-white/50` for unselected stars and ensure the selected/unselected distinction does not rely solely on color (the filled star glyph helps, but contrast still matters).

### 4.4 `placeholder-white/25` on form inputs
- **Severity:** Minor
- **WCAG:** 1.4.3 Contrast (Minimum) — placeholder text is not required to meet contrast ratios per WCAG, but it is a best practice
- **Location:** Lines 296, 319, 390, 464, 557-559, 757, 764, 769, 777, 782, 789, 1019, 1025, 1032, 1038, 1089, 1094, 1143
- **Issue:** Placeholder text at 25% white opacity is very hard to read. While WCAG does not strictly require placeholder contrast, WCAG 2.1 SC 1.4.3 applies to all text that conveys information.
- **Fix:** Increase to `placeholder-white/50` for better readability.

### 4.5 Coral text on navy for links and labels
- **Severity:** Minor
- **WCAG:** 1.4.3 Contrast (Minimum)
- **Location:** Lines 222, 324, 977, and various coral-colored headings
- **Issue:** `#f95c5c` (coral) on `#1a1b4b` (navy) has a contrast ratio of approximately **4.3:1** — just under the 4.5:1 threshold for normal text. Passes for large text (18px+ or 14px bold).
- **Fix:** For small coral text, use the lighter coral `#ff7a7a` (better contrast) or ensure it is used only at large/bold sizes. For the badge at line 222, the small uppercase text at `text-xs` fails.

---

## 5. Screen Reader — Dynamic Content

### 5.1 Chat bubbles announced correctly (main chat)
- **Status:** PASS
- **Location:** Line 459 — `role="log" aria-live="polite"` on `#chat-messages`
- **Note:** New messages appended to the log container will be announced. Good implementation.

### 5.2 System error messages use `role="alert"`
- **Status:** PASS
- **Location:** Lines 330, 793, 1098, JS line ~1542
- **Note:** Error messages and system messages correctly use `role="alert"`.

### 5.3 Toast notifications use `role="status"`
- **Status:** PASS
- **Location:** Line 175 — `<div id="toast" role="status" aria-live="polite">`
- **Note:** Toast updates will be announced. Good.

### 5.4 Offer analysis results not announced
- **Severity:** Major
- **WCAG:** 4.1.3 Status Messages
- **Location:** Lines 809-815 — `#offer-result` div
- **Issue:** When the offer analysis loads, the result container is unhidden but has no live region. Screen reader users get no notification that results appeared.
- **Fix:** Add `aria-live="polite"` to `#offer-result` or announce via a status message.

### 5.5 Audit analysis results not announced
- **Severity:** Major
- **WCAG:** 4.1.3 Status Messages
- **Location:** Lines 1114-1117 — `#audit-result` div
- **Issue:** Same as 5.4. No live region on the audit results container.
- **Fix:** Add `aria-live="polite"` to `#audit-result`.

---

## 6. Focus Management

### 6.1 SPA section transitions (covered in 3.2)
See issue 3.2 above. Focus does not move when sections change.

### 6.2 After form submission, focus moves to chat input
- **Status:** PASS
- **Location:** JS line 1360 — `document.getElementById('msg-input').focus()`
- **Note:** After starting a negotiation, focus correctly moves to the chat input.

### 6.3 After sending a message, focus returns to input
- **Status:** PASS
- **Location:** JS line 1442 — `document.getElementById('msg-input').focus()`
- **Note:** Good pattern.

### 6.4 Modal close does not return focus
- **Severity:** Major
- **WCAG:** 2.4.3 Focus Order
- **Location:** JS line ~1729 — `closeFeedbackModal()`
- **Issue:** When the modal closes, focus is not returned to the element that opened it. Focus falls to `<body>`, forcing keyboard users to navigate back to where they were.
- **Fix:** Store the trigger element before opening the modal, and restore focus on close:
  ```js
  let modalTrigger = null;
  function openFeedbackModal() {
    modalTrigger = document.activeElement;
    // ... existing code ...
    document.querySelector('#feedback-modal button, #feedback-modal input').focus();
  }
  function closeFeedbackModal() {
    document.getElementById('feedback-modal').classList.add('hidden');
    if (modalTrigger) modalTrigger.focus();
  }
  ```

---

## 7. Form Labels

### 7.1 All text inputs and selects have associated `<label>` elements
- **Status:** PASS
- **Location:** Lines 270-284 (scenario-type), 293-297 (target-value), 318-320 (context), 756-790 (offer form), 1017-1041 (calculator), 1088-1095 (audit form)
- **Note:** Labels use `for` attributes matching input `id`s. Good.

### 7.2 Textarea inputs in chat area use `aria-label`
- **Status:** PASS
- **Location:** Line 467 — `aria-label="Chat message"`, line 390 (demo input has `placeholder` but no explicit label)

### 7.3 Demo chat input missing accessible label
- **Severity:** Major
- **WCAG:** 1.3.1 Info and Relationships, 4.1.2 Name, Role, Value
- **Location:** Line 390 — `<textarea id="demo-msg-input" ... placeholder="Your move... (Enter to send)">`
- **Issue:** Unlike the main chat input (which has `aria-label="Chat message"`), the demo chat input relies only on `placeholder` for its accessible name. Placeholder is not a reliable accessible name in all screen readers.
- **Fix:** Add `aria-label="Your negotiation move"`.

### 7.4 Feedback email input lacks visible label
- **Severity:** Minor
- **WCAG:** 1.3.1 Info and Relationships
- **Location:** Line 559 — `<input id="feedback-email" type="email" placeholder="Email for updates (optional)">`
- **Issue:** Uses placeholder only (no `<label>`). While the preceding textarea has a similar issue, this is an email field where autocomplete and assistive tech behavior depend on a proper label.
- **Fix:** Add a `<label>` element or `aria-label="Email for updates (optional)"`.

### 7.5 Feedback comment textarea lacks label
- **Severity:** Minor
- **WCAG:** 4.1.2 Name, Role, Value
- **Location:** Lines 557-558, 1143-1144 — feedback textareas in both scorecard and modal
- **Issue:** Both feedback comment textareas rely on placeholder text only.
- **Fix:** Add `aria-label="Feedback comment"`.

---

## 8. Error Messages

### 8.1 Form validation errors use `role="alert"`
- **Status:** PASS
- **Location:** Lines 330, 793, 1098
- **Note:** Error containers have `role="alert"`, so screen readers will announce errors when they appear.

### 8.2 Inline feedback validation ("Please select a rating first") not announced
- **Severity:** Minor
- **WCAG:** 4.1.3 Status Messages
- **Location:** JS lines 1666-1667 — rating label changes to error text
- **Issue:** The rating label text changes to an error message, but the `<p>` element has no `role="alert"` or `aria-live`. Screen readers will not announce this validation error.
- **Fix:** Add `role="alert"` to `#rating-label` and `#modal-rating-label` (or wrap them in a live region).

---

## 9. Mobile / Touch Targets

### 9.1 Navigation link buttons too small
- **Severity:** Major
- **WCAG:** 2.5.5 Target Size (Level AAA) / 2.5.8 Target Size Minimum (Level AA in 2.2)
- **Location:** Lines 191-196 — desktop nav buttons with `px-3 py-1.5` (approx 36x30px)
- **Issue:** Touch targets are smaller than the 44x44px minimum recommended by WCAG. These are also shown on tablets where touch is the primary input.
- **Fix:** Increase padding to at least `px-4 py-2.5` or ensure adequate spacing between targets.

### 9.2 "Clear all history" link button
- **Severity:** Minor
- **WCAG:** 2.5.8 Target Size Minimum
- **Location:** Line 954 — small text link `text-xs` with no padding
- **Issue:** Tiny touch target. Difficult to tap on mobile.
- **Fix:** Add padding: `px-3 py-2`.

### 9.3 Copy/Print buttons in playbook
- **Severity:** Minor
- **WCAG:** 2.5.8 Target Size Minimum
- **Location:** Lines 679-686 — small buttons with `px-3 py-1.5`
- **Issue:** Below 44x44px minimum.
- **Fix:** Increase to `px-4 py-2.5`.

---

## 10. Reduced Motion

### 10.1 No `prefers-reduced-motion` media query
- **Severity:** Critical
- **WCAG:** 2.3.3 Animation from Interactions (Level AAA) / best practice for AA
- **Location:** Entire `<style>` block, lines 25-170
- **Issue:** The page uses multiple CSS animations (`bubbleIn`, `blink`, `fillBar`, `scorePop`, `fadeUp`, `pulse`) and JavaScript animations (`animateCountUp` with `requestAnimationFrame`). None are wrapped in a `prefers-reduced-motion` check. Users with vestibular disorders may experience discomfort.
- **Fix:** Add a reduced-motion media query that disables or reduces all animations:
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
  ```
  Also check `prefers-reduced-motion` in JavaScript before running `animateCountUp`:
  ```js
  function animateCountUp(el, target, duration = 800) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      el.textContent = target;
      return;
    }
    // ... existing animation code
  }
  ```

---

## Priority Fix Order

### Critical (must fix for AA compliance)
1. **10.1** — Add `prefers-reduced-motion` (affects all users with motion sensitivity)
2. **3.2** — Focus management on SPA section transitions
3. **3.3** — Modal focus trap
4. **2.1/2.2** — Arrow-key navigation for custom radiogroups (difficulty + stars)
5. **2.4** — Demo chat `aria-live` region
6. **2.6** — Score announcements for screen readers

### Major (should fix for solid AA compliance)
7. **1.1** — Section `aria-label` attributes
8. **1.2** — Add `<main>` landmark
9. **1.3** — Heading hierarchy
10. **4.1/4.2/4.3** — Color contrast fixes for `/60`, `/30`, `/20` opacity text
11. **2.7** — Calculator live region
12. **2.8** — Canvas chart text alternative
13. **5.4/5.5** — Offer/audit results live regions
14. **6.4** — Modal focus return
15. **7.3** — Demo input label
16. **9.1** — Nav touch targets

### Minor (polish)
17. **7.4/7.5** — Feedback input labels
18. **3.1** — Logo Space key handling
19. **2.3/2.5** — Aria labels on log/typing
20. **4.4/4.5** — Placeholder contrast, coral small text
21. **8.2** — Rating validation announcements
22. **9.2/9.3** — Small touch targets
23. **1.4** — Star button `role="radio"`
24. **3.4** — Slider `aria-valuetext`
