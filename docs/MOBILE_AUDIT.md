# DealSim Mobile Usability Audit

**Auditor:** Mobile-first frontend specialist
**Date:** 2026-03-19
**File:** `static/index.html` (2631 lines, single-page app with Tailwind CSS)
**Viewport tested against:** 375px (iPhone SE), 390px (iPhone 14), 768px (iPad)

---

## Executive Summary

The app is reasonably well-structured for mobile. The viewport meta tag is correct, a hamburger menu exists, and most layout uses Tailwind responsive utilities. However, there are **18 issues** across touch targets, slider usability, text sizing, scroll containment, and edge-case layout breakage that would degrade the phone experience.

**Severity key:** CRITICAL = broken on mobile, HIGH = significant UX pain, MEDIUM = noticeable friction, LOW = polish

---

## 1. Navigation

### 1.1 Hamburger Menu - WORKS

The hamburger button (`#nav-hamburger`) is present at `sm:hidden`, toggles `#mobile-menu`, and the JS correctly toggles `hidden` and `aria-expanded`. Clicking outside or pressing Escape closes it. Each menu item calls `closeMobileMenu()` after navigation.

### 1.2 MEDIUM - Mobile menu button items too small for comfortable touch

**Lines 203-210.** Each menu button has `px-4 py-2` which yields roughly 36px height. Apple HIG and WCAG recommend minimum 44px touch targets.

**Fix:**
```diff
- class="block w-full text-left px-4 py-2 rounded-lg text-white/60 hover:bg-white/5 text-sm"
+ class="block w-full text-left px-4 py-3 rounded-lg text-white/60 hover:bg-white/5 text-sm"
```
Change `py-2` to `py-3` on all 8 mobile menu buttons (lines 203-210). This brings the target to ~44px.

### 1.3 MEDIUM - Desktop nav items missing from mobile menu

The desktop nav (line 191-198) shows Setup, Demo, Offers, Audit, Calculator, History. The mobile menu (lines 203-210) shows Setup, Demo, Offer Analyzer, Negotiation Audit, Earnings Calculator, Opponent Tuner, Score History, Daily Challenge. This is actually better -- mobile has MORE items. No issue here.

### 1.4 LOW - No visual indicator for active section in mobile menu

Neither the desktop nav nor the mobile menu highlights the currently active section. On mobile where screen real estate is limited, this is disorienting.

**Fix:** In the `showSection()` JS function (line 1218), add active state tracking:
```js
// After closeMobileMenu():
document.querySelectorAll('.nav-link, #mobile-menu button').forEach(b => b.classList.remove('text-white', 'bg-white/10'));
// Highlight matching button based on section id
```

---

## 2. Chat Interface

### 2.1 WORKS WELL

The chat section (`#sec-chat`, line 425) uses `flex-col min-h-[calc(100vh-57px)]` which fills the screen. The message area (`#chat-messages`, line 454) is `flex-1 overflow-y-auto` so it scrolls correctly. The input bar is pinned at the bottom with `border-t` and `backdrop-blur`.

### 2.2 MEDIUM - Chat messages too wide on small screens

Line 1503: Bubbles use `max-w-[75%] sm:max-w-[60%]`. On a 375px screen, 75% = 281px. This is fine. However, the padding reduction at line 165 (`#sec-chat .max-w-3xl { padding-left: 4px; padding-right: 4px; }`) is too aggressive -- bubbles nearly touch the screen edge.

**Fix (line 165):**
```css
@media (max-width: 640px) {
  #sec-chat .max-w-3xl { padding-left: 8px; padding-right: 8px; }
}
```

### 2.3 HIGH - Chat input textarea may be obscured by virtual keyboard on iOS

The input bar (line 457) uses `backdrop-blur` and sits at the natural document flow bottom. On iOS Safari, the virtual keyboard pushes viewport but the fixed-position-like bar may get hidden. The bar is NOT `position: fixed` (it is flow-based inside a flex column), which is actually correct -- the flex layout handles this. However, `min-h-[calc(100vh-57px)]` does not account for the keyboard.

