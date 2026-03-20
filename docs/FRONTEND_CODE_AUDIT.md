# Frontend Code Audit: `static/index.html`

**File:** `static/index.html` (2,631 lines)
**Date:** 2026-03-19
**Auditor scope:** JavaScript quality, HTML semantics, CSS, security, performance, accessibility, mobile, code organization, browser compatibility, loading strategy

---

## 1. JavaScript Quality

### Global State Management
- **Single mutable `state` object (line 1194):** All session state lives in one global object (`state.sessionId`, `state.round`, `state.isSending`, etc.). This works for the current scale but provides no encapsulation. Any function can silently corrupt state.
- **Scattered global variables:** `lastScoreData` (line 1545), `feedbackRating` (line 1645), `currentChallenge` (line 2530), `_typingCounter` (line 1514), `_demoTypingCounter` (line 1975) are loose globals outside the `state` object. Inconsistent placement makes it easy to miss dependencies.
- **No state change notifications:** UI updates are imperative (`getElementById` + manual DOM mutation). If two code paths both need to react to a state change, the second one must be wired up manually. Risk of the UI falling out of sync with `state`.

### Error Handling
- **`fetch` calls handle errors well overall.** Every API call has a `try/catch`, checks `res.ok`, and falls back to user-visible error messages. This is above average for SPAs.
- **Silent swallows on line 1631 and 1768:** `.catch(() => {})` on the debrief-money-left fetch and the `trackEvent` function. The debrief one is acceptable (non-critical), but `trackEvent` silently eats network errors with no logging at all, making debugging harder.
- **`document.execCommand('copy')` fallback (line 1786):** Deprecated API used as a fallback for clipboard. Works today but will eventually break.

### Memory Leaks / Event Listeners
- **MutationObservers never disconnected (lines 2520-2525, 2580-2585):** `historyObserver` and `challengeObserver` observe section class changes and are never cleaned up. In this SPA with no route teardown, this is acceptable but not ideal.
- **No `AbortController` on fetch calls:** If the user navigates away mid-request (e.g., clicks "End & Score" then immediately "Try Again"), in-flight fetches will still resolve and mutate the DOM. Could cause stale data to appear in the wrong section. Using `AbortController` on `sendMessage`, `fetchScorecard`, `showDebrief`, and `generatePlaybook` would fix this.
- **Inline `onclick` handlers on dynamically created elements:** Not a leak risk here since elements are replaced via `innerHTML = ''`, but the pattern prevents easy cleanup if the architecture changes.

### Specific Bugs
- **Line 2281:** `document.getElementById('playbook-opening')` references an element that does not exist in the HTML. This will throw silently (no-op on null) but the error message never displays.
- **Race condition in `renderScorecard` (line 1622):** The debrief fetch fires after rendering the scorecard. If the user navigates away before it resolves, it will modify hidden elements. Low severity but worth noting.

---

## 2. HTML Semantics

### Heading Hierarchy
- **Good:** `h1` on the landing page (line 229), `h2` for each section, `h3` for sub-sections within scorecard/debrief/playbook. The hierarchy is largely correct.
- **Issue:** Several sections use `h2` headings at the same level but there is no wrapping `<main>` element. The `<body>` directly contains `<nav>` and multiple `<section>` elements, which is fine structurally but adding `<main>` would improve landmark navigation.

### Landmark Roles
- **Good:** `<nav>` has `role="navigation"` and `aria-label="Main navigation"` (line 181). Chat messages have `role="log"` and `aria-live="polite"` (line 454). Error alerts have `role="alert"` (lines 325, 788, 1093). Toast has `role="status"` with `aria-live="polite"` (line 176). Modal has `role="dialog"` and `aria-modal="true"` (line 1121).
- **Missing:** No `<main>` landmark. No `role="region"` or `aria-label` on the `<section>` elements, so screen readers see multiple unlabeled sections.

### Form Labels
- **Good:** All form inputs have associated `<label>` elements with `for` attributes matching `id`s. The textarea at line 462 uses `aria-label` instead, which is acceptable.
- **Missing labels:** The range inputs in the Opponent Tuner section (lines 841, 854, etc.) have `aria-label` attributes which is correct, but the visual `<label>` elements lack `for` attributes since sliders use different IDs than labels reference.

