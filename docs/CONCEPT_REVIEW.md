# DealSim Concept Mockup Review

**Date:** 2026-03-19
**Files reviewed:**
- `static/concept-a-arena.html` (1349 lines)
- `static/concept-b-coach.html` (1318 lines)
- `static/concept-c-lab.html` (1326 lines)

---

## 1. Visual Consistency

### Brand Cohesion

All three concepts share:
- Dark background palette (dark navy/black)
- Same system font stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, ...`)
- CSS custom properties for color theming
- Card-based layout patterns
- "DealSim" branding + SimVerse parent mention
- Emoji-based iconography throughout

Each concept has a distinct visual identity:

| Property | Arena | Coach | Lab |
|---|---|---|---|
| Background | `#0f0f23` solid | `#1a1147` to `#2d1b69` gradient | `#0d1117` solid |
| Primary accent | Coral `#f95c5c` | Amber `#f5a623` | Cyan `#58a6ff` |
| Secondary accent | Green `#00ff88` | Purple `#7c5cff` | Orange `#f0883e` |
| Card radius | `1rem` (16px) | `20px` | `6px` |
| Card border | `rgba(255,255,255,0.08)` | `rgba(124,92,255,0.30)` | `#30363d` |
| Mood | Cyberpunk / competitive | Warm / nurturing | GitHub-like / clinical |
| Nav style | Sticky stats bar | Sticky nav with emoji dots | Sticky nav with text links |

**Verdict:** Strong differentiation while maintaining recognizable DealSim DNA. The shared font stack and dark palette keep them in the same family. Lab's visual language is closest to developer tool conventions (GitHub aesthetic), which aligns with its transparency positioning.

---

## 2. Responsive Design

### Arena (Concept A)
- **Breakpoint coverage:** Single breakpoint at `640px` only
- **Missing:** No tablet breakpoint (768px-1024px)
- **Leaderboard grid:** JS-based responsive at 768px (via `fixLbGrid()`) rather than CSS media query -- functional but non-standard
- **Hero:** Uses `clamp()` for font sizing -- good
- **Stats bar:** `flex-wrap: wrap` handles narrow widths
- **Scenario scroller:** Horizontal scroll works on mobile, but no scroll indicators
- **Issue:** `.hood-card` inner grid (`grid-template-columns: 1fr 1fr`) never collapses to single column on mobile

### Coach (Concept B)
- **Breakpoint coverage:** Single breakpoint at `640px`
- **Handles:** Hero flex direction, blob sizing, scenario grid (3col to 2col), garden grid
- **Today's Practice grid:** Uses `grid-template-columns: 1fr 1fr` with no mobile collapse -- will squeeze on small screens
- **Coach's Notes:** Uses `auto-fit, minmax(260px, 1fr)` -- responsive naturally
- **Onboarding overlay:** `padding: 24px` on mobile is good, card has `max-width: 540px`
- **Issue:** The `onboarding-overlay` has `display: none` AND `display: flex` in the same inline style on line 568 -- **the flex declaration wins**, meaning the overlay is visible on page load

### Lab (Concept C)
- **Breakpoint coverage:** Single breakpoint at `768px` -- better threshold than the others
- **Handles:** Market bar stacking, sim-split column direction, hides nav links on mobile
- **Footer grid:** `grid-template-columns: 2fr 1fr 1fr 1fr` never collapses -- **will break on mobile**
- **Scenario grid:** `auto-fill, minmax(280px, 1fr)` -- naturally responsive
- **Flow diagram:** Horizontal scroll with `overflow-x: auto` and `min-width: 700px` -- functional
- **Feedback section:** `grid-template-columns: 1fr 1fr` never collapses on mobile

### Responsive Summary

| Feature | Arena | Coach | Lab |
|---|---|---|---|
| Mobile breakpoint | 640px | 640px | 768px |
| Tablet breakpoint | None | None | None |
| Desktop-first | Yes | Yes | Yes |
| clamp() for type | Yes | Yes | Yes |
| Grid collapse issues | Hood card | Practice grid | Footer, Feedback |
| Nav responsive | Partial (no collapse) | Works | Good (hides links) |

