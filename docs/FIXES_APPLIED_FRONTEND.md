# Frontend Integration Fixes Applied

**Date:** 2026-03-19
**File modified:** `static/index.html`
**Preserves:** All ARIA labels (accessibility agent), loading states & tooltips (UI polish agent)

---

## Critical Integration Fixes (5 broken features repaired)

### 1. Offer Analyzer
- **URL:** Changed `POST /api/analyze-offer` → `POST /api/offers/analyze`
- **Request:** Changed `full_text` → `offer_text`; removed extra `salary`, `bonus`, `equity` fields not in API model
- **Response:** Replaced single-string `data.analysis` reader with structured rendering of `components`, `overall_score`, `overall_market_position`, `key_insights`, and `counter_strategies` (each with proper sub-fields like `negotiability`, `risk_level`, `suggested_counter`)

### 2. Email Audit
- **URL:** Changed `POST /api/audit-negotiation` → `POST /api/tools/audit-email`
- **Request:** Changed `thread_text` → `email_text`; removed `context` field not in API model
- **Response:** Replaced single-string `data.feedback` reader with structured rendering of `overall_score`, `tone`, `strengths`, `issues`, `suggestions`, and `rewrite_hints`

### 3. Debrief
- **"What They Were Thinking":** Replaced `data.opponent_thoughts` (non-existent) with structured cards reading `opponent_target`, `opponent_reservation`, `opponent_pressure`, `hidden_constraints`, `outcome_grade`
- **Move Analysis:** Changed `m.grade` → `m.strength`; changed `m.text` → `m.analysis`; added `m.move_type` badge and `m.missed_opportunity` display
- **Added:** `key_moments`, `best_move`, `biggest_mistake` sections from API response

### 4. Playbook
- **Complete rewrite** of both HTML and JS. Old fields (`opening_moves`, `key_phrases`, `rebuttals`, `walk_away`) replaced with:
  - `style_profile` — "Your Negotiation Style" section
  - `strengths` / `weaknesses` — side-by-side cards
  - `recommendations[]` — cards with `category`, `title`, `description`, `priority`
  - `practice_scenarios` — bulleted list

### 5. Daily Challenge
- Replaced hardcoded `DAILY_CHALLENGES` JS array (7 static items) with `GET /api/challenges/today` API call
- Now reads `title`, `description`, `scenario_prompt`, `date` from backend `ChallengeResponse`
- Graceful fallback to a static challenge if API is unreachable

---

## Conversion Fixes (5 improvements)

### 6. "Money Left on Table" on Scorecard
- Added prominent yellow-bordered card on scorecard (before dimension bars) showing `$X,XXX left on the table`
- Auto-fetches from `/api/sessions/{id}/debrief` after scorecard renders
- Links to full debrief with "See full debrief →"

### 7. Share Score Button
- Added "Share Your Score" button on scorecard (above "Try Again")
- Generates text: "I scored X/100 on DealSim's negotiation simulator! [outcome]. $Y left on the table. Try it: [URL]"
- Copies to clipboard with fallback for older browsers

### 8. Debrief → Playbook CTA
- Added "Get your personalized playbook →" coral CTA button at bottom of debrief section
- Added "Practice Again" secondary button below it
- Eliminates debrief dead-end (previously only had "Back to Scorecard")

### 9. Feedback Modal Trigger
- Wired `openFeedbackModal()` to fire after scorecard view with 15-second delay
- Only triggers after 2nd+ completed session (tracked via `localStorage` counter)
- Avoids interrupting first-time users

### 10. Instant Demo as HERO
- Extracted Demo from the 4-card grid into a full-width hero CTA above other cards
- Larger (2x padding), coral border, glow effect
- Copy: "Try a 60-Second Negotiation — No setup required. Jump in and negotiate with AI right now."
- Remaining 3 cards (Offer Analyzer, Daily Challenge, Earnings Calc) in 3-column grid below

---

## Accessibility Fix

### 11. Low-Contrast Text
- Changed all `text-white/40` → `text-white/70` (19 occurrences)
- Changed all `text-white/50` → `text-white/70` (26 occurrences)
- Ensures WCAG AA compliance (minimum 4.5:1 contrast ratio for normal text on `#1a1b4b` background)

---

## State Changes
- Added `moneyLeftOnTable: null` to global `state` object
- Added `currentChallenge` variable for daily challenge API data
- Added `dealsim_session_count` localStorage key for feedback modal trigger

## Functions Added
- `shareScore()` — clipboard share with fallback
- Inline debrief-fetch in `renderScorecard()` for money-left display

## Functions Modified
- `analyzeOffer()` — new URL, request, response handling
- `runAudit()` — new URL, request, response handling
- `showDebrief()` — new field mapping for all debrief data
- `generatePlaybook()` — complete rewrite for new data structure
- `loadDailyChallenge()` — async, API-backed with fallback
- `startChallenge()` — uses `currentChallenge` from API
- `renderScorecard()` — triggers debrief fetch + feedback modal