### Button vs Div Clickables
- **Good:** All clickable elements are actual `<button>` elements, not `<div>` or `<span>`. The DealSim logo/home link (line 182) is a `<div>` with `onclick`, `role="button"`, `tabindex="0"`, and `onkeydown` for Enter. This works but a `<button>` would be simpler and get free keyboard handling.

---

## 3. CSS / Tailwind

### Tailwind Usage
- **Consistent and idiomatic.** The custom theme (lines 9-22) extends colors and fonts cleanly. Custom utility classes like `focus-coral`, `coral-glow`, `diff-btn.selected` supplement Tailwind where needed.
- **No `@apply` usage:** All Tailwind classes are applied directly in HTML, which leads to extremely long class strings (e.g., line 241 has 10+ classes). Readable here because the component count is manageable.

### Custom CSS Conflicts
- **Potential specificity issue:** `.section { display: none; }` and `.section.active { display: flex; }` (lines 36-37) use custom CSS that could conflict with Tailwind's `flex` class if both are applied. Currently safe because `.section.active` always wins, but fragile.
- **`@media (max-width: 400px)` override (line 162):** Uses `!important` to override Tailwind's `grid-cols-2`. This works but `!important` is a maintenance hazard. A Tailwind `@screen` directive or a more specific selector would be cleaner.

### Responsive Breakpoints
- The app uses `sm:` (640px) as the primary breakpoint throughout, matching Tailwind defaults. The 400px breakpoint (line 161) handles very small phones. No `md:`, `lg:`, or `xl:` breakpoints are used, which means the layout is essentially two-tier (mobile vs. everything else). For a chat/form app this is reasonable.

### Color Contrast
- **Primary concern:** `text-white/60` and `text-white/70` on `#1a1b4b` background. White at 60% opacity on dark navy gives approximately `rgba(255,255,255,0.6)` which is `#9999b8` on `#1a1b4b`. Contrast ratio is roughly 4.5:1, barely passing WCAG AA for normal text but failing for small text (12-13px used in many places).
- **`text-white/30` (line 341, 951, etc.):** At 30% opacity, this fails WCAG AA entirely. Used for "fine print" text but still needs to be readable.
- **`text-white/20` on star buttons (lines 545-549):** Unselected stars are nearly invisible. Accessibility concern for users with low vision.

---

## 4. Security

### innerHTML Usage (XSS Risk)
This is the most significant finding in the audit.

- **`escapeHtml` function exists (line 1159) and is used in most places.** Chat bubbles use `.textContent` (line 1507), which is safe. Score labels, coaching tips, and offer analysis results pass server data through `escapeHtml()` before inserting via `innerHTML`.
- **Unescaped `innerHTML` assignments from server data:**
  - **Line 1602:** Dimension bar rendering builds HTML strings where `label` is escaped but the structure around it is not parameterized. Currently safe because all dynamic values go through `escapeHtml`.
  - **Lines 2034, 2041, 2044, 2053, 2060, 2063:** Offer analysis results build large HTML strings. All user-visible text passes through `escapeHtml`, which is correct. However, the pattern of string concatenation with `innerHTML +=` is error-prone. One missed `escapeHtml` call in a future edit would introduce XSS.
  - **Lines 2131-2158:** Audit results follow the same pattern. Same risk profile.
  - **Line 2220:** `data.hidden_constraints.map()` passes through `escapeHtml` correctly.
  - **Line 1522:** Typing indicator uses `innerHTML` with hardcoded HTML (no user data). Safe.

- **Recommendation:** Replace `innerHTML +=` string-building with a helper that creates DOM elements programmatically (like `appendBubble` already does). This makes XSS structurally impossible rather than relying on developer discipline.

### User Input Sanitization
- All user inputs are sent to the server as JSON payloads with `Content-Type: application/json`. No URL query parameters carry user data. No `eval()` or `Function()` calls. The `encodeURIComponent` is correctly used on session IDs in URL paths (lines 1408, 1470, etc.).

