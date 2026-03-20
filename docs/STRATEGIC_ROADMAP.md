# DealSim Strategic Roadmap

**Date:** 2026-03-20
**Source:** Synthesis of 20+ agent analyses covering deployment, monetization, marketing, legal, retention, competitive landscape, performance, accessibility, testing, scalability, and content strategy.
**Production Readiness Score:** 68/100 (ship-ready for private beta after blockers fixed)

---

## The One-Line Strategy

**Ship the simplest version this week. Measure cost per session and completion rate. Add features only when data says users want them.**

---

## Phase 0: Pre-Launch Blockers (Do This Week)

These must be fixed before any public deployment. Estimated: 1-2 days.

### Critical (breaks the product or creates legal exposure)

| # | Issue | Fix | Effort |
|---|-------|-----|--------|
| B-1 | **Tailwind CDN** — 300KB render-blocking JS, GDPR risk (IPs to US), contradicts privacy policy | `npm run build:css`, replace `<script>` with `<link>`, update CSP | 30 min |
| B-2 | **`YOUR_DOMAIN` placeholders** in nginx config | `sed` replace or envsubst in entrypoint | 10 min |
| B-3 | **`user_id` path param unvalidated** — path traversal risk | Add `^[a-zA-Z0-9_-]{1,64}$` validator | 15 min |
| B-4 | **`EventRequest.properties` unbounded** — memory exhaustion | Add max depth/size validator | 15 min |
| B-5 | **No Impressum** — legally required under German TMG section 5 | Add impressum page with name, address, contact | 30 min |
| B-6 | **No Terms of Service** — AI disclaimer needed | Create ToS with 11 sections (outline provided by legal agent) | 1 hour |

### High Priority (embarrassing but not blocking)

| # | Issue | Fix | Effort |
|---|-------|-----|--------|
| H-1 | 6 unprotected localStorage calls (crashes in Safari private mode) | Wrap in try/catch | 20 min |
| H-2 | 11 fetch calls without timeout (UI freezes if server hangs) | Add `fetchWithTimeout` helper | 30 min |
| H-3 | 2 missing double-click guards (startChallenge, startQuickMatch) | Add boolean guards | 10 min |
| H-4 | Skip-to-content link missing | Add sr-only link after `<body>` | 5 min |
| H-5 | No focus trap in modals | Add trapFocus/releaseFocus utility | 20 min |
| H-6 | `text-white/30` fails WCAG AA contrast | Change to `text-white/50` in 3 locations | 5 min |
| H-7 | Privacy policy gaps (6 items) | Update retention periods, add AI disclosure, UpCloud sub-processor | 1 hour |

---

## Phase 1: Soft Launch (Week 1-2)

**Goal:** Get 100 users. Measure completion rate, return rate, cost per session.

### Deployment
- **Target:** Single VPS, ~$10-15/month
- **Stack:** Docker (nginx + FastAPI), SSL via Let's Encrypt
- **Monitoring:** Health endpoint already built, add Plausible analytics ($9/month) or use built-in `analytics.js`

### Launch Channels (do these 3, in this order)
1. **Reddit r/careerguidance** — ready-to-post template provided. Engage 48+ hours in comments.
2. **Hacker News Show HN** — technical angle plays well. Post 8-9 AM ET.
3. **Email 5 negotiation coaches/career YouTubers** — one "yes" from a 50k+ creator changes everything.

### Landing Page Fixes (before posting)
- Replace hero CTA card with solid filled coral button ("Start Negotiating Free")
- Add trust strip: "100% free · Private · No signup required"
- Hide quick-action cards for first-time visitors (progressive disclosure)

### Week 1 Targets

| Metric | Target |
|--------|--------|
| Unique visitors | 500+ |
| First simulations started | 100+ |
| Completion rate | 60%+ |
| Return within 7 days | 20%+ |
| Product-market fit signal | Repeat rate > 20% |

---

## Phase 2: Validate & Retain (Week 3-6)

### Retention Fixes (highest leverage, implement in order)
1. **Streak forgiveness** — change `diffDays === 1` to `diffDays <= 2`. Prevents #1 dropout reason. (30 min)
2. **XP curve rebalancing** — add `Math.pow(score - 80, 1.5)` bonus for high performers. Increase streak bonus to `25 * Math.min(streak, 7)`. (1 hour)
3. **Wire share buttons** — session-export.js already generates 1200x630 PNGs. Add "Share to Twitter/LinkedIn". Every share = potential new user. (2 hours)
4. **Expand daily challenges** — move from hardcoded Python to YAML file. Add 30 more for 60-day rotation. (1 day)

### Content Addition: 6 Personal Finance Scenarios
Easiest to implement, most universal appeal:
- Gym Cancellation (difficulty 1)
- Insurance Claim (difficulty 2)
- Used Furniture (difficulty 1)
- Hotel Upgrade (difficulty 1)
- Cable/Internet Bill (difficulty 1)
- Home Contractor (difficulty 2)

~60-80 lines of Python each. 4 locations to update per scenario.

### Analytics
- Wire `analytics.js` (already built) into index.html — 1 script tag + 12 one-liner calls
- Track the 7-step funnel: page_view → scenario_configured → negotiation_started → message_sent → negotiation_completed → feedback_submitted → negotiation_repeated
- Alert thresholds: completion < 40%, error rate > 5%, feedback < 3.5/5