**All three need:** A tablet breakpoint (768px-1024px) and audit of two-column grids that never collapse.

---

## 3. Animation Performance

### Arena (Concept A)
| Animation | Property | GPU-accelerated? |
|---|---|---|
| `gridPulse` | `opacity` | Yes |
| `float` (particles) | `transform`, `opacity` | Yes |
| `livePulse` | `opacity`, `transform` | Yes |
| `firePulse` | `transform` | Yes |
| `shimmer` | `transform` | Yes |
| `ringFill` | `stroke-dashoffset` | **No** -- SVG attribute, repaint only |
| `progressIn` | `width` | **No** -- triggers layout |
| `fadeUp` | `opacity`, `transform` | Yes |
| `spin` | `transform` | Yes |
| Card hover | `transform`, `box-shadow` | `transform` yes, `box-shadow` **no** |

### Coach (Concept B)
| Animation | Property | GPU-accelerated? |
|---|---|---|
| `morphBlob` | `border-radius` | **No** -- triggers layout |
| `floatFace` | `transform` | Yes |
| `fadeSlideIn` | `opacity`, `transform` | Yes |
| `pulse-node` | `box-shadow` | **No** -- triggers repaint |
| `nudgePulse` | `border-color` | **No** -- triggers repaint |
| `growIn` | `transform`, `opacity` | Yes |
| `lightbulbOn` | `filter` | **Partial** -- GPU in some browsers |
| Progress bar fill | `width` | **No** -- triggers layout |
| Card hover | `transform`, `box-shadow` | Mixed |
| Confetti canvas | Canvas 2D | Manual rAF -- good |

### Lab (Concept C)
| Animation | Property | GPU-accelerated? |
|---|---|---|
| `fadeUp` | `opacity`, `transform` | Yes |
| `blink` (cursor) | `opacity` | Yes |
| Card hover | `border-color` | **No** -- triggers repaint |
| Gauge fill | `width` | **No** -- triggers layout |
| Expand icon | `transform` | Yes |
| Range slider | Native | Browser-handled |

### Animation Summary

| Metric | Arena | Coach | Lab |
|---|---|---|---|
| Total animations | 10+ | 10+ | 5 |
| GPU-accelerated % | ~75% | ~55% | ~60% |
| Layout-triggering | `progressIn` (width) | `morphBlob` (border-radius), progress bars | Gauge fills |
| Worst offender | Minor | `morphBlob` runs continuously on 3 elements | None (minimal animation) |

**Coach's `morphBlob` is the main concern** -- it animates `border-radius` on three absolutely positioned elements continuously. On low-end devices this will trigger constant repaints. Fix: use SVG path morphing or `clip-path` instead.

---

## 4. Code Quality

### Arena (Concept A)
- **JS errors:** None found. All functions defined before use.
- **Event listeners:** All properly attached via `onclick` attributes and IIFEs.
- **Logic:** Live counter increments randomly (good fake social proof). Countdown timer works correctly. Emoji feedback has proper deselection logic.
- **Minor issue:** `selectEmoji()` uses `document.querySelectorAll('.emoji-btn')` which selects ALL emoji buttons on the page, not scoped to the feedback section. This could conflict if emoji buttons existed elsewhere.
- **Duplicate CSS:** `@keyframes fadeUp` defined in both the `@media` block and would conflict if both applied.