### Escaping in Dynamic Content
- The `escapeHtml` function (lines 1159-1163) uses the DOM-based `textContent`/`innerHTML` approach, which is correct and handles all HTML special characters. No manual regex-based escaping that could miss edge cases.

---

## 5. Performance

### DOM Queries
- **Repeated `getElementById` calls:** Functions like `renderScorecard` call `getElementById` 10+ times. Each call is O(1) in modern browsers, so this is not a real bottleneck, but caching references in variables at function scope (as done in `drawHistoryChart`) would be cleaner.
- **`document.querySelectorAll('.diff-btn')` (line 1250):** Called on every difficulty button click. Scans the whole DOM for a 3-element set. Negligible cost but could be cached.

### Reflow Triggers
- **`autoResize` (lines 1293-1296):** Sets `el.style.height = 'auto'` then reads `el.scrollHeight`, then sets height again. This causes a forced synchronous layout (reflow) on every keystroke in the chat input. For a single textarea this is acceptable, but it is technically a layout thrash pattern.
- **`container.scrollTop = container.scrollHeight` (line 1511):** Called after every bubble append. Triggers a reflow to compute `scrollHeight`. Again, acceptable for the use case.

### Unoptimized Patterns
- **History chart redraws on every section show (line 2521-2524):** The MutationObserver fires `renderHistory()` every time `sec-history` gains the `active` class. This re-reads localStorage, rebuilds the entire list DOM, and redraws the canvas. For 50 entries max, this is fine, but a dirty flag would be more efficient.
- **`recalcEarnings` runs on every keystroke (lines 1016, 1022, 1029, 1035):** Each input event triggers the full calculation loop (up to 50 iterations). The loop is trivial, but debouncing by ~100ms would avoid unnecessary intermediate calculations.

### Large Inline Script
- The `<script>` block spans lines 1155-2629 (~1,475 lines). This blocks parsing and is not cacheable separately from the HTML. See Section 8 for extraction recommendations.

---

## 6. Accessibility

### ARIA Attributes
- **Well-implemented:** Difficulty radio group uses `role="radiogroup"` with `aria-checked` (lines 298-307). Star rating uses `role="radiogroup"` with per-button `aria-label` (lines 544-549). Hamburger has `aria-expanded` and `aria-controls` (line 187). Modal has `aria-modal="true"` (line 1121).
- **Missing:** The section-based "routing" does not announce section changes to screen readers. When `showSection` hides one view and shows another, there is no `aria-live` region or focus management to inform assistive technology. A screen reader user would not know the view changed.

### Keyboard Navigation
- **Good:** `*:focus-visible` styling is defined (line 169). Enter/Escape keyboard shortcuts are handled for chat input (lines 1382-1391) and modal (line 2592). The home button responds to Enter key (line 182).
- **Missing:** No keyboard navigation between difficulty buttons (left/right arrow keys for the radio group). The `role="radiogroup"` pattern requires arrow key navigation per WAI-ARIA. Currently only click/Enter works.
- **Modal focus trap missing:** When the feedback modal opens (line 2712), focus is not moved into the modal and not trapped. A keyboard user can Tab behind the modal overlay to the hidden page content.

### Screen Reader Announcements
- **Chat messages use `aria-live="polite"` on the container (line 454).** New messages appended to the container will be announced. However, the entire container is the live region, so appending a new bubble announces only the new text (good).
- **Section changes are silent.** No `aria-live` announcement when navigating between Setup, Demo, Chat, Scorecard, etc.

### Focus Management
- **After form submit, focus moves to chat input (line 1355).** Good.
- **After "Try Again", no focus management.** The user is dumped back to the landing section with no focus target.
- **After score animation, no focus management.** The scorecard appears but focus stays wherever it was.

---

## 7. Mobile

