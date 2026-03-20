# DealSim Frontend Performance Analysis (Web Vitals)

**Date:** 2026-03-19
**Scope:** `static/index.html` (2642 lines), `static/themes.css` (655 lines), `nginx/dealsim.conf`

---

## 1. LCP (Largest Contentful Paint)

**Largest element on initial load:** The `<h1>` headline block ("DealSim -- The Flight Simulator for Negotiations") at lines 228-232, roughly 60px tall with `text-4xl sm:text-5xl font-extrabold`. The "Try a 60-Second Negotiation" CTA button block (lines 239-245) is also a strong LCP candidate due to its large padded area.

**Blocking resources:**
- **Tailwind CDN** (`cdn.tailwindcss.com`) at line 7 is loaded as a synchronous `<script>` in `<head>`. This is the single biggest LCP blocker. The Tailwind CDN script is ~100KB+ and must download, parse, and execute before any Tailwind classes resolve. Until it completes, the page renders with broken/unstyled layout.
- **Inline `<style>` block** (lines 25-170, ~145 lines) is parsed synchronously but is fast since it is inline.
- **`themes.css`** is NOT linked in index.html -- it appears to be unused or loaded separately. If it were linked, it would add another blocking resource.

**Estimated LCP:** 1.5-3.0s on 3G, 0.8-1.5s on 4G, depending heavily on Tailwind CDN response time.

**Recommendations:**

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 1 | Replace Tailwind CDN with a pre-built CSS file (run `npx tailwindcss -o styles.css --minify` at build time) | **High** | Medium |
| 2 | If keeping CDN, add `async` or move script to bottom of body (but this breaks class resolution) -- not viable. Build-time compilation is the only real fix. | **High** | Medium |
| 3 | Inline critical CSS for the landing section (above-the-fold styles for sec-landing) and defer the rest | **Medium** | Low |

---

## 2. FID / INP (Interaction to Next Paint)

**Analysis of main-thread JS operations:**

The inline JS (lines 1160-2634, ~1475 lines) is moderate in size. Key observations:

- **No heavy computation on load.** `DOMContentLoaded` calls `loadDailyChallenge()` (a fetch) and `recalcEarnings()` (trivial math). Good.
- **`sendMessage()` / `sendDemoMessage()`**: These are async fetch calls with minimal DOM manipulation (append a bubble, show typing indicator). No long tasks.
- **`renderScorecard()`** (lines 1552-1645): Moderate DOM work -- iterates dimensions, creates HTML via string concatenation, sets innerHTML. For the typical 6 dimensions, this is fast (<5ms).
- **`drawHistoryChart()`** (lines 2453-2516): Canvas 2D rendering. For 50 data points max, this is sub-millisecond.
- **`renderHistory()`** (lines 2417-2451): Iterates up to 50 items, creates DOM nodes in a loop. Could cause minor jank with 50 items but unlikely to exceed 50ms.
- **MutationObserver** watchers (lines 2525-2530, 2585-2590) on section class changes -- lightweight, fire rarely.
- **`animateCountUp()`** uses `requestAnimationFrame` properly. Good.
- **Event tracking** (`trackEvent`) is fire-and-forget fetch with `.catch(() => {})`. Good -- no blocking.

**Potential concern:** `innerHTML` assignments in `analyzeOffer()`, `runAudit()`, and `renderScorecard()` use string concatenation to build HTML. For large API responses (many components, many suggestions), this could cause a long task. In practice, responses are small.

**Estimated INP:** <100ms for all interactions. No expensive JS on the main thread.

**Recommendations:**

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 4 | No critical changes needed. JS is lean and async. | N/A | N/A |
| 5 | Consider `DocumentFragment` for `renderHistory()` if history grows beyond 50 items | **Low** | Low |

---

## 3. CLS (Cumulative Layout Shift)

**Analysis:**

- **Section switching** uses `display: none` / `display: flex` via `.section` / `.section.active` (line 35-36). Sections start hidden, only one is shown at a time. No layout shift on initial load because only `sec-landing` has `active`.
- **Sticky nav** (`sticky top-0 z-50` at line 180) is rendered immediately -- no shift.
- **Font loading**: System font stack (line 18: `-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif`). These are available instantly. Zero FOIT/FOUT risk. No layout shift from font swap.
- **No images** anywhere in the document. All visual elements are text, emoji code points, and inline SVGs.
- **Emoji rendering**: Uses HTML entities (`&#x1F680;`, `&#x26A1;`, etc.) not image-based emoji. Rendered by the OS font. No size change during load.
- **"Money Left on Table" card** (line 508) starts `hidden` and is revealed asynchronously after the debrief fetch completes. This causes a layout shift on the scorecard page, but it happens after user interaction (not on initial load), so it does not count toward CLS.
- **Toast notification** (line 130-135): Fixed position, does not affect layout flow. Good.
- **Theme switcher** (in themes.css): Fixed position bottom-right. No layout impact.