### Coach (Concept B)
- **Bug (Critical):** Line 568 -- the onboarding overlay has TWO display properties in inline style: `display:none` immediately followed by `display:flex`. **CSS inline styles apply last-wins**, so `display:flex` overrides `display:none`. The overlay is **visible on page load**, blocking the entire page.
- **JS quality:** Good. Onboarding stepper logic is clean. Step dots update correctly.
- **Event listeners:** Mix of `onclick` attributes and proper event delegation. Escape key listener for onboarding -- good accessibility.
- **IntersectionObserver:** Used for progress bar animations, but sets `width: 0%` immediately on all bars, which means if JS fails, bars show empty.
- **Tip rotation:** Uses day-of-year modulo for daily tip -- clever, but `dayOfYear` calculation uses inconsistent date math (divides epoch diff by `86400000` without accounting for DST transitions).

### Lab (Concept C)
- **JS errors:** None found. All functions cleanly scoped.
- **selectStyle():** Uses `innerHTML` assignment -- minor XSS concern if `styleData` values ever come from user input (currently hardcoded, so safe).
- **updatePreview():** Correctly syncs select dropdown with preview panel.
- **Event listeners:** `onmouseenter`/`onmouseleave` inline handlers on scenario cards -- works but verbose. Would benefit from event delegation.
- **Missing:** No keyboard navigation for scenario cards or style selector nodes.
- **Good practice:** `toggleAdvanced()` is clean toggle pattern.

### Code Quality Summary

| Metric | Arena | Coach | Lab |
|---|---|---|---|
| JS bugs | 0 | 1 critical (overlay visible) | 0 |
| Event handling | OK (scope issue) | Good (keyboard support) | OK (no keyboard) |
| Progressive enhancement | Partial | Poor (bars broken without JS) | Good |
| Inline styles | Heavy | Heavy | Heavy |
| CSS organization | Well-sectioned comments | Well-sectioned comments | Clean, minimal |

---

## 5. Psychology Hooks

### Arena (Concept A)

| Hook | Claimed | Implementation | Correct? |
|---|---|---|---|
| **Social proof (anchoring)** | "Top players average 82/100" | Hardcoded in hero | Yes -- anchoring bias sets the reference point |
| **Live counter** | "2,847 negotiations completed today" | JS increments randomly every 2.8s | Yes -- bandwagon effect / social proof |
| **Scarcity / urgency** | "Today's challenge expires in 4h 23m" | Real countdown timer | Yes -- scarcity principle |
| **Variable reward** | Mystery box on Daily Challenge | Shimmer animation on "?" box | Yes -- dopamine-driven variable ratio reinforcement |
| **Loss aversion** | "7-day streak -- Don't break it!" | Static display | Yes -- endowment effect on streaks |
| **Progress / near-miss** | "#247 of 3,102 -- 34 pts to #200" | Static with progress bar | Yes -- goal gradient effect |
| **XP / leveling** | Level 4, 340/500 XP | Animated ring + static numbers | Yes -- operant conditioning via visible progress |
| **Achievement unlocking** | Locked achievements with shimmer | Locked items have grayscale + shimmer overlay | Yes -- Zeigarnik effect (incomplete tasks are remembered) |

**Assessment:** Arena has the densest psychology layer. All hooks are correctly implemented. The combination of variable reward (mystery box), scarcity (countdown), and social proof (live counter + leaderboard) is textbook mobile game retention design.

### Coach (Concept B)

| Hook | Claimed | Implementation | Correct? |
|---|---|---|---|
| **Zeigarnik effect** | "Unfinished negotiation" nudge bar | Pulsing border, resume CTA | Yes -- incomplete task creates tension |
| **Goal setting** | "I want to improve my..." chips | Selectable goal chips in hero | Yes -- self-determination theory (autonomy) |
| **Mastery path** | Learning path with 8 modules | Visual node map with done/current/locked | Yes -- competence building + goal gradient |
| **Personalization** | Onboarding flow (3 steps) | Multi-step modal with scenario/confidence/launch | Yes -- IKEA effect (investment creates ownership) |
| **Growth metaphor** | Achievement Garden | Plants at different growth stages | Yes -- metaphorical progress + endowment |
| **Social learning** | Community insights | Anonymous tip cards | Yes -- social proof via peer learning |
| **Coaching feedback** | Coach's Notes section | Strength/focus/tip cards | Yes -- mastery-oriented feedback (Dweck) |
| **Radar chart / DNA** | "Negotiation DNA" | SVG radar with scored/unscored dimensions | Yes -- incomplete profile drives completion |
| **Daily tips** | Rotating coaching tip | JS rotates based on day-of-year | Yes -- variable content keeps return visits fresh |