**Fix:** Add to the `<style>` block:
```css
@supports (height: 100dvh) {
  #sec-chat { min-height: calc(100dvh - 57px); }
}
```
This uses dynamic viewport height which adjusts for the virtual keyboard on modern mobile browsers.

### 2.4 LOW - Keyboard shortcut hints unhelpful on mobile

Lines 475-479 show `Enter`, `Shift+Enter`, `Esc` keyboard hints below the chat input. These are meaningless on mobile.

**Fix:**
```diff
- <p class="text-center text-white/20 text-xs mt-2 max-w-3xl mx-auto">
+ <p class="text-center text-white/20 text-xs mt-2 max-w-3xl mx-auto hidden sm:block">
```

---

## 3. Forms

### 3.1 WORKS - Input sizing

All form inputs use `px-4 py-3` (line 274, 292, 315, etc.) which yields ~44-48px height. This meets touch target requirements.

### 3.2 MEDIUM - Landing form card padding too generous on mobile

Line 265: `p-8` on the form card is 32px. On a 375px screen, that leaves only 311px for content (375 - 32 - 32). With `px-4` outer padding, effective width is 375 - 16 - 16 - 32 - 32 = 279px.

**Fix:**
```diff
- <div class="bg-navy-card rounded-2xl border border-white/10 p-8 shadow-2xl">
+ <div class="bg-navy-card rounded-2xl border border-white/10 p-5 sm:p-8 shadow-2xl">
```

### 3.3 MEDIUM - Select dropdown arrow hard to tap

Line 272-283: The custom select has a pointer-events-none arrow icon. The select itself is full width, so this is fine. But the visual affordance (the small chevron in `right-3`) could be larger on touch.

No code change needed -- the entire select is tappable.

### 3.4 LOW - Difficulty buttons may be cramped on narrow screens

Line 298: `<div class="flex gap-3">` with three `flex-1` buttons. At 375px with form padding, each button gets roughly 80px width. The text "Medium" fits, but barely.

**Fix (optional):**
```diff
- <div class="flex gap-3" role="radiogroup">
+ <div class="flex gap-2 sm:gap-3" role="radiogroup">
```

---

## 4. Sliders (Opponent Tuner)

### 4.1 HIGH - Slider thumb too small for reliable touch interaction

Lines 89-99: The slider thumb is 18x18px with a 2px border, making the visual target only 18px. Apple HIG requires 44px minimum for touch targets.

**Fix (CSS, line 89-99):**
```css
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none; appearance: none;
  width: 28px; height: 28px; border-radius: 50%;
  background: #f95c5c; cursor: pointer; border: 2px solid #fff;
  transition: transform 0.15s ease;
}
input[type="range"]::-moz-range-thumb {
  width: 28px; height: 28px; border-radius: 50%;
  background: #f95c5c; cursor: pointer; border: 2px solid #fff;
}
```
Increase from 18px to 28px. The track height (6px, line 87) provides enough contrast.

### 4.2 MEDIUM - Tooltips hover-only, invisible on touch devices

Lines 139-151: Tooltips use `:hover` and `:focus-within` to show. On mobile, hover does not exist (except on long-press which is unreliable). The `cursor-help` on labels (line 836) is also meaningless on touch.

**Fix:** Add touch-friendly tooltip activation. In the `<style>` block, add:
```css
@media (hover: none) {
  .tooltip-wrap .tooltip-text {
    position: static; transform: none; max-width: 100%;
    margin-top: 4px; visibility: visible; opacity: 0.7;
    font-size: 11px; padding: 4px 0; background: none; border: none;
    color: rgba(255,255,255,0.4);
  }
  .tooltip-wrap .tooltip-text::after { display: none; }
}
```
This shows the tooltip as inline hint text on touch devices instead of a hover popup.

### 4.3 LOW - Slider value display small

Lines 839, 852, etc.: The current value display (`text-sm text-coral font-semibold`) is 14px. Readable but could be more prominent since it is the primary feedback for the slider.

No change needed -- meets minimum.

---