---

## Phase 3: Monetize (Week 7-12)

### Pricing Model

| | Free | Pro ($9/mo) | Expert ($29/mo) |
|---|---|---|---|
| Sessions/day | 3 | Unlimited | Unlimited |
| Scenarios | 3 | All | All |
| Debrief ("What They Were Thinking") | Locked | Full | Full |
| Playbook generator | Locked | PDF export | + custom scenarios |
| LLM opponent | — | Rule-based | LLM-powered |

**Lifetime deal: $49** (first 500 customers). Works because marginal cost is near-zero.

**Break-even: 2 paying users** at ~$16/month server costs.

**The conversion engine is the debrief.** Lock it behind Pro.

### Implementation (8-13 days)
1. Usage tracking + feature gating (3-5 days)
2. Magic link email auth — no passwords (2-3 days)
3. LemonSqueezy payment integration (2-3 days)
4. Pricing page + upgrade CTAs (1-2 days)

### Payment Processor: LemonSqueezy
- Handles EU VAT automatically (Merchant of Record)
- Supports subscriptions + one-time purchases
- 5% + $0.50/transaction (higher than Stripe, but tax handling saves more)
- Switch to Stripe at $10K+/month volume

---

## Phase 4: Scale (Month 3-6)

### Technical Scaling

| DAU | Infrastructure | Cost |
|-----|---------------|------|
| 0-100 | Single VPS, file persistence | ~$10/mo |
| 100-1K | + Redis for sessions/rate-limiting, 2-4 workers | ~$50/mo |
| 1K-10K | + PostgreSQL, CDN, load balancer | ~$200/mo |

### Content Expansion
- Cultural negotiation scenarios (unique differentiator — no competitor has these)
- Multi-round scenarios (2-4 linked sessions with evolving persona)
- Custom Scenario MVP (form-based, unlocks infinite user-generated content)
- YAML scenario template for non-developer creation

### B2B Play
- Manager dashboards for team performance tracking
- LMS/SCORM integration for enterprise L&D
- White-label option for training companies

### Performance Optimization
- Extract 102KB inline JS to deferred `app.js` (FID -50%)
- Bundle 15 JS files into 2-3 (saves 12+ round trips)
- Minify all JS/CSS (payload -25%)
- Target: LCP < 2.5s, FID < 100ms

---

## Competitive Position

**DealSim owns the upper-right quadrant: high-tech AND strategically deep.**

No current product combines:
- LLM-driven adaptive counterparties (when shipped)
- Multiple scenario types (not just sales)
- Real-time strategic coaching
- Post-session analytics with opponent state reveal

**Position against education ($5,000 Harvard workshops), not apps ($20/month).**

**4-layer moat:**
1. Scenario engine (6-12 months to replicate)
2. Strategic coaching model (12-18 months)
3. Performance data flywheel (compounds over time)
4. Brand as "the simulator" (narrative moat, unclaimed)

---

## What NOT to Do

From the devil's advocate:

1. **Don't build more features before launching.** The codebase has Series A complexity and weekend-project user count.
2. **Don't add API versioning yet.** No external consumers depend on stability.
3. **Don't add LLM integration to the free tier.** Rule-based engine is sufficient. LLM goes into Expert tier only.
4. **Don't add accounts before you have paying users waiting.** Auth is friction. Free tier stays account-free.
5. **Don't add more themes.** Three themes = triple the visual QA for zero revenue impact.
6. **Don't over-invest in infrastructure.** Current architecture handles 100 DAU without changes.

---

## Legal Checklist (Germany-Specific)

- [ ] Impressum (TMG §5) — name, address, contact, VAT ID
- [ ] Terms of Service with AI disclaimer
- [ ] Privacy policy update (retention periods, AI disclosure, UpCloud sub-processor)
- [ ] Bundle Tailwind locally (eliminates cross-border data transfer)
- [ ] Session data deletion endpoint (GDPR Art. 17)
- [ ] EU AI Act transparency notice ("You are negotiating with an AI")
- [ ] Kleinunternehmerregelung eligibility check (revenue < EUR 22,000)
- [ ] Gewerbeanmeldung if operating commercially

---

## Testing Before Launch

| Layer | Target |
|-------|--------|
| Backend pytest | 376 tests, all passing (already done) |
| Tailwind CSS rebuild | Verify `lg:` classes captured (Earnings Calculator) |
| Visual spot-check | All 3 themes × landing + chat + scorecard |
| Smoke test | Complete one full negotiation end-to-end |
| Mobile test | 375px viewport, touch targets, chat UX |

Post-launch: add Playwright E2E (6 critical flows), visual regression (27 screenshots), Lighthouse CI.

---

## The Decision Framework

**When someone suggests a new feature, ask:**
1. Does this help the next 100 users complete a negotiation? → Do it.
2. Does this help existing users return for a second session? → Do it after #1.
3. Does this help paying users get more value? → Do it after monetization ships.
4. Everything else → Capture to backlog, don't build.

---

*Generated from 20+ parallel agent analyses. 376/376 backend tests passing.*
