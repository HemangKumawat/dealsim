# DealSim Browser Compatibility Audit

Audited: all files under `static/` (index.html, 12 JS modules, themes.css, 2 SVGs).

---

## 1. CSS Issues

### 1.1 `backdrop-filter` missing `-webkit-` prefix

**Files affected:**
- `index.html` line 148 (`.modal-overlay`)
- `index.html` line 261 (`nav` element via Tailwind `backdrop-blur`)
- `quick-match.js` line 102 (overlay)
- `stats-bar.js` line 28 (`#stats-bar`)
- `themes.css` line 495 (`.theme-switcher`)
- `concept-c-lab.html` line 91

**Already prefixed (no action needed):**
- `theme-switcher.js` lines 208-209 (has both `backdrop-filter` and `-webkit-backdrop-filter`)
- `concept-b-coach.html` (has both prefixes)

**Browsers affected:** Safari < 15.4 (iOS and macOS). Safari 9-15.3 require `-webkit-backdrop-filter`.

**User impact:** ~5-8% of users on older Safari versions. The blur effect silently degrades (no blur, but layout remains functional).

**Fix:** Add `-webkit-backdrop-filter` alongside every `backdrop-filter` declaration. For Tailwind utility classes in HTML, add a custom utility or inline style.

```css
/* Example fix for themes.css */
.theme-switcher {
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
}
```

### 1.2 Scrollbar styling: no Firefox equivalent

**Files affected:**
- `themes.css` lines 239-262 (`::-webkit-scrollbar` rules)
- `index.html` lines 74-77 (`::-webkit-scrollbar` rules)
- `scenario-cards.js` lines 70-73 (`::-webkit-scrollbar` for `.sc-row`)

**Browsers affected:** Firefox uses `scrollbar-width` and `scrollbar-color` instead. The scenario-cards.js file correctly includes both approaches. The main themes.css and index.html do not.

**User impact:** ~3-4% (Firefox users see default browser scrollbar). Purely cosmetic.

**Fix:** Add Firefox-compatible properties alongside WebKit rules:
```css
/* Add to themes.css and index.html <style> */
body {
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) transparent;
}
```

### 1.3 `gap` in flexbox

**Files affected:** Extensively used across all JS modules (`achievements.js`, `engine-peek.js`, `stats-bar.js`, `onboarding.js`, `daily-challenge-card.js`, `learning-path.js`) and in index.html Tailwind classes.

**Browsers affected:** Safari < 14.1 (released April 2021). Flexbox `gap` was not supported before this version.

**User impact:** ~1-2% of users on very old Safari. Elements lose their spacing.

**Fix:** For critical layouts, add `margin` fallbacks. For most users, this is acceptable degradation since Safari 14.1+ is nearly universal now. If needed:
```css
/* Fallback pattern */
.flex-container > * + * {
  margin-left: 12px; /* fallback for gap: 12px */
}
@supports (gap: 12px) {
  .flex-container > * + * {
    margin-left: 0;
  }
}
```

### 1.4 `-webkit-line-clamp` (non-standard)

**Files affected:**
- `daily-challenge-card.js` line 69 (`-webkit-line-clamp:2;-webkit-box-orient:vertical`)

**Browsers affected:** This is actually well-supported everywhere despite the `-webkit-` prefix. Firefox supports it since v68. No action needed.

### 1.5 `inset: 0` shorthand

**Files affected:**
- `themes.css` lines 270, 293, 318 (arena overlays)
- `theme-switcher.js` line 83
- `onboarding.js` lines 71, 84

**Browsers affected:** Safari < 14.1 does not support `inset` shorthand.

**User impact:** ~1-2%. Overlay elements may not be positioned correctly.

**Fix:** Replace with longhand:
```css
top: 0; right: 0; bottom: 0; left: 0;
```

---

## 2. JavaScript Issues

### 2.1 `navigator.clipboard.writeText()` — Clipboard API

**Files affected:**
- `index.html` line 1990 (share score)
- `index.html` line 2558 (copy playbook)

**Browsers affected:** Requires HTTPS context. Not available in HTTP, some WebViews, or very old browsers. IE has no support.