## 5. Score History Chart

### 5.1 WORKS - Canvas resizes correctly

Line 936: `<canvas id="history-chart" height="200" class="w-full">`. The `drawHistoryChart` function (line 2448) reads `getBoundingClientRect()` and scales by `devicePixelRatio`. This correctly adapts to mobile widths.

### 5.2 MEDIUM - Chart too short on mobile for readability

The canvas has `height="200"` as an HTML attribute. On a 375px wide screen, a 200px tall chart with 40px left padding and 30px bottom padding leaves only 130px of plot height. Data points may overlap.

**Fix:**
```diff
- <canvas id="history-chart" height="200" class="w-full"></canvas>
+ <canvas id="history-chart" height="200" class="w-full sm:h-auto" style="min-height: 180px;"></canvas>
```
The canvas height is fine at 200px. The real fix is in the JS -- the chart already handles this via `getBoundingClientRect()`. No change needed after review.

### 5.3 LOW - No touch interaction on chart

The chart is draw-only with no tap-to-see-score interaction. This is a feature gap, not a bug.

---

## 6. Scorecard

### 6.1 WORKS - Layout is single-column

The scorecard (line 487-584) uses `max-w-2xl mx-auto` with `px-4` padding. All content stacks vertically. The dimension bars (`#dimension-bars`, line 513) render in a `space-y-4` stack. Fully readable on 375px.

### 6.2 LOW - Large score circle may feel oversized on small screen

Line 495: The overall score display is `w-36 h-36` (144x144px). On a 375px screen, this takes 42% of the width. It is centered and looks intentional (hero element), so no change needed.

### 6.3 MEDIUM - Action buttons grid could benefit from full-width on mobile

Line 523: `<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">`. This already stacks to 1 column on mobile. Correct behavior.

---

## 7. Offer Analyzer

### 7.1 WORKS - 2-column form stacks correctly

Lines 756 and 769: `<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">`. Both grid sections correctly stack to single column below `sm` (640px). Verified.

### 7.2 MEDIUM - Form card padding

Line 747: `p-6 sm:p-8`. Already has responsive padding. Good.

### 7.3 LOW - Offer result card scroll position

Line 2070: `scrollIntoView({ behavior: 'smooth', block: 'start' })`. On mobile, this may scroll the result behind the sticky nav.

**Fix (line 2070):**
```diff
- document.getElementById('offer-result').scrollIntoView({ behavior: 'smooth', block: 'start' });
+ document.getElementById('offer-result').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
```

---

## 8. Daily Challenge

### 8.1 WORKS - Card layout is mobile-friendly

The challenge card (line 970) uses `p-8` which is slightly generous. The button at line 978-981 is full-width (`flex-1` in a flex container).

### 8.2 MEDIUM - Challenge card padding too much on small screens

Line 970: `p-8` = 32px on each side. On 375px with outer `px-4`, inner width = 375 - 16 - 16 - 32 - 32 = 279px.

**Fix:**
```diff
- <div id="challenge-card" class="bg-navy-card rounded-2xl border border-white/10 p-8">
+ <div id="challenge-card" class="bg-navy-card rounded-2xl border border-white/10 p-5 sm:p-8">
```

---

## 9. Modals

### 9.1 WORKS - Feedback modal responsive

Line 1122: `max-w-md w-full mx-4`. The `mx-4` provides 16px margin on each side, so on 375px the modal is 343px wide. The modal uses `flex items-center justify-center` on the overlay, centering it vertically. Escape key and overlay click both close it.

### 9.2 LOW - Modal could be bottom-sheet on mobile

On phones, centered modals feel less native than bottom sheets. This is a UX improvement, not a bug.

### 9.3 MEDIUM - Star rating buttons small for touch

Lines 1131-1135: Star buttons use `text-3xl` which is about 30px font-size, but the actual tap target is only the star glyph. No padding is added.

