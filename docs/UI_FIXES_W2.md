# UI Fixes Week 2 — DealSim

Date: 2026-03-19
File: `static/index.html` (2102 lines -> 2441 lines)

## 1. Loading States

Every API call now shows a loading indicator:

- **Start Negotiation** button: already had spinner (kept)
- **Demo Start** button: ADDED spinner + disabled state + "Starting..." text
- **Demo Send** button: ADDED spinner, disabled during send
- **Demo Score** fetch: ADDED typing indicator dots in demo chat
- **Chat Send** button: ADDED spinner replacing icon/text, disabled during send
- **End & Score** button: ADDED spinner + "Scoring..." text + disabled state
- **Debrief** button: ADDED spinner on scorecard button + loading skeleton in debrief section
- **Playbook** button: ADDED spinner on scorecard button + loading skeleton in playbook section
- **Offer Analyzer** submit: already had spinner (kept), ADDED disabled state on button
- **Audit** submit: already had spinner (kept), ADDED disabled state on button
- **Feedback Submit** (inline): ADDED spinner + "Sending..." text
- **Feedback Submit** (modal): ADDED "Sending..." text + disabled state

## 2. Error States

- Error messages now styled as alert boxes (coral background, border, rounded) instead of plain text
- Error divs use `role="alert"` for screen readers
- Chat system messages styled as visible alert pills (coral background) instead of invisible gray text
- All error messages made more user-friendly ("Check your connection", "Is the server running?" etc.)
- Form errors scroll into view with `scrollIntoView({ behavior: 'smooth' })`
- Feedback submit failure now shows a toast instead of silent fail
- Demo start failure shows a toast instead of injecting into chat area before it exists

## 3. Empty States

- **Score History**: Replaced plain text with illustrated empty state (chart icon, descriptive text, CTA link to try a demo)
- **Daily Challenge completed**: Enhanced with card wrapper, green border, checkmark icon
- **Debrief pre-state**: Already had "Complete a negotiation" text (kept)
- **Playbook pre-state**: Improved message text for clarity

## 4. Mobile Responsiveness

- Offer form 2-column grids: changed from `grid-cols-2` to `grid-cols-1 sm:grid-cols-2` (stacks on phones)
- Audit/Offer card padding: `p-6 sm:p-8` for tighter mobile padding
- Calculator card padding: `p-6 sm:p-8`
- Chat header: tighter gap on mobile (`gap-2 sm:gap-4`), smaller End button padding (`px-3 sm:px-4`)
- Chat input area: tighter padding on mobile
- Added `@media (max-width: 400px)` breakpoint to stack all 2-col grids to single column on very small screens
- Scorecard action buttons: `grid-cols-1 sm:grid-cols-2` to stack on mobile
- Demo result buttons: added `flex-wrap` for small screens

## 5. Keyboard Navigation

- **Escape key**: closes feedback modal, closes mobile menu, ends negotiation (in chat)
- **Enter key**: sends message in chat (already existed), sends in demo (already existed)
- **Focus-visible**: Added global `:focus-visible` outline style (coral ring) for all interactive elements
- **Modal**: backdrop click closes modal, Escape closes modal
- **Mobile menu**: click-outside closes menu
- **ARIA attributes**:
  - `role="navigation"`, `role="menu"`, `role="menuitem"` on nav elements
  - `role="radiogroup"` + `aria-checked` on difficulty buttons and star ratings
  - `role="dialog"` + `aria-modal` on feedback modal
  - `role="log"` + `aria-live="polite"` on chat messages container
  - `role="alert"` on error messages
  - `aria-label` on hamburger button, chat input, close buttons, star buttons, sliders
  - `aria-expanded` + `aria-controls` on hamburger toggle
- **Home logo**: made keyboard-focusable with `tabindex="0"` and `onkeydown` handler
- All `<label>` elements now have matching `for` attributes on inputs

## 6. Print Stylesheet

- Added `print-color-adjust: exact` for better color reproduction
- Playbook card headings print in dark red (`color: #c0392b`)
- All `.print-white *` children also get white bg + black text
- Cards get `page-break-inside: avoid`
- Card shadows removed in print
- Links underlined in print

## 7. Micro-interactions

- **Button active state**: Global `button:active:not(:disabled) { transform: scale(0.97) }` press effect
- **Button disabled state**: Global `button:disabled { opacity: 0.6; cursor: not-allowed }`
- **Section transitions**: Added `opacity` transition on `.section` class for smooth fade
- **Score count-up**: New `animateCountUp()` function with cubic easing, used on:
  - Main scorecard overall score
  - Demo score
- **Typing indicator**: Now appears in demo chat (not just main chat) via `appendDemoTyping()`/`removeDemoTyping()`
- **Slider thumb hover**: Added `transform: scale(1.2)` on hover
- **Toast notifications**: New toast system for copy confirmation, tuner reset, errors
- **Smooth scroll**: `html { scroll-behavior: smooth }` + `scrollIntoView` on results
- **Quick-action cards**: Added `transition-all duration-200` + text color transition on hover

## 8. Copy/Text Quality

- Error messages rewritten to be actionable ("Check your connection", "Is the server running?")
- Chat placeholder: already clear ("Type your message...")
- Demo input placeholder updated: "Your move... (Enter to send)"
- Opponent role default: "Ready to negotiate" instead of "Loading..."
- Empty playbook message: "Complete a negotiation first to generate your playbook."
- Empty analysis fallback: "No analysis available. Try providing more details."
- All button labels reviewed and kept (already clear)
- Placeholder texts reviewed (already helpful)

## 9. Quick Wins Implemented

1. **Tooltips on opponent tuner sliders**: Each of the 6 sliders now has a hover tooltip explaining what it controls. Uses pure CSS tooltip (`.tooltip-wrap` / `.tooltip-text`) with arrow pointer. Examples:
   - Aggressiveness: "How forcefully the opponent pushes their position..."
   - Budget Authority: "How much power they have to approve your asks..."

2. **Copy to clipboard on playbook**: New "Copy" button next to "Print" in playbook header. Uses `navigator.clipboard.writeText()` with toast confirmation.

3. **Keyboard shortcut hints**:
   - Chat input bar shows: `Enter` to send, `Shift+Enter` new line, `Esc` end & score
   - Demo input placeholder includes "(Enter to send)"

4. **Smooth scroll**: `html { scroll-behavior: smooth }` globally, plus `scrollIntoView({ behavior: 'smooth' })` when results appear (offer analysis, audit results, form errors).

## Additional Improvements

- **Loading skeletons**: Debrief and playbook sections show animated pulse skeleton placeholders while loading (`.skeleton` class with pulse animation)
- **Toast notification system**: Reusable `showToast()` function with slide-up animation
- **Mobile menu a11y**: Proper aria-expanded tracking
- **Consistent disabled states**: All buttons that trigger API calls are disabled during loading to prevent double-submission