**Assessment:** Coach has the most psychologically sophisticated design. The combination of Zeigarnik (unfinished task), growth metaphor (garden), and personalization (onboarding + DNA) creates a nurturing but sticky experience. The "play more to unlock" pattern on the DNA chart is particularly effective.

### Lab (Concept C)

| Hook | Claimed | Implementation | Correct? |
|---|---|---|---|
| **Reciprocity** | Free tools (no signup) | 3 free tools with real previews | Yes -- Cialdini's reciprocity principle |
| **Transparency** | "No black boxes" | Flow diagram, state machine params, scoring breakdown | Yes -- trust-building through openness |
| **Authority** | Market data with sources | "Levels.fyi, Glassdoor, Blind, LinkedIn Salary" | Yes -- authority bias via cited sources |
| **Loss aversion** | Lifetime earnings calculator | "$15k today = $1.24M over 30 years" | Yes -- compounding loss framing |
| **Social proof** | Practitioner testimonials | Career coaches, HR, individuals with quotes | Yes -- authority + social proof |
| **Ownership** | "Your data, stored locally" | Privacy messaging in analytics section | Yes -- data autonomy builds trust |
| **Calibration framing** | Feedback as "engine calibration" | Terminal-style calibration pipeline | Yes -- reframes feedback as collaboration, not complaint |
| **Hidden state** | Locked opponent variables | Redacted terminal display (blocked out text) | Yes -- curiosity gap (Loewenstein) |

**Assessment:** Lab uses trust-building psychology rather than retention psychology. This is the right call for the "data transparency" positioning. The reciprocity play (free tools upfront) and authority signals (cited data sources, published methodology) target a more skeptical, analytical audience.

---

## 6. Cross-Browser Compatibility

### Potential Issues

| CSS Feature | Arena | Coach | Lab | Safari Risk | Firefox Risk |
|---|---|---|---|---|---|
| `backdrop-filter` | Stats bar | Nav, onboarding overlay | Nav | Needs `-webkit-` prefix | OK (since FF 103) |
| `-webkit-background-clip: text` | Hero headline | Hero headline | -- | Needs `-webkit-` prefix (present) | OK with prefix |
| `background-clip: text` | Present (unprefixed) | Present (unprefixed) | -- | Not supported without `-webkit-` | Not supported without `-webkit-` |
| `inset: 0` shorthand | Multiple | Onboarding overlay | -- | OK (Safari 14.1+) | OK (FF 66+) |
| `aspect-ratio` | -- | Garden plots | -- | OK (Safari 15+) | OK (FF 89+) |
| `scrollbar-width: thin` | Scenario scroller | -- | -- | **Not supported in Safari** | OK |
| `::-webkit-scrollbar` | Present | Present | -- | OK | **Not supported in Firefox** |
| `clamp()` | Yes | Yes | Yes | OK (Safari 13.1+) | OK (FF 75+) |
| SVG `filter: drop-shadow()` | -- | Radar chart dots | -- | OK | OK |
| `stroke-dasharray` animation | XP ring | -- | -- | OK | OK |

### Critical Cross-Browser Issues

1. **All three use `backdrop-filter`** -- Arena and Lab include it without the `-webkit-` prefix on the nav element. Coach has both prefixes on the onboarding overlay but the nav uses inline style with only `-webkit-backdrop-filter`. Needs the unprefixed version too for Firefox.

2. **Arena's `background-clip: text`** -- Has both `-webkit-background-clip` and `background-clip` on the hero headline. The unprefixed `background-clip: text` has limited support. Both prefixed and unprefixed are present, which is correct.

