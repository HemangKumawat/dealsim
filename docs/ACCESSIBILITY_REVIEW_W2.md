# DealSim Accessibility Review -- Week 2

**File reviewed:** `static/index.html` (2,102 lines pre-fix, ~2,160 post-fix)
**Date:** 2026-03-19
**Standard:** WCAG 2.1 AA

---

## 1. WCAG 2.1 AA Compliance

### 1.1 Images and Alt Text
- **Status: PASS (with notes)**
- No `<img>` elements are used. All icons are emoji characters (Unicode) or inline SVGs.
- Decorative SVGs now have `aria-hidden="true"` where appropriate (hamburger icon, send arrow, close X).
- The `<canvas>` element for score history now has `role="img"` and `aria-label` describing its purpose. Canvas content remains inaccessible to screen readers since it is drawn programmatically -- a data table fallback would be the ideal long-term fix.

### 1.2 Form Input Labels
- **Status: FIXED -- now PASS**
- **Previously missing:** 15+ form inputs had `<label>` elements without `for` attributes, or no labels at all. This includes:
  - All 6 Opponent Tuner sliders (Aggressiveness, Flexibility, Patience, Market Knowledge, Emotional Reactivity, Budget Authority)
  - All Offer Analyzer inputs (Role, Salary, Bonus, Equity, Location, Full Text)
  - All Earnings Calculator inputs (Current Salary, Negotiated Salary, Years, Raise %)
  - Audit form inputs (Context, Thread Text)
  - Feedback comment textarea and email input (scorecard inline)
  - Modal feedback comment textarea
- **Fix applied:** Added `for="<input-id>"` to all labels. Added `sr-only` class hidden labels for feedback comment and email fields that use placeholder-only patterns.