**User impact:** Low. Both usages already have `.catch()` fallbacks. The first one (line 1990) falls back to `document.execCommand('copy')` via a temporary textarea. The second (line 2558) shows a user-friendly error message.

**Status: Already handled correctly.** No fix needed.

### 2.2 `Element.remove()` — DOM convenience method

**Files affected:**
- `theme-switcher.js` line 74
- `daily-challenge-card.js` line 99
- `onboarding.js` lines 512-513, 583-584
- `achievements.js` line 234

**Browsers affected:** IE 11 only (no support). All modern browsers support this.

**User impact:** Negligible (<0.5%). IE 11 is end-of-life.

**Fix (only if IE 11 support is required):**
```js
// Polyfill
if (!Element.prototype.remove) {
  Element.prototype.remove = function() {
    this.parentNode && this.parentNode.removeChild(this);
  };
}
```

### 2.3 `Element.closest()`

**Files affected:**
- `engine-peek.js` line 346

**Browsers affected:** IE 11 only.

**User impact:** Negligible. Same as above.

### 2.4 Arrow functions and template literals

**Files affected:**
- `theme-switcher.js` (uses `=>`, template literals throughout)
- `service-worker.js` (uses `=>`)

**Browsers affected:** IE 11 only. All other browsers support ES6+.

**User impact:** Negligible. The older modules (gamification.js, radar-chart.js, scenario-cards.js, etc.) use `function()` and string concatenation, so they are compatible. Only theme-switcher.js and service-worker.js use ES6 syntax.

**Status: Acceptable.** IE 11 is dead. No action needed.

### 2.5 `const`/`let` declarations

**Files affected:** `achievements.js`, `theme-switcher.js`, `gamification.js`, `service-worker.js`

**Browsers affected:** IE 11 has partial `const`/`let` support (no block scoping in loops). All modern browsers are fine.

**Status: Acceptable.** No action needed.

### 2.6 `Object.assign()`

**Files affected:**
- `theme-switcher.js` lines 82-84, 88-93 (used for style assignment)

**Browsers affected:** IE 11 only.

**Status: Acceptable.**

### 2.7 `requestAnimationFrame`

**Files affected:**
- `achievements.js` line 221
- `celebrations.js` lines 115-116, 186-187

**Browsers affected:** Universally supported in all browsers since 2012. No issue.

### 2.8 `window.matchMedia()`

**Files affected:**
- `celebrations.js` line 16 (prefers-reduced-motion check)

**Browsers affected:** Universally supported. No issue.

### 2.9 `scrollIntoView()` with options object

**Files affected:**
- `quick-match.js` line 85 (`{ behavior: 'smooth', block: 'start' }`)
- `daily-challenge-card.js` line 131 (`{ behavior: 'smooth', block: 'center' }`)
- `onboarding.js` line 465 (`{ behavior: 'smooth', block: 'center', inline: 'nearest' }`)

**Browsers affected:** Safari < 15.4 does not support the options object for `scrollIntoView`. It will still scroll, but without smooth animation and without block positioning.

**User impact:** ~2-3%. Degrades gracefully (scrolls instantly instead of smoothly).

**Fix (if needed):** Use `smooth-scroll-polyfill`:
```html
<script src="https://cdn.jsdelivr.net/npm/smoothscroll-polyfill@0.4.4/dist/smoothscroll.min.js"></script>
```

### 2.10 `Array.includes()`

**Files affected:**
- `theme-switcher.js` lines 336, 361

**Browsers affected:** IE 11 only. All modern browsers support it.

**Status: Acceptable.**

### 2.11 APIs NOT used (confirmed safe)

The following were checked and are NOT present in the codebase:
- `structuredClone` -- not used
- `Array.at()` -- not used
- `Optional chaining (?.)` -- not used
- `Nullish coalescing (??)` -- not used
- `ResizeObserver` -- not used
- `IntersectionObserver` -- not used in main app (only in concept-b-coach.html)
- `Web Animations API (.animate())` -- not used
- `<dialog>` element -- not used
- `inert` attribute -- not used
- `content-visibility` -- not used

---

## 3. HTML/DOM Issues

### 3.1 SVG Favicon

**Files affected:**
- `index.html` line 25: `<link rel="icon" type="image/svg+xml" href="/favicon.svg" />`
- `index.html` line 26: PNG fallback `<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />`