**Potential CLS issue:** The `demo-start-card` is hidden and `demo-chat-area` is shown when the user clicks "Start Demo". This swap happens after a user interaction, so it does not affect CLS. Same for scorecard reveal after negotiation.

**Estimated CLS:** ~0 (excellent). No layout shifts on initial load.

**Recommendations:**

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 6 | Reserve height for `scorecard-money-left` div to prevent shift when it appears | **Low** | Low |
| 7 | No other CLS issues found | N/A | N/A |

---

## 4. Bundle Size

**Current state:** Everything is in a single HTML file.

| Component | Lines | Estimated Size |
|-----------|-------|----------------|
| HTML structure | ~1160 | ~55 KB |
| Inline CSS | ~145 | ~6 KB |
| Inline JS | ~1475 | ~55 KB |
| **Total (uncompressed)** | **2642** | **~116 KB** |
| **Gzipped estimate** | | **~25-30 KB** |

**Assessment:** This is NOT too large. A 25-30 KB gzipped payload is well within acceptable limits. The single-file SPA approach actually has a performance advantage: one HTTP request, no waterfall of CSS/JS fetches.

**The real size problem** is the Tailwind CDN script (~100KB+ minified JS that generates CSS at runtime), which dwarfs the entire application.

**Recommendations:**

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 8 | Keep the single-file SPA structure. Extracting CSS/JS into separate files would add HTTP requests without meaningful benefit at this size. | N/A | N/A |
| 9 | When/if the app grows past ~200KB uncompressed, extract JS into a separate file with `defer` | **Low** | Low |

---

## 5. Tailwind CDN Impact

**Current:** `<script src="https://cdn.tailwindcss.com"></script>` at line 7, synchronous, render-blocking.

This is the single largest performance problem in the application.

**What happens on every page load:**
1. Browser hits `cdn.tailwindcss.com` -- DNS lookup + TLS handshake + download (~100KB+ JS)
2. Browser parses and executes the Tailwind compiler
3. Tailwind scans the DOM for class usage and generates CSS
4. Only THEN can the browser render the page correctly

**On a slow connection (3G):** This adds 2-4 seconds to first meaningful paint.
**On a fast connection:** Still adds 200-500ms due to JS compilation overhead.

**Additional risks:**
- CDN outage = completely broken styling
- No cache benefit across different sites (CDN serves different versions)
- The Tailwind Play CDN is explicitly documented as "not for production"

**Recommendations:**

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 10 | **[HIGHEST PRIORITY]** Switch to build-time Tailwind CSS. Run `npx tailwindcss -i input.css -o dist/styles.css --minify` and link the output. This alone could cut LCP by 1-3 seconds. | **High** | Medium |
| 11 | If build step is not possible, at minimum add `<link rel="preconnect" href="https://cdn.tailwindcss.com">` before the script tag to start the connection earlier | **Medium** | Low |
| 12 | Set up a simple build script: `npx tailwindcss --watch` during development, `--minify` for production | **High** | Low |

---

## 6. Font Loading

**Current:** System font stack only (line 18):
```
-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif
```

**Assessment:** Excellent. No external font files, no FOIT, no FOUT, no layout shift from font swap. GDPR-safe (no Google Fonts). Every platform renders instantly with its native font.

**Lab theme** references `'JetBrains Mono', 'Fira Code', monospace` (themes.css lines 201, 232, 472) but does not load these fonts. Users who have them installed get them; others fall back to `monospace`. This is a graceful degradation with no performance cost.

**Recommendations:** None needed. This is already optimal.

---

## 7. Image Optimization

**Current:** Zero images in the entire application. All visuals are:
- HTML entity emoji (`&#x1F680;`, `&#x26A1;`, `&#x1F4E8;`, etc.)
- Inline SVG icons (hamburger menu, arrows, share icon, etc.)
- Canvas 2D rendering (history chart)
- CSS-only effects (gradients, borders, shadows, animations)

**Emoji rendering:** Uses Unicode code points rendered by the OS emoji font. Performance is excellent -- the browser does not need to load any image resources. On Windows, these render via Segoe UI Emoji; on macOS via Apple Color Emoji. Both are pre-loaded system fonts.

**SVG icons** are inline (not fetched), so zero HTTP requests.

**Recommendations:** None needed. Zero-image approach is ideal for performance.

---

## 8. Caching Strategy

**Current nginx config:** No caching headers are configured. Every request goes to the backend proxy.

**What should be cached:**

| Resource | Cache Strategy | Recommended Header |
|----------|---------------|--------------------|
| `index.html` | Short cache + revalidate | `Cache-Control: public, max-age=300, must-revalidate` (5 min) |
| `themes.css` | Long cache with hash | `Cache-Control: public, max-age=31536000, immutable` (if filename-hashed) |
| `/api/challenges/today` | Cache for the day | `Cache-Control: public, max-age=3600` |
| `/api/sessions/*` | No cache | `Cache-Control: no-store` |
| `/api/feedback` | No cache | `Cache-Control: no-store` |
| `/api/events` | No cache | `Cache-Control: no-store` |