**Fix:**
```diff
- class="modal-star text-3xl text-white/20 hover:text-yellow-400 transition-colors"
+ class="modal-star text-3xl text-white/20 hover:text-yellow-400 transition-colors p-1"
```
Same fix for the scorecard inline stars (lines 545-549):
```diff
- class="star-btn text-3xl text-white/20 hover:text-yellow-400 transition-colors"
+ class="star-btn text-3xl text-white/20 hover:text-yellow-400 transition-colors p-1"
```

---

## 10. Scrolling

### 10.1 WORKS - No horizontal overflow detected

The body has no `overflow-x: hidden` (risky) but all content uses `w-full`, `max-w-*` with `mx-auto`, and `px-4` outer padding. The only risk is:

### 10.2 HIGH - Quick action cards grid can overflow on very small screens

Line 249: `<div class="grid grid-cols-3 gap-3 mb-10">`. On 375px with `px-4` outer padding, each card gets (375 - 32 - 24) / 3 = 106px. The emoji + text inside is tight but fits.

However, the media query at line 161-163 only targets `.grid-cols-2` at 400px breakpoint, not `grid-cols-3`. On screens below 320px (rare but possible), the 3-column grid will overflow.

**Fix (line 161):**
```css
@media (max-width: 400px) {
  .grid-cols-2, .grid-cols-3 { grid-template-columns: 1fr !important; }
}
```
Or better, use Tailwind responsive on the element directly:
```diff
- <div class="grid grid-cols-3 gap-3 mb-10">
+ <div class="grid grid-cols-3 gap-2 sm:gap-3 mb-10">
```

### 10.3 MEDIUM - Chat scroll behavior

Line 454: `#chat-messages` uses `overflow-y-auto`. The container is `flex-1` inside a flex column, so it grows to fill available space and scrolls internally. The `scrollTop = scrollHeight` calls in JS (lines 1511, 1524, 1539, 1972, 1984) correctly auto-scroll on new messages.

However, there is no `overscroll-behavior: contain` to prevent the chat scroll from propagating to the page scroll.

**Fix (line 454):**
```diff
- <div id="chat-messages" class="flex-1 overflow-y-auto px-4 py-6 space-y-4 max-w-3xl w-full mx-auto">
+ <div id="chat-messages" class="flex-1 overflow-y-auto px-4 py-6 space-y-4 max-w-3xl w-full mx-auto overscroll-contain">
```

### 10.4 MEDIUM - Demo chat area has max-height that may be too small

Line 382: `max-h-[400px]`. On a 375px x 667px screen (iPhone SE), after the nav (57px), heading area (~120px), and input area (~80px), only ~410px remain. The 400px max-height is fine but the demo section itself is not flex-based like the main chat, so the input may get pushed off-screen when many messages accumulate.

No critical fix needed -- the 400px scroll container handles this.

---

## 11. Text

### 11.1 WORKS - Font sizes meet minimum

All body text uses `text-sm` (14px) or larger. The smallest text instances:
- `text-xs` (12px): Used for labels, timestamps, tracking badges, and helper text. This is acceptable for secondary information.
- `text-white/30 text-xs` (line 341, 1060): Privacy/disclaimer text at 12px with 30% opacity is very hard to read on mobile in bright light.

### 11.2 LOW - Low-contrast helper text

Lines 341, 476, 1060: Text at `text-white/30 text-xs` or `text-white/20 text-xs` is 12px at 20-30% opacity on a dark background. While intentionally subtle, it may fail WCAG contrast on mobile.

**Fix:**
```diff
- text-white/20 text-xs
+ text-white/40 text-xs
```
Raise minimum opacity from `/20` and `/30` to `/40` for any text that conveys information.

### 11.3 WORKS - Line lengths

`max-w-2xl` (672px) and `max-w-xl` (576px) containers with `px-4` padding keep line lengths well under 80 characters on mobile. Good.

---

## 12. Print

### 12.1 WORKS - Print styles exist

Lines 108-117: The `@media print` block sets white background, hides all sections except `#sec-playbook`, hides `.no-print` elements, and styles `.print-white` cards with borders instead of dark backgrounds.

### 12.2 MEDIUM - Print from mobile may include nav bar