3. **Arena's scrollbar styling** -- Uses both `scrollbar-width: thin` (Firefox) and `::-webkit-scrollbar` (Chrome/Safari). This is actually the correct dual approach.

4. **Coach's `aspect-ratio: 1`** on garden plots -- Requires Safari 15+. Older Safari/iOS versions will not maintain square aspect ratio. Consider a `padding-bottom: 100%` fallback.

5. **Lab has no significant cross-browser issues** -- Its minimal animation approach and standard CSS properties make it the safest across browsers.

---

## 7. Shared Elements (Theme System Extraction Candidates)

### Definitely Extract

| Element | Present In | Notes |
|---|---|---|
| **Font stack** | All three | Identical system font stack |
| **Dark background tokens** | All three | Each uses CSS vars, just different values |
| **Card component** | All three | Same pattern: bg + border + radius + shadow + hover |
| **Section label** | All three | Small caps, uppercase, letter-spacing, accent color |
| **Button primary** | All three | Accent bg, white/dark text, hover lift |
| **Button outline/ghost** | All three | Transparent bg, border, hover fill |
| **Difficulty dots** | All three | Row of filled/empty circles |
| **Feedback section** | All three | Emoji-based rating + textarea + submit |
| **Sticky nav** | All three | Sticky, backdrop-filter, border-bottom |
| **Footer** | All three | SimVerse mention, privacy link, copyright |
| **Section spacing** | All three | Consistent padding pattern (60-80px vertical) |
| **Scenario cards** | All three | Emoji + name + difficulty + category tag |
| **Scoring dimensions** | All three | 6-dimension breakdown with bars |
| **SimVerse badge** | All three | "Part of SimVerse" branding |

### Extract with Theme Variants

| Element | Variation by Theme |
|---|---|
| Color tokens | `--accent-primary`, `--accent-secondary`, `--bg-base`, `--card-bg`, `--card-border` |
| Card border-radius | Arena: 16px, Coach: 20px, Lab: 6px |
| Button border-radius | Arena: 8px, Coach: 50px (pill), Lab: 6px |
| Section label color | Uses `--accent-primary` in each |
| Scrollbar styling | Different accent colors |

---

## 8. Feature Comparison Matrix

| Feature | Arena | Coach | Lab |
|---|---|---|---|
| **Hero section** | Cyberpunk grid + particles | Blob illustration + goals | Terminal snippet + CTA |
| **Sticky nav** | Stats bar (XP, streak, rate) | Emoji dot nav + progress btn | Text links + launch btn |
| **Onboarding flow** | None | 3-step modal wizard | None (direct to console) |
| **Game modes** | 3 cards (Quick/Ranked/Daily) | Recommended practice | Simulation console (config) |
| **Leaderboard** | Full (5 players + your rank) | None | None |
| **XP / Level system** | Ring + progress bar | Progress bars only | None |
| **Achievements** | 6 achievement tiles | Achievement Garden (6 plots) | None |
| **Streak tracking** | Fire emoji + stats bar | Progress recap card | None |
| **Learning path** | None | 8-module visual path | None |
| **Negotiation DNA** | None | Radar chart + dimension bars | Radar chart + dimension bars |
| **Coach's notes** | None | 3 personalized cards | None |
| **Daily challenge** | Countdown + mystery reward | Daily tip rotation | None |
| **Scenario browser** | Horizontal scroller (10) | None (recommended only) | Grid with filters (10) |
| **Simulation console** | None | None | Full config panel + preview |
| **Engine transparency** | Code snippet + stats | None | Flow diagram + state machine + params |
| **Free tools** | None | None | 3 tools (analyzer, audit, calculator) |
| **Market data** | None | None | 4-metric intelligence bar |
| **Social proof** | Live counter + leaderboard | Avatar stack + "3,000+ learners" | Practitioner testimonials |
| **Feedback section** | Emoji + textarea | Emoji + textarea + community tips | Structured form (scenario + text) |
| **Privacy messaging** | None | Footer lock icon | "Data stored locally" + footer |
| **Countdown timer** | Hero + daily challenge | None | None |
| **Confetti effect** | None | On progress button + onboarding | None |
| **Keyboard support** | None | Escape closes modal | None |
| **User personas** | None | None | Career coaches, HR, individuals |
| **Methodology link** | None | None | "Read Methodology" CTA |