### 1.3 Color Contrast
- **Status: NEEDS ATTENTION (partial)**
- **Passing pairs:**
  - White (#fff) on navy (#1a1b4b): ratio ~12.5:1 -- PASS
  - Coral (#f95c5c) on navy (#1a1b4b): ratio ~4.6:1 -- PASS (barely meets 4.5:1 for normal text)
  - Emerald (#34d399) on navy: ratio ~7.5:1 -- PASS
  - Yellow (#facc15) on navy: ratio ~9.8:1 -- PASS
- **Failing pairs (not fixed, flagged for manual review):**
  - `text-white/50` (rgba 255,255,255,0.5 = effective #8d8db5 on navy) -- ratio ~3.2:1 -- **FAIL** for body text, PASS for large text only
  - `text-white/40` -- ratio ~2.6:1 -- **FAIL** for all text sizes
  - `text-white/30` -- ratio ~2.0:1 -- **FAIL**
  - `text-white/20` -- ratio ~1.5:1 -- **FAIL** (used for unselected star ratings, placeholder hints)
- **Recommendation:** Increase opacity of body text from `text-white/50` to `text-white/70` minimum. Reserve `text-white/30` and below for decorative or large-text-only use. Placeholder text (`placeholder-white/25`) is exempt per WCAG but still poor UX.

### 1.4 Focus Indicators
- **Status: FIXED -- now PASS**
- **Previously:** Custom `.focus-coral:focus` style used `outline: none` which removed focus indicators for keyboard users on text inputs. Other buttons had no visible focus style.
- **Fix applied:** Added global `*:focus-visible` styles with a 2px coral outline + offset. Added enhanced `box-shadow` ring for buttons, links, and role="button" elements on `:focus-visible`. The existing `.focus-coral:focus` for inputs still works for mouse/click focus, while keyboard focus now has visible outlines.

### 1.5 Keyboard Accessibility
- **Status: IMPROVED -- remaining issues**
- **Fixed:**
  - DealSim logo home link: was a `<div>` with `onclick` only -- now has `role="button"`, `tabindex="0"`, and `onkeydown` Enter handler
  - Skip-to-content link added for keyboard users to jump past navigation
  - All focus-visible styles now render properly
- **Remaining issues (not fixed in this pass):**
  - Difficulty selector buttons use `onclick` only -- they ARE `<button>` elements so they are keyboard-accessible by default. PASS.
  - The section routing system (`showSection()`) does not manage focus -- when switching sections, focus stays on the triggering button instead of moving to the new section heading. This is a usability issue but not a strict WCAG violation.
  - Star rating buttons are individual buttons (fine for keyboard) but have no `role="radiogroup"` semantics. Functional but not ideal.

---

## 2. Mobile Responsiveness (320px - 768px)

### 2.1 Navigation
- **Status: GOOD**
- Hamburger menu appears at `sm:hidden` breakpoint (below 640px)
- Mobile menu is a fixed dropdown below the nav bar
- All sections are accessible from the mobile menu
- **Fixed:** Added `aria-expanded` toggle and `aria-controls` to hamburger button for screen reader clarity.

### 2.2 Form Layout
- **Status: GOOD**
- All form cards use `max-w-2xl` / `max-w-xl` with responsive padding
- Grid layouts (`grid-cols-2`) work well on 320px+ -- inputs stack naturally since each column gets ~140px+
- The Offer Analyzer's 2-column grid at 320px is tight but functional (Tailwind's responsive grid handles it)

### 2.3 Chat Input
- **Status: GOOD**
- Chat textarea uses `flex-1` with a `shrink-0` send button
- Auto-resize JS keeps the textarea manageable
- Max-height constraints (`max-height: 140px`) prevent it from consuming the screen
- `onkeydown` Enter-to-send is appropriate for desktop; mobile keyboards send with the button

### 2.4 Sliders
- **Status: GOOD**
- Range inputs have custom thumb styling (`18px` diameter) which is adequate for touch (Apple HIG recommends 44px minimum, but 18px thumb on a full-width track is acceptable since the track itself is touch-targetable)
- **Recommendation for future:** Increase thumb size to 24px+ for better touch ergonomics

### 2.5 Text Readability
- **Status: GOOD**
- Viewport meta tag is present: `<meta name="viewport" content="width=device-width, initial-scale=1.0">`
- Base font size is system default (16px via Inter)
- Body text at `text-sm` (14px) is readable without zooming on mobile
- Headings scale with `sm:text-5xl` / `text-4xl` breakpoints

---

## 3. Performance

### 3.1 External Resources
- **Tailwind CDN:** `https://cdn.tailwindcss.com` -- runtime CDN, generates CSS on-the-fly. This is the development version and is NOT production-ready. It loads ~100KB+ of JS and generates CSS at runtime. **Recommendation:** Switch to a build step with PostCSS/Tailwind CLI for production. Estimated savings: 80-90KB.
- **Google Fonts:** `https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap` -- loads Inter font with 6 weight variants. The `display=swap` parameter is good (prevents FOIT). However, loading 6 weights is heavy; the page primarily uses 400, 500, 600, 700, 800. **Recommendation:** Drop weight 300 if unused.
- **No other external resources.** No analytics scripts, no third-party libraries, no images.

### 3.2 Render-Blocking Resources
- **Tailwind CDN script:** Blocks rendering (synchronous `<script>` in `<head>`). This is the main performance concern.
- **Google Fonts CSS:** Uses `<link>` which is render-blocking but mitigated by `preconnect` hint and `display=swap`.
- **Inline `<style>` block:** ~90 lines of custom CSS -- negligible impact.
- **Inline `<script>` block:** ~1,150 lines at bottom of body -- does NOT block rendering (good placement).

### 3.3 Estimated Page Weight
| Resource | Estimated Size |
|----------|---------------|
| HTML document | ~70 KB |
| Tailwind CDN JS | ~110 KB (gzipped ~35 KB) |
| Generated CSS (runtime) | ~15 KB |
| Inter font (6 weights) | ~180 KB (gzipped ~90 KB) |
| **Total** | **~375 KB raw, ~210 KB transferred** |

This is lightweight for a single-page app. The main optimization target is replacing Tailwind CDN with a build step.

---

## 4. Fixes Applied

### 4.1 Skip Navigation Link
- Added `<a href="#main-content" class="skip-link">Skip to main content</a>` immediately after `<body>`
- Added `<main id="main-content">` wrapper around all section content
- Added CSS for `.skip-link` that is hidden until focused via keyboard

### 4.2 Focus-Visible Styles
- Added global `*:focus-visible` with `outline: 2px solid #f95c5c; outline-offset: 2px`
- Added enhanced button/link focus styles with coral box-shadow ring
- Keyboard users now see clear focus indicators on all interactive elements

### 4.3 Screen Reader Only Utility
- Added `.sr-only` CSS class (standard pattern for visually hidden but screen-reader-accessible content)
- Applied to feedback comment and email labels that were placeholder-only

### 4.4 ARIA Labels and Roles
- **Navigation:** Added `aria-label="Main navigation"` to `<nav>`
- **Hamburger:** Added `aria-label`, `aria-expanded`, `aria-controls="mobile-menu"` -- JS now toggles `aria-expanded` state
- **Mobile menu:** Added `role="menu"` and `aria-label`
- **All 12 sections:** Added `role="region"` and descriptive `aria-label` to each `<section>`
- **Chat messages:** Added `role="log"` and `aria-live="polite"` to both chat containers (main and demo)
- **Feedback modal:** Added `role="dialog"`, `aria-modal="true"`, `aria-label`
- **Close button (modal):** Added `aria-label="Close feedback dialog"`
- **Star rating buttons (10 total):** Added `aria-label="Rate N star(s)"` to all
- **Error messages (3):** Added `role="alert"` and `aria-live="assertive"` to form-error, offer-error, audit-error
- **Canvas chart:** Added `role="img"` and `aria-label` describing the chart
- **Decorative SVGs:** Added `aria-hidden="true"` to hamburger SVG, send button SVG, modal close SVG
- **Home logo:** Added `role="button"`, `tabindex="0"`, `onkeydown` handler, and `aria-label="DealSim home"`
- **Emoji decorations:** Added `aria-hidden="true"` to the logo rocket emoji

### 4.5 Form Label Associations
- Added `for` attribute to 19 `<label>` elements that were missing explicit input associations:
  - 6 tuner slider labels
  - 6 offer analyzer labels
  - 4 earnings calculator labels
  - 2 audit form labels
  - 1 difficulty group (converted to `aria-labelledby` pattern with `role="group"`)

---

## 5. Remaining Issues (Not Fixed -- Flagged for Future)

### 5.1 High Priority
1. **Low-contrast body text:** `text-white/50`, `text-white/40`, `text-white/30` fail WCAG AA 4.5:1 ratio. These are used extensively for secondary text, descriptions, and labels. Bump to `text-white/70` minimum for body text.
2. **Tailwind CDN in production:** Replace with build-time CSS generation before deploying to production.

### 5.2 Medium Priority
3. **Focus management on section switch:** When `showSection()` is called, focus should move to the new section's heading or first interactive element. Currently focus stays on the triggering button.
4. **Star rating semantics:** Consider wrapping star buttons in a `role="radiogroup"` with `role="radio"` on each star and `aria-checked` state management.
5. **Canvas chart alternative:** Provide a text-based data table as a fallback for screen readers and users who disable JavaScript.
6. **Escape key for modal:** The feedback modal does not close on Escape key press. Add `keydown` listener for `Escape`.

### 5.3 Low Priority
7. **Touch target size:** Slider thumbs (18px) are below the recommended 44px minimum for touch targets. Functional but not ideal.
8. **Print stylesheet:** Print styles hide all sections except playbook -- consider adding a print-accessible view for scorecard.
9. **`prefers-reduced-motion`:** Animations (bubbleIn, fillBar, scorePop, fadeUp) do not respect `prefers-reduced-motion: reduce` media query. Add a media query to disable animations for users who prefer reduced motion.
10. **Font weight 300:** Loaded but appears unused -- drop from the Google Fonts URL to save ~30KB.

---

## Summary

| Category | Before | After |
|----------|--------|-------|
| Labels associated with inputs | ~8 of 23 | 23 of 23 |
| ARIA landmarks on sections | 0 of 12 | 12 of 12 |
| Focus-visible styles | None | Global |
| Skip navigation | Missing | Added |
| Keyboard-accessible logo | No | Yes |
| ARIA on star ratings | None | All 10 labeled |
| Error alerts for screen readers | None | 3 with role="alert" |
| Chat regions announced | No | Yes (role="log", aria-live) |
| Modal semantics | None | role="dialog", aria-modal |
| Hamburger aria-expanded | No | Yes, toggles with JS |

The page was already well-structured with semantic HTML and a good mobile layout. The main gaps were missing ARIA attributes, form label associations, and keyboard focus visibility -- all now addressed. The remaining high-priority item is the low-contrast secondary text, which requires a design decision on opacity values.