The `#global-nav` is not hidden in print styles. On mobile Chrome print, the sticky nav will appear at the top of the printed page.

**Fix (add to line 112):**
```css
@media print {
  #global-nav { display: none !important; }
  /* ... existing rules ... */
}
```

### 12.3 LOW - Playbook grid may not print well

Line 709: `<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">`. In print mode, Tailwind responsive classes may not apply as expected since print rendering doesn't use viewport width. The `page-break-inside: avoid` on line 115 helps.

---

## 13. Earnings Calculator

### 13.1 HIGH - 2-column grid does NOT stack on mobile

Line 1024: `<div class="grid grid-cols-2 gap-4 mb-5">` for "Years in Career" and "Annual Raise %" inputs. This is a hardcoded 2-column layout with NO responsive breakpoint. On 375px, each input gets ~155px width, which is barely usable.

The media query at line 161-163 targets `.grid-cols-2` below 400px and forces 1-column, BUT this uses `!important` on the Tailwind utility class name as a CSS selector. Since Tailwind generates the class `.grid-cols-2` with `grid-template-columns: repeat(2, minmax(0, 1fr))`, the `!important` override works.

**Verdict:** Actually handled by the 400px media query. However, between 400px and 640px the 2-column layout is still active and cramped.

**Fix:**
```diff
- <div class="grid grid-cols-2 gap-4 mb-5">
+ <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
```

### 13.2 MEDIUM - Results 3-column grid cramped on mobile

Line 1045: `<div class="grid grid-cols-3 gap-4 text-center text-xs">`. On 375px minus padding, each column is about 90px. The dollar amounts like "$475,000" at `text-xs` (12px) font-weight `font-semibold` fit but are tight.

**Fix:**
```diff
- <div class="grid grid-cols-3 gap-4 text-center text-xs">
+ <div class="grid grid-cols-3 gap-2 sm:gap-4 text-center text-xs">
```

---

## Summary of All Fixes

| # | Severity | Section | Issue | Fix |
|---|----------|---------|-------|-----|
| 1 | MEDIUM | Navigation | Menu items 36px height | `py-2` to `py-3` |
| 2 | MEDIUM | Chat | Padding too tight (4px) | Change to `8px` |
| 3 | HIGH | Chat | iOS keyboard + viewport | Add `100dvh` support |
| 4 | LOW | Chat | Keyboard hints on mobile | Add `hidden sm:block` |
| 5 | MEDIUM | Forms | Card padding `p-8` on mobile | `p-5 sm:p-8` |
| 6 | LOW | Forms | Difficulty button gap | `gap-2 sm:gap-3` |
| 7 | HIGH | Sliders | 18px thumb too small | Increase to 28px |
| 8 | MEDIUM | Sliders | Tooltips hover-only | Show inline on touch |
| 9 | MEDIUM | Cards | Challenge card padding | `p-5 sm:p-8` |
| 10 | MEDIUM | Modal | Star rating touch targets | Add `p-1` padding |
| 11 | HIGH | Scrolling | 3-col grid missing from 400px override | Add `.grid-cols-3` to media query |
| 12 | MEDIUM | Scrolling | Chat scroll propagation | Add `overscroll-contain` |
| 13 | HIGH | Calculator | 2-col grid not responsive | `grid-cols-1 sm:grid-cols-2` |
| 14 | MEDIUM | Calculator | Results grid gap | `gap-2 sm:gap-4` |
| 15 | MEDIUM | Print | Nav visible in print | Hide `#global-nav` in print |
| 16 | LOW | Text | Low-contrast helper text | Raise opacity to `/40` |
| 17 | LOW | Offer | scrollIntoView behind nav | Use `block: 'nearest'` |
| 18 | LOW | Nav | No active section indicator | Add active class tracking |

**HIGH priority fixes (4):** iOS viewport, slider thumbs, 3-col grid overflow, calculator layout.
**MEDIUM priority fixes (9):** Touch targets, padding, tooltips, scroll containment, print nav.
**LOW priority fixes (5):** Polish items that improve experience but are not broken.