**Recommendations:**

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 13 | Add a `location /static/` block in nginx with `expires 7d` and `add_header Cache-Control "public, max-age=604800"` for static assets | **High** | Low |
| 14 | Enable gzip compression in nginx: `gzip on; gzip_types text/html text/css application/javascript application/json;` | **High** | Low |
| 15 | Add `ETag` and `Last-Modified` headers for the HTML file | **Medium** | Low |
| 16 | Set `Cache-Control: no-store` on all `/api/sessions/` responses | **Low** | Low |

---

## 9. Theme Switching Performance

**Analysis of themes.css:**

The theme system uses CSS custom properties (`var(--bg)`, `var(--accent)`, etc.) switched via `[data-theme]` attribute on `<html>`. This is the optimal approach.

**Will switching cause a flash?**
- The `.theme-transition` class (lines 92-101) adds `transition: background-color 0.5s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease` to all elements. This creates a smooth cross-fade, not a flash.
- However, `theme-transition *` with the wildcard selector applies transitions to EVERY element in the DOM. For a page with hundreds of elements, this creates hundreds of simultaneous CSS transitions, which could cause jank on low-end devices.

**Will switching cause layout shift?**
- Theme changes only affect colors, shadows, and border-radius -- no width, height, padding, or margin changes. Border-radius changes (e.g., Coach theme uses `border-radius: 20px` vs Arena's `12px`) do not affect layout. No CLS from theme switching.

**Arena theme effects** (grid overlay, scanline, particles, glow pulse) use fixed-position elements with `pointer-events: none` and CSS-only animations. The particle animation at line 346 animates `translateY(100vh)` to `translateY(-20vh)` -- this uses GPU-composited transforms, not layout-triggering properties. Good.

**Coach theme effects** (morphing blobs with `filter: blur(80px)`) are expensive. Three 300-500px blurred elements with continuous animation will consume GPU resources. On low-end mobile devices, this could cause frame drops. The `prefers-reduced-motion` media query (lines 613-631) correctly disables all animations. Good.

**Recommendations:**

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 17 | Replace `.theme-transition *` with explicit class targets (`.ds-card, .ds-btn, .ds-input, body, nav`) to avoid transitioning hundreds of elements | **Medium** | Low |
| 18 | Add `will-change: transform` to `.coach-blob` elements to hint GPU compositing | **Low** | Low |
| 19 | Consider reducing Coach blob blur from 80px to 40px on mobile via media query | **Low** | Low |

---

## 10. Connection Overhead (HTTP Requests on Initial Load)

**Requests for a fresh page load:**

| # | URL | Type | Blocking? | Size |
|---|-----|------|-----------|------|
| 1 | `/` (index.html) | Document | Yes | ~25-30 KB gzipped |
| 2 | `cdn.tailwindcss.com` | Script | **Yes (render-blocking)** | ~100KB+ |
| 3 | `/api/challenges/today` | XHR | No (async, DOMContentLoaded) | ~0.5 KB |

**Total: 3 HTTP requests.** Only 2 are required for first paint.

This is excellent. Most SPAs make 10-20 requests on initial load. The single-file architecture pays off here.

After Tailwind CDN elimination (recommendation #10), initial load would be just 1 HTTP request for the full application.

**Recommendations:**

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 20 | Eliminating Tailwind CDN reduces blocking requests from 2 to 1 | **High** | (see #10) |
| 21 | Lazy-load the daily challenge fetch -- defer it until the user navigates to that section (it already uses a MutationObserver, but `loadDailyChallenge()` is also called in DOMContentLoaded at line 2631) | **Low** | Low |

---

## Priority Summary

### High Impact
1. **Replace Tailwind CDN with build-time CSS** (#10, #12) -- estimated LCP improvement of 1-3 seconds. This is the single most impactful change.
2. **Add nginx gzip compression** (#14) -- reduces transfer size by 60-70%.
3. **Add nginx caching headers for static assets** (#13) -- eliminates redundant downloads on repeat visits.

### Medium Impact
4. **Preconnect to Tailwind CDN** (#11) -- quick win if CDN elimination is deferred.
5. **Inline critical CSS for above-the-fold content** (#3) -- faster first paint.
6. **Scope theme transition selector** (#17) -- smoother theme switching on low-end devices.

### Low Impact (Polish)
7. Reserve height for money-left card (#6)
8. Defer daily challenge load (#21)
9. GPU hints for Coach blobs (#18, #19)
10. Use DocumentFragment for large lists (#5)

### Already Optimal
- Font loading (system fonts, zero external requests)
- Image strategy (zero images, emoji + inline SVG)
- JS bundle size (lean, no frameworks)
- CLS on initial load (~0)
- FID/INP (<100ms for all interactions)
- HTTP request count (3 total, could be 1)