### Touch Targets
- **Buttons are generally well-sized.** Primary CTAs use `py-3` or `py-4` (12-16px padding) with full-width, easily exceeding the 44px minimum.
- **Concern:** Navigation links in the desktop nav (line 192) are `px-3 py-1.5`, making them ~28px tall. These are hidden on mobile (`hidden sm:flex`), so the mobile hamburger menu handles this correctly with larger targets (`px-4 py-2`).
- **Star rating buttons (line 545):** `text-3xl` makes these approximately 30x30px. Close to the 44px minimum but may be tight on small phones. The `gap-3` (12px) between them helps prevent mis-taps.

### Viewport Handling
- **`<meta name="viewport" content="width=device-width, initial-scale=1.0">` is set (line 5).** Correct.
- **`min-h-[calc(100vh-57px)]` on sections (line 217):** Uses `vh` units which can cause issues on mobile browsers where the address bar changes height. `dvh` (dynamic viewport height) would be more reliable but has limited support. Acceptable trade-off.

### Scroll Behavior
- **`html { scroll-behavior: smooth; }` (line 127):** Applied globally. This can cause unexpected behavior when programmatically changing sections, as the smooth scroll to top (line 1223) fights with the instant section swap. On mobile, this can feel sluggish.
- **Chat scroll:** `container.scrollTop = container.scrollHeight` (line 1511) snaps to bottom. No smooth scroll here, which is actually correct for chat UX.

### Form Usability
- **Textarea auto-resize (line 1293):** Works well for mobile. Max height capped at 140px prevents the keyboard from pushing the textarea off screen.
- **`novalidate` on the form (line 267):** Disables browser-native validation in favor of custom JS validation. The custom validation (lines 1314-1315) is minimal -- only checks for empty fields, no format validation on the number input.

---

## 8. Code Organization

### The 2,631-Line Single File
This is the primary structural concern. The file is maintainable today because the developer clearly understands it, but it will not scale.

**Problems with the current approach:**
- No code splitting: the entire app downloads and parses before anything renders.
- No caching granularity: changing one function invalidates the entire cached HTML.
- IDE features (find references, refactor) struggle with 1,475 lines of inline JS.
- No testability: functions are globals, not importable modules.

**Recommended extraction points (by natural boundaries):**

| Extract to | Lines | Contents |
|---|---|---|
| `css/app.css` | 26-170 | All custom CSS (animations, scrollbar, print styles, tooltips, responsive overrides) |
| `js/state.js` | 1194-1213 | State object, constants |
| `js/ui.js` | 1159-1296 | Utility functions (escapeHtml, showToast, animateCountUp, autoResize, showSection, mobile menu) |
| `js/chat.js` | 1302-1541 | Form submit, sendMessage, endNegotiation, fetchScorecard, bubble helpers |
| `js/demo.js` | 1806-1989 | All demo-related functions |
| `js/scorecard.js` | 1542-1708 | renderScorecard, feedback system |
| `js/tools.js` | 1991-2175 | Offer analyzer, negotiation audit |
| `js/debrief.js` | 2177-2353 | Debrief, playbook generator |
| `js/calculator.js` | 2358-2391 | Earnings calculator |
| `js/history.js` | 2394-2518 | Score history, chart drawing |
| `js/challenge.js` | 2527-2585 | Daily challenge |
| `js/init.js` | 2587-2628 | Keyboard shortcuts, click-outside handlers, DOMContentLoaded |

This decomposition would reduce the HTML file to ~1,150 lines (pure markup) and create ~12 focused JS modules at 30-150 lines each.

---

## 9. Browser Compatibility

### ES Features Used
- **`async/await`:** Used throughout. Supported in all browsers since 2017 (Chrome 55, Firefox 52, Safari 10.1, Edge 15). No polyfill needed.
- **Optional chaining `?.`:** Used at lines 1529, 1679, 1988, 2406. Requires Chrome 80+, Firefox 72+, Safari 13.1+, Edge 80+. All from early 2020. Safe for modern browsers, but will break on older corporate browsers (IE11, older Edge Legacy).
- **`const`/`let`, arrow functions, template literals, destructuring:** All ES2015+. Universally supported.
- **`navigator.clipboard.writeText`:** Requires HTTPS context. Will fail on HTTP localhost in some browsers. The fallback using `document.execCommand('copy')` (line 1786) handles this, but `execCommand` is deprecated.
- **`performance.now()`:** Widely supported. No issues.
- **`MutationObserver`:** Widely supported since IE11. No issues.
- **No ES2024+ features detected.** No `Object.groupBy`, no `Promise.withResolvers`, no `Array.fromAsync`. The codebase is conservatively ES2020-level.