**Browsers affected:** SVG favicons are not supported in Safari < 15 or IE.

**Status: Already handled.** PNG fallback is declared. Browsers that don't support SVG favicons will use the PNG version.

### 3.2 SVG content compatibility (favicon.svg, logo.svg)

Both SVGs use basic elements only (`<rect>`, `<path>`, `<circle>`) with no filters, masks, or advanced features. Fully compatible with all browsers that render SVG (everything since IE 9).

**Status: No issues.**

### 3.3 SVG with SMIL animations (theme-switcher.js Coach effects)

**Files affected:**
- `theme-switcher.js` lines 127-143: `<animate>` elements inside SVG for coach blob effects.

**Browsers affected:** Chrome briefly deprecated SMIL but reversed the decision. All major browsers support SMIL animations. However, IE never supported them.

**User impact:** Negligible. IE users see static blobs instead of animated ones. Purely decorative.

---

## 4. localStorage Availability

**Files affected:** `gamification.js`, `theme-switcher.js`, `daily-challenge-card.js`, `onboarding.js`, `score-trends.js`

**Risk scenarios:**
1. **Safari Private Browsing (iOS < 11):** `localStorage.setItem()` threw `QuotaExceededError`. Fixed in Safari 11+ (2017), which now allows localStorage in private mode (cleared on close).
2. **Firefox Private Browsing:** localStorage works normally since Firefox 48 (2016).
3. **Disabled cookies/storage:** Some corporate environments or privacy extensions block localStorage entirely.

**Current handling:**
- `gamification.js` line 62-68: wraps `localStorage.getItem` in try/catch -- handles errors gracefully.
- `daily-challenge-card.js` line 22: wraps in try/catch.
- `theme-switcher.js`, `onboarding.js`: NO try/catch around localStorage access.

**User impact:** ~0.5-1% could hit errors if localStorage is blocked.

**Fix:** Wrap all localStorage access in a guard:
```js
function storageAvailable() {
  try {
    var x = '__storage_test__';
    localStorage.setItem(x, x);
    localStorage.removeItem(x);
    return true;
  } catch (e) {
    return false;
  }
}
```

Apply in `theme-switcher.js` (lines 343, 360) and `onboarding.js` (lines 502, 542, 579).

---

## 5. Service Worker / PWA

**Files affected:** `service-worker.js`, `manifest.json`

**Browsers affected:** IE and older browsers have no Service Worker support. Safari support since 11.1 (2018).

**Current handling:** Line 245-249 of index.html checks `'serviceWorker' in navigator` before registering. This is correct -- browsers without support simply skip registration.

**Status: Already handled correctly.**

---

## 6. Tailwind CDN

**Files affected:** `index.html` line 50 (`<script src="https://cdn.tailwindcss.com">`)

**Risk:** Using Tailwind CDN in production is not recommended for performance. It works in all modern browsers but adds ~300KB of JavaScript parsing on page load.

**Note:** This is a deployment concern, not a compatibility issue.

---

## Summary: Priority Fixes

| Priority | Issue | Impact | Effort |
|----------|-------|--------|--------|
| **High** | Missing `-webkit-backdrop-filter` in 5 locations | ~5-8% users (older Safari) | 10 min |
| **Medium** | Missing Firefox scrollbar styles in themes.css | ~3-4% users (cosmetic) | 5 min |
| **Medium** | localStorage unguarded in theme-switcher.js, onboarding.js | ~0.5-1% (errors in edge cases) | 10 min |
| **Low** | `inset: 0` shorthand (Safari < 14.1) | ~1-2% | 10 min |
| **Low** | `scrollIntoView` options (Safari < 15.4) | ~2-3% (graceful degradation) | 5 min or polyfill |
| **Low** | `gap` in flexbox (Safari < 14.1) | ~1-2% (layout spacing) | 30 min |
| **None** | IE 11 features (remove, closest, arrow functions, etc.) | <0.5% | N/A |

Overall, the codebase is in good shape. The older JS modules (gamification.js, radar-chart.js, scenario-cards.js, celebrations.js, etc.) deliberately use ES5-compatible syntax. The main gaps are the missing `-webkit-backdrop-filter` prefixes and unguarded localStorage access.