---

## 9. Best Features Per Concept

### Arena -- Best Competitive/Gamification Elements

1. **Daily Challenge with Mystery Reward** -- The shimmer-animated mystery box + countdown timer is the strongest retention hook across all three concepts. The combination of scarcity (expires today), variable reward (unknown prize), and bonus XP creates a powerful daily return incentive.

2. **Sticky Stats Bar** -- Persistent display of streak, XP, level, win rate, and a "Play Now" CTA. This is superior to a standard nav because it maintains game state awareness at all times. The fire emoji pulse animation on the streak is a small but effective touch.

3. **Leaderboard with Personal Context** -- Not just a top-5 list, but contextualized with "Your Rank: #247 of 3,102 -- 34 pts to #200". The progress bar to the next milestone uses goal gradient effect perfectly.

4. **XP Ring Animation** -- SVG-based circular progress with gradient fill, animated on page load. Visually compelling way to show level progress.

5. **Live Counter** -- "2,847 negotiations completed today" with a pulsing green dot and incrementing numbers. Creates urgency and social validation simultaneously.

### Coach -- Best Warmth/Encouragement Elements

1. **Onboarding Wizard** -- The 3-step flow (scenario preference / confidence emoji slider / personalized first practice) is the best first-run experience of the three. It collects useful data while making the user feel cared for. The confetti on completion is a strong positive reinforcement.

2. **Achievement Garden** -- Replacing traditional badge/trophy systems with a growing garden metaphor is original and warm. The progression from seed to sprout to tree with "empty plots" waiting is more encouraging than locked/unlocked binary states.

3. **Zeigarnik Nudge Bar** -- "You have an unfinished negotiation" with a pulsing border is the most psychologically sophisticated retention hook. It creates genuine cognitive tension that the user wants to resolve.

4. **Coach's Notes** -- Three personalized feedback cards (strength, focus area, actionable tip) frame the system as a supportive mentor rather than a score judge. The "2-question rule" tip is specific enough to feel genuinely helpful.

5. **Negotiation DNA Radar** -- The partially-revealed profile with dashed circles for unscored dimensions and "Play more to unlock" labels creates a completion drive while respecting that the user hasn't earned full assessment yet.

6. **Daily Tip Rotation** -- 7 rotating tips with genuine negotiation advice. Each is specific and actionable, not generic motivation.

### Lab -- Best Data Transparency/Trust Elements

1. **Simulation Console** -- Full configuration panel with scenario dropdown, target value input, difficulty slider, and advanced opponent tuning (aggressiveness, flexibility, risk tolerance, emotional reactivity). The live preview panel updating in real-time is the strongest "you're in control" signal.

2. **Engine Flow Diagram** -- The 5-stage pipeline (Input > Rule Parser > State Machine > Scoring > Output) makes the simulation engine legible. This is the single best trust-building element across all three concepts.

3. **Opponent State Machine Selector** -- Interactive display of 5 negotiation styles with their exact behavioral parameters (aggressiveness: 0.85, flexibility: 0.15, etc.). Clicking between styles and seeing the numbers change builds immediate confidence that the system is deterministic, not random.

4. **Free Tools (Reciprocity)** -- Three genuinely useful free tools (Offer Analyzer, Email Audit, Lifetime Earnings Calculator) with realistic preview data. Each shows enough output to prove value before asking for engagement. The "No signup" tags are trust signals.