### CSS Compatibility
- **`backdrop-filter: blur(4px)` (line 103):** Requires `-webkit-` prefix for Safari < 18. Currently unprefixed only. Will not blur on older Safari.
- **Tailwind CDN v3:** Handles vendor prefixes for its own utilities. Custom CSS may need manual prefixing.

---

## 10. Loading Strategy

### First Paint Analysis
The loading sequence is:
1. **Tailwind CDN script (line 7):** Render-blocking. Downloads ~114KB of JS, executes, then generates CSS. This is the single largest bottleneck. First meaningful paint cannot happen until this completes.
2. **Tailwind config (lines 8-23):** Executes synchronously after Tailwind loads. Fast.
3. **Google Fonts preconnect (line 24) + font load (line 25):** Non-blocking due to `display=swap`. Text renders immediately in fallback font, swaps to Inter when loaded. Good.
4. **Inline `<style>` block (lines 26-171):** Parsed synchronously. At ~145 lines, this is negligible.
5. **HTML body (lines 173-1153):** Parsed and rendered. Only `sec-landing` is visible (`.section.active`).
6. **Inline `<script>` block (lines 1155-2629):** Blocks interactivity. At ~1,475 lines, parsing takes 50-100ms on a modern device. On a low-end phone, this could take 200-500ms.

### Tailwind CDN as Bottleneck
The CDN version of Tailwind generates CSS at runtime in the browser. This is explicitly meant for development/prototyping only. For production:
- **Switch to Tailwind CLI or PostCSS build.** This generates a static CSS file containing only the classes actually used, typically 10-30KB gzipped vs. 114KB of runtime JS.
- **Impact:** Removing the CDN script and replacing with a built CSS file would cut first-paint time by 200-500ms on a 4G connection.

### Script Loading Strategy
- **All JS is inline and synchronous.** No `defer`, no `async`, no dynamic imports. The 1,475-line script block at the bottom of `<body>` blocks the `DOMContentLoaded` event.
- **No lazy loading of sections.** All 12 sections' HTML is in the initial payload even though only 1 is visible. The HTML weighs ~40KB uncompressed. For a mostly-text SPA this is acceptable, but sections like the chart canvas and complex forms could be lazy-loaded.

### Recommendations (Priority Order)
1. **Replace Tailwind CDN with a built CSS file.** Single biggest performance win.
2. **Extract JS to external file(s) with `defer`.** Enables browser caching and parallel download.
3. **Add `<link rel="preconnect">` for the API origin** if it is on a different domain.
4. **Consider `fetchpriority="high"` on the font stylesheet** to prioritize Inter loading.

---

## Summary of Priority Fixes

| Priority | Category | Issue |
|---|---|---|
| **P0** | Performance | Replace Tailwind CDN with build-time CSS generation |
| **P0** | Security | Refactor `innerHTML +=` string-building to DOM-based element creation to prevent future XSS regressions |
| **P1** | Accessibility | Add focus trap to feedback modal |
| **P1** | Accessibility | Announce section changes to screen readers |
| **P1** | Accessibility | Add arrow-key navigation to difficulty radio group |
| **P1** | Bug | Fix dead reference to `playbook-opening` element (line 2281) |
| **P1** | JS Quality | Add `AbortController` to in-flight fetches on navigation |
| **P2** | Code Org | Extract JS into separate modules (see Section 8 table) |
| **P2** | CSS | Fix color contrast for `text-white/30` and `text-white/20` elements |
| **P2** | Performance | Extract inline JS to external file with `defer` |
| **P2** | CSS | Add `-webkit-` prefix for `backdrop-filter` |
| **P3** | Mobile | Consider `dvh` units instead of `vh` for section min-height |
| **P3** | JS Quality | Consolidate scattered globals into the `state` object |
| **P3** | Performance | Debounce `recalcEarnings` on keystroke |