5. **Market Intelligence Bar** -- Real-looking market data with cited sources (Levels.fyi, Glassdoor, LinkedIn Salary) and date stamps (2026, updated quarterly). This positions DealSim as a data platform, not just a game.

6. **Hidden State Reveal** -- The redacted opponent variables (`budget_ceiling: ████████ (locked)`) create a curiosity gap while demonstrating that the engine tracks hidden state. The promise of post-session reveal is a strong completion incentive.

7. **Calibration-Framed Feedback** -- Framing user feedback as "engine calibration" with a terminal-style pipeline (`feedback_received > reviewed > weight_adjusted > scenario_version: bumped`) transforms complaining into collaboration.

---

## 10. Critical Bugs

| # | Concept | Severity | Description |
|---|---|---|---|
| 1 | Coach | **P0** | Line 568: Onboarding overlay has `display:none` immediately followed by `display:flex` in the same inline style. The overlay is **visible on page load**, blocking the entire page. Fix: Remove `display:flex` from inline style, add it only in JS. |
| 2 | Arena | P2 | `selectEmoji()` in the feedback section uses global `.emoji-btn` selector. If emoji buttons existed in other sections (they don't currently, but they would in a unified version), selection would break. |
| 3 | Arena | P2 | `.hood-card` two-column grid never collapses on mobile. |
| 4 | Lab | P2 | Footer 4-column grid never collapses on mobile -- will overflow. |
| 5 | Lab | P2 | Feedback section 2-column grid never collapses on mobile. |
| 6 | Coach | P2 | Today's Practice 2-column grid (`1fr 1fr`) will squeeze too narrow on phones. |
| 7 | Coach | P3 | `dayOfYear` calculation doesn't account for DST transitions (off by one occasionally). |

---

## 11. Recommendations for Unified Version

### Must-Have from Each Concept

**From Arena:**
- Daily Challenge mechanic (mystery reward + countdown)
- Sticky stats bar (adapted as persistent progress indicator)
- Leaderboard with personal context

**From Coach:**
- Onboarding wizard (first-run experience)
- Achievement Garden (growth metaphor)
- Coach's Notes (personalized feedback)
- Zeigarnik nudge (unfinished session prompt)
- Negotiation DNA radar

**From Lab:**
- Simulation Console (full configuration)
- Engine transparency section (flow diagram + state machine)
- Free tools (reciprocity play)
- Market intelligence bar
- Calibration-framed feedback
- User persona section (career coaches, HR, individuals)

### Theme System Architecture

The unified version should use CSS custom properties with a theme layer:

```
--ds-bg-base          (Arena: #0f0f23, Coach: #1a1147, Lab: #0d1117)
--ds-bg-card          (Arena: #1a1a2e, Coach: #221758, Lab: #161b22)
--ds-accent-primary   (Arena: #f95c5c, Coach: #f5a623, Lab: #58a6ff)
--ds-accent-secondary (Arena: #00ff88, Coach: #7c5cff, Lab: #f0883e)
--ds-accent-success   (Arena: #00ff88, Coach: #00d68f, Lab: #3fb950)
--ds-border           (per theme)
--ds-radius-card      (Arena: 16px, Coach: 20px, Lab: 6px)
--ds-radius-button    (Arena: 8px, Coach: 50px, Lab: 6px)
--ds-text-dim         (per theme)
```

### Shared Components to Extract
1. `<ds-card>` -- background, border, radius, shadow, hover
2. `<ds-section>` -- label + title + subtitle + divider
3. `<ds-button>` -- primary, outline/ghost variants
4. `<ds-nav>` -- sticky, backdrop-filter, brand + links
5. `<ds-difficulty>` -- dot indicators
6. `<ds-feedback>` -- emoji row + textarea + submit
7. `<ds-footer>` -- SimVerse branding, links, copyright
8. `<ds-scenario-card>` -- emoji + name + difficulty + tags
9. `<ds-gauge>` -- track + fill bar for scoring
10. `<ds-radar>` -- SVG radar chart (Coach + Lab both have this)
