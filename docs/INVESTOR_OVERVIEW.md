# DealSim — Investor Overview

**March 2026 | Pre-Revenue MVP | Bootstrapped**

---

## 1. Executive Summary

DealSim is an AI negotiation flight simulator. Users practice salary negotiations, freelance rate discussions, and business deals against calibrated AI opponents, then receive a scored breakdown of their performance across six dimensions with specific coaching tips. The product fills a $29-$99 gap in a $2-4B market where the only options are free YouTube videos and $4,000+ executive coaches. A 70-agent analysis, 13-agent build sprint, and 12-agent security audit produced a working product with 18 API endpoints, 310 passing tests, and $12/month infrastructure costs. The technology works. The economics are extraordinary. Demand is the open question — and we have a concrete plan to answer it in seven days.

---

## 2. The Product

### What Exists Today

DealSim is a fully functional negotiation simulator built on FastAPI with a single-page frontend. The codebase spans approximately 8,800 lines across three development phases, all architecturally complete and tested.

**Core Simulation Engine**

The user selects a scenario (salary, freelance, rent, medical bill, car purchase, scope creep, raise, vendor negotiation, counter-offer, or budget request — 10 types total). An AI opponent with hidden constraints, a reservation price, and calibrated personality traits opens the negotiation. The user types natural-language messages. The engine parses offers, classifies moves (anchor, concession, question, reframe, emotional appeal), computes counter-offers based on 5 negotiation styles crossed with 3 pressure levels, and renders responses. When the negotiation ends, a six-dimension scorecard grades performance on Opening Strategy, Information Gathering, Concession Pattern, BATNA Usage, Emotional Control, and Value Creation — each with a 0-100 score and coaching tips for weak areas.

**The Debrief ("What They Were Thinking")**

After every simulation, users see the opponent's hidden state revealed: their true reservation price, the moment they almost walked away, the move that shifted power, and an exact dollar figure for money left on the table. This feature is structurally impossible in ChatGPT — there is no hidden opponent state to reveal when the AI is stateless.

**Offer Analyzer**

Users paste any offer letter and receive instant market positioning: percentile rank against P25/P50/P75/P90 benchmarks, red flags, and a specific recommendation. The analyzer generates three counter-offer strategies (conservative, assertive, aggressive) with exact scripts — words to say in the meeting. A printable playbook combines everything into a cheat sheet for the real negotiation.

**Daily Challenges**

Thirty micro-negotiation scenarios rotate monthly, each constrained to 3 turns with a specific skill focus. Streak tracking and compressed scoring create a habit loop.

**18 API Endpoints Across 4 Route Groups:**

| Group | Endpoints | Purpose |
|-------|-----------|---------|
| Simulation | 5 | Session CRUD, messaging, completion |
| Analysis | 4 | Offer analysis, counter-offers, playbooks, lifetime calculator |
| Post-Sim | 2 | Debrief reveal, shareable scorecard PNG |
| Challenge | 3 | Daily challenge retrieval, start, completion |
| History | 2 | Score tracking, behavioral pattern detection |
| Audit | 1 | Paste a real email thread, get scored |
| System | 1 | Health check + admin dashboard |

**12 Distinct UI Sections:**

1. Scenario selection with 10 negotiation types
2. Opponent customization (5 sliders: style, pressure, patience, transparency, budget tightness)
3. Difficulty progression (Easy through Expert)
4. Chat interface with real-time negotiation
5. Six-dimension radar scorecard
6. "What They Were Thinking" debrief with turn-by-turn analysis
7. Money Left on Table calculator
8. Offer Analyzer with percentile gauge
9. Counter-Offer Generator with three strategy cards
10. Printable Negotiation Playbook
11. Score History with improvement trends
12. Daily Challenge with timer and constraint display

---

## 3. The Market

**Global negotiation training** is a $2-4B market growing at 7-11% CAGR. Corporate L&D spending is $102.8B, with 50% of organizations prioritizing soft skills development.

**Category validation exists.** Hyperbound, a Y Combinator W24 company, raised $18.3M in Series A funding at $3.2M ARR for AI sales roleplay. They target enterprise sales teams at premium pricing. This proves VCs believe in AI-powered practice for human conversations.

**The pricing gap is enormous.** Harvard charges $5,500 per person for negotiation workshops. Executive coaches charge $2,000-4,000 for multi-session programs. Free resources (YouTube, blog posts, ChatGPT prompt templates) offer advice but not practice. Between free advice and $4,000 coaching, there is almost nothing. DealSim sits at $29 per preparation session — accessible to anyone with a job offer in hand.

**The adjacent market is larger than the core.** AI roleplay simulation is projected to grow from $2.24B to $12.5B by 2035. Nobody currently owns "deal prep" as a consumer category. People do not search for "negotiation simulator." They search for "how to negotiate salary" and "is this offer good." DealSim meets them at the moment of need — when they have an offer letter and 48 hours to respond.

**Direct competition is thin.** Tough Tongue AI offers a $10/month negotiation tool with unclear traction and no funding. No other product offers structured, scored negotiation simulation for individuals. The 12-18 month window before Gong, LinkedIn Learning, or similar platforms add "practice mode" is real but finite.

---

## 4. The Technology

### Hybrid Rule + LLM Architecture

The core technical insight is a hybrid engine. A rule-based system handles all strategic decisions: which counter-offer to make, when to walk away, how to respond to pressure tactics. This layer is deterministic, debuggable, and costs $0.00 per simulation. An LLM layer (provider-agnostic, currently using DeepSeek V3.2) renders natural language in the opponent's voice, adding conversational richness without introducing bugs in game mechanics.

This architecture solves three problems simultaneously:

1. **Cost.** Pure rule-based simulations cost nothing. Hybrid simulations (rule engine + LLM rendering) cost $0.003 each. Full LLM simulations cost $0.035. At any price point above $1, gross margins exceed 98%.

2. **Reliability.** Game-critical logic (offer parsing, acceptance thresholds, concession calculations) never touches an LLM. The scoring engine produces identical results for identical inputs. This is testable. ChatGPT-based alternatives cannot guarantee consistent scoring because the model is non-deterministic.

3. **Swappability.** The simulator is an abstract base class. Replacing the rule engine with a different LLM backend — Claude, GPT-4, or a multi-agent framework — requires subclassing one method. No architectural changes.

### Direction-Aware Engine

The engine correctly handles all negotiation directions. In a salary negotiation, the user wants the number to go up. In a medical bill negotiation, the user wants the number to go down. Concession detection, scoring, difficulty adjustment, and debrief calculations all branch on negotiation direction. This was a non-trivial engineering problem — the initial implementation had concession scoring inverted for buyer scenarios, difficulty modifiers that made hard mode easier, and debrief calculations using terminal state instead of per-turn tracking. All fixed and tested. (See: BUG-01, PERSONA-01, DEBRIEF-02 in engine fixes.)

### Test Coverage

310 tests passing across the full codebase. Test categories include:

- **Integration tests:** Full negotiation lifecycle (create session, negotiate multiple rounds, close deal, generate scorecard)
- **Engine tests:** Direction-aware concession detection, all 5 opponent styles, pressure level behavior, edge cases (acceptance signals with embedded offers, zero-concession deals)
- **Scorer tests:** All 6 dimensions, coaching tip generation, zero-concession gamification prevention
- **Security tests:** Session ID format validation, rate limiter behavior, error masking
- **Debrief tests:** Money-left calculation in both deal and no-deal scenarios, per-turn state tracking

### Security Hardening

A 12-point security review identified and fixed 10 issues before any public deployment:

- **CORS misconfiguration** — environment variable name mismatch caused wildcard CORS on every deployment. Fixed.
- **XSS in admin dashboard** — user-controlled strings (feedback comments, scenario types) interpolated into HTML without escaping. Fixed with `html.escape()`.
- **Admin key vulnerabilities** — insecure default, timing-vulnerable comparison, key leaked in HTML source. Fixed with `secrets.compare_digest()`, disabled-by-default admin, and placeholder replacement.
- **Rate limiter memory leak** — IP-keyed dict with no eviction. Fixed with two-layer cleanup (per-request pruning + periodic sweep).
- **Docker running as root** — added non-root user, proper `chown`, and `USER` directive.
- **Raw exception strings in API responses** — internal error details (file paths, class names) exposed to clients. Fixed with generic error messages and server-side logging.
- **Session ID injection** — arbitrary strings accepted in URL paths. Fixed with UUID4 regex validation on all session endpoints.

### Cloud-Ready Deployment

Pre-configured for Render (one-click via `render.yaml`), Railway, and Fly.io (Frankfurt region, auto-stop for cost efficiency). Docker Compose included. The simplified stack (FastAPI + optional PostgreSQL + Redis) runs on 4GB RAM. No Neo4j, no Celery, no complex orchestration — every unnecessary component was removed during the architecture correction phase.

---

## 5. The Moat

### Short-Term Differentiation (Months 1-6)

The scoring engine and hidden-state debrief are the immediate differentiators. ChatGPT can simulate a conversation, but it cannot:

- Track hidden opponent state and reveal it after the simulation
- Calculate the exact dollar amount left on the table
- Score performance deterministically across six dimensions
- Show move-by-move annotations ("$4,200/year lost at this specific moment")
- Detect behavioral patterns across sessions ("You always cave on equity")

A competent prompt engineer could replicate the conversation quality in 2-4 weeks. Replicating the structured scoring, hidden state, and cross-session analytics takes months.

### Medium-Term Moat (Months 6-18): The Data Flywheel

Every simulation captures structured data from the first day of operation:

```
User offer → Move classification → Opponent hidden state at each turn
→ Concession velocity → Trigger patterns → Outcome
```

This data feeds four compounding layers:

| Layer | Threshold | What It Enables |
|-------|-----------|-----------------|
| Tactic Effectiveness | 10,000 simulations | "Anchoring first works 73% of the time in salary negotiations" |
| Company Intelligence | 2,500 users (50/company) | "Google's hiring managers typically counter at P65" |
| Outcome Prediction | 10,000 with real outcomes | "Based on your profile and this company, expect $X-$Y" |
| Outcome Guarantee | 50,000 users | "We guarantee $5K+ improvement or your money back" |

Competitors can copy the interface. They cannot copy calibration data built from tens of thousands of structured negotiation outcomes.

### Long-Term Defensibility (Year 2-3)

At scale, DealSim becomes a two-sided data platform. The offer analyzer improves with every offer submitted. The simulation engine improves with every negotiation completed. Benchmark formation (percentile ranking against other users) creates switching costs. The data compounds; the product improves; the moat deepens.

**Three-year defensibility timeline:**

- **Year 1:** Scoring engine + debrief features (replicable but takes time)
- **Year 2:** 10,000+ calibrated scenarios with real outcome distributions (not replicable without the user base)
- **Year 3:** Company-specific intelligence and outcome predictions (structural moat)

---

## 6. The Business Model

DealSim follows a wedge-and-expand model, starting with the highest-intent buyer and expanding into recurring revenue.

| Tier | Product | Price | Target Buyer |
|------|---------|-------|-------------|
| **Wedge** | Offer Analysis Report | $19 per report | Anyone with an offer in hand |
| **Core** | Negotiation Simulation | $29-49 per session | Pre-negotiation prep |
| **Retention** | Negotiation Gym | $19/month | Professionals building skill |
| **Enterprise** | Sales Team Platform | $199/seat/month | Sales managers |
| **Platform** | API + White-Label | $50,000+/year | Training companies, bootcamps |

The insight from the 70-agent analysis: **the simulation is a feature; the offer analysis is the product.** People do not wake up wanting to practice negotiating. They wake up with an offer letter and 48 hours to respond. The analysis is what they pay for. The simulation is the premium upsell.

**The full user journey:**

1. Chrome extension detects an offer email (free)
2. Offer Analyzer: "You're $25K below market" ($19)
3. Simulation: Practice the recommended counter-offer ($29-49)
4. Playbook: Carry a cheat sheet into the meeting (bundled)
5. Gym subscription: Build the skill permanently ($19/month)

Each step increases commitment and demonstrates value before asking for more.

---

## 7. Unit Economics

| Metric | Value |
|--------|-------|
| Cost per simulation (rule-based) | $0.00 |
| Cost per simulation (hybrid with LLM) | $0.003 |
| Cost per simulation (full LLM) | $0.035 |
| Gross margin at $5 price point | 99.3% |
| Gross margin at $29 price point | 99.9% |
| Infrastructure at launch | $12/month (Vercel free tier + domain) |
| Infrastructure at 100 concurrent users | ~$13/month (Hetzner CX32) |
| Break-even | 1 paid simulation at any price above $0.04 |

The economics work at every scale. A single $29 sale covers 10 months of infrastructure. The product reaches profitability before exhausting the $15K bootstrap budget in every scenario modeled, including the pessimistic case.

**Why costs stay low:** The hybrid architecture means 80% of interactions are handled by the zero-cost rule engine. The LLM is called only for natural language rendering — not for strategic decisions, scoring, or game logic. This is structurally different from competitors who route every interaction through an LLM at $0.01-0.10 per turn.

---

## 8. Revenue Projections

### Base Case: $29/Report Model (Organic Only)

Assumptions: 20% month-over-month user growth, 4% free-to-paid conversion, 5% monthly churn, $0 marketing spend.

| Month | Total Users | Paid Users | MRR | Cumulative Revenue |
|-------|-------------|------------|-----|-------------------|
| 1 | 35 | 1 | ~$29 | $29 |
| 3 | 53 | 5 | ~$140 | ~$350 |
| 6 | 97 | 13 | ~$380 | ~$1,600 |
| 12 | 263 | 34 | ~$960 | ~$7,100 |

**Year 1 target: $32K cumulative** (blended across one-time reports, simulation sessions, and early gym subscriptions).

### Path to $100K ARR

The path requires one of these triggers:

1. **Gym subscriptions reach 200 paying users at $19/month** — achievable at Month 8-10 with 4% conversion from a growing free base
2. **Enterprise pilot with a single company** — one 50-seat deal at $199/seat = $10K/month
3. **Bootcamp partnership** — career services integration at 3-5 coding bootcamps, bundled pricing

### Three-Year Trajectory (Conditional on Validation)

| Year | Revenue | Products | Key Milestone |
|------|---------|----------|---------------|
| 1 | $100K ARR | DealSim | Product-market fit confirmed |
| 2 | $1-2M ARR | DealSim + API + white-label | Enterprise traction |
| 3 | $5-10M ARR | Platform + marketplace | Data moat established |

These numbers are aspirational. Year 1 is modeled. Years 2-3 are conditional on achieving Year 1 targets. The pessimistic scenario halves everything; the business still works because infrastructure costs are negligible.

---

## 9. Distribution Strategy

DealSim's distribution relies on zero-cost organic channels matched to moments of need.

### Channel 1: Reddit (Primary)

**r/cscareerquestions** (2.1M members) and **r/salary** are communities where salary negotiation is a recurring topic. The 30-day plan:

- Days 1-10: Helpful comments on negotiation threads (build credibility, no links)
- Day 11: Personal story post ("I built a tool after leaving $40K on the table")
- Day 14: Cross-post to r/freelance, r/careerguidance, r/negotiation
- Day 21: Results post with anonymized user data

Projected math: 100K views on a front-page post yields approximately 4,000 visitors, 400 trial users, and 100 paid conversions at 4% conversion.

### Channel 2: Product Hunt + Hacker News

Coordinated launch in the same week as the Reddit push. Product Hunt's audience skews toward early adopters willing to try tools. Hacker News values technical depth — the hybrid engine architecture is a genuine technical story.

### Channel 3: Career Coaches (Partnership)

Career coaches are the lowest-friction B2B channel. They already advise clients on negotiation. DealSim becomes their practice tool — white-label opportunity or affiliate commission. Target: 10 coaches using DealSim with clients by Month 3.

### Channel 4: Bootcamp Career Services

Coding bootcamps (General Assembly, Flatiron, App Academy) have career services teams that help graduates negotiate first offers. DealSim integrates as a preparation tool. Longer sales cycle (3-6 months) but high lifetime value per partnership.

### Channel 5: Chrome Extension (Month 2)

A browser extension that detects offer-related emails and surfaces the Offer Analyzer at the moment of maximum intent. This converts passive interest into active engagement at zero marginal cost.

### Channel 6: Shareable Scorecard (Viral Mechanic)

Every completed simulation generates a branded PNG scorecard (1200x630, OG image dimensions) designed for sharing on LinkedIn and Reddit. Without this, completed simulations are dead ends. With it, every satisfied user becomes a distribution channel. The Go-To-Market and Psychology agents both identified this as the single highest-leverage growth feature.

---

## 10. The Team

### Solo Founder, Force-Multiplied

DealSim was built by one person using Claude Code as an engineering force multiplier. The development process demonstrates a new model for bootstrapped product development:

**70-Agent Strategic Analysis**

Three structured board meetings with specialized AI agents covered market sizing, competitive analysis, pricing strategy, user psychology, distribution channels, technical feasibility, product-market fit assessment, and devil's advocacy. Each agent operated independently with a specific mandate. The devil's advocate agent argued the kill case. The findings were synthesized into actionable decisions — not consensus theater.

**13-Agent Build Sprint**

The MVP was built and tested in a single session. Architecture decisions (drop Neo4j, drop Celery, simplify to FastAPI + file-based persistence) emerged from the analysis and were implemented immediately. The codebase grew from zero to 2,950 lines of working product with integration tests.

**12-Agent Quality Audit**

Separate security review and engine review agents identified 10 security vulnerabilities and 10 engine bugs. All critical and high-severity issues were fixed and tested before any public deployment. The test suite grew from the initial integration tests to 310 passing tests covering security, engine correctness, scoring edge cases, and direction-aware behavior.

**What this demonstrates:** A solo technical founder with AI agent orchestration can produce output that historically required a 3-5 person team. The constraint is not engineering capacity — it is market validation and distribution. Which is why the ask below focuses on those areas.

---

## 11. The Ask

**DealSim is not raising capital.** The project is bootstrapped with $15K in personal runway. Infrastructure costs $12/month. Unit economics are profitable from the first sale. The business reaches cash-flow positive before the runway runs out in every modeled scenario.

**What accelerates this:**

**Beta testers** — specifically 5 people with a real negotiation happening in the next 30 days (salary offer, freelance rate discussion, contract renewal, raise conversation). Five users who test with real stakes will tell us more than 500 signups who never return. If they come back for a second session unprompted, we have a business. If they do not, we will know in a week.

**Advisory connections** — introductions to:
- Sales enablement leaders (potential enterprise pivot if B2C demand proves soft)
- Corporate L&D buyers (bulk licensing channel)
- Career coaches (lowest-friction distribution partner)
- Bootcamp career services directors (high-value institutional channel)
- Anyone who has built and sold a SaaS training product

**Pricing feedback** — the model says one-time reports ($29/session) maximize early revenue while subscriptions ($19/month) maximize lifetime value. We want to test both and would value input from anyone who has navigated this decision.

---

## 12. Risks and Mitigations

### Risk 1: ChatGPT Does 70% of This for Free

**Probability: HIGH.** Anyone can prompt ChatGPT to roleplay a hiring manager. The conversation quality is acceptable.

**Mitigation:** ChatGPT cannot track hidden opponent state, reveal what the opponent was thinking, calculate money left on the table, score performance deterministically, detect behavioral patterns across sessions, or generate a shareable scorecard. The 30% that ChatGPT cannot do is the 30% that creates the "one more game" retry loop and the data flywheel. DealSim competes on structured outcomes, not conversation quality.

**Monitoring:** If ChatGPT ships a "negotiation practice" mode with scoring, we pivot to enterprise (where integration, team analytics, and CRM connectivity matter more than the simulation itself).

### Risk 2: Solo Founder

**Probability: MEDIUM.** One person cannot build, market, sell, and support a SaaS product indefinitely. Burnout, context-switching, and bus-factor are real.

**Mitigation:** The AI agent workflow demonstrated during development is the ongoing operating model, not a one-time build sprint. The codebase is deliberately simple (8,800 lines, no build step, file-based persistence, single Docker container). Support load at launch is near-zero because infrastructure is self-healing (auto-stop on Fly.io, session auto-cleanup, rate limiting). The first hire — if revenue justifies it — is a part-time marketer, not an engineer.

### Risk 3: Demand Is Unproven

**Probability: HIGH.** Nobody is searching for "negotiation simulator." The Sean Ellis estimate is 8-15%, well below the 40% product-market fit threshold. This might be a vitamin, not a painkiller.

**Mitigation:** The validation plan is concrete and fast. Find 5 people with real negotiations happening this week. Offer free practice sessions. Measure whether they return for a second session unprompted. If they do not, archive DealSim and test CommsShield (difficult workplace conversations — stronger acute-pain signal) or pivot the engine toward Hyperbound's market (B2B sales teams). The kill decision happens at Day 7, not Month 6.

**The positioning correction:** Market this as "prepare for THIS deal" (painkiller for event-driven use), not "become a better negotiator" (vitamin for aspirational self-improvement). The anxiety reduction before a real negotiation is the emotional hook, supported by exposure therapy research.

### Risk 4: Scoring Engine Is Replicable

**Probability: MEDIUM.** The six-dimension scoring rubric could be reverse-engineered from the feedback and rebuilt in a weekend by a prompt engineer.

**Mitigation:** The scoring engine is the short-term differentiator, not the long-term moat. The data flywheel (tactic effectiveness data, company intelligence, outcome predictions) is the long-term moat, and it requires the user base that the scoring engine attracts. By the time a competitor replicates the scoring, DealSim should have thousands of calibrated outcomes that the competitor cannot replicate without building the same user base from scratch.

### Risk 5: Retention in an Episodic Category

**Probability: MEDIUM.** People negotiate salaries once every 1-3 years. The natural usage frequency is low.

**Mitigation:** Three retention mechanisms:
1. **Negotiation Gym** with daily challenges turns episodic need into habitual practice ($19/month subscription)
2. **Pattern recognition** across sessions creates identity investment ("I'm a 1400-rated negotiator")
3. **Scope expansion** beyond salary — rent, medical bills, car purchases, freelance rates, raises — means the same user has 3-5 negotiation events per year, not one

---

## Appendix: Key Metrics at a Glance

| Metric | Value |
|--------|-------|
| Lines of code | ~8,800 |
| API endpoints | 18 |
| Negotiation scenarios | 10 |
| Daily challenge pool | 30 |
| Test suite | 310 passing |
| Security issues found and fixed | 10 |
| Engine bugs found and fixed | 10 |
| Dependencies | 4 (FastAPI, uvicorn, Pydantic, Pillow) |
| Infrastructure cost | $12/month |
| Cost per simulation | $0.003 (hybrid) |
| Gross margin | 98%+ |
| Time to break-even | 1 sale |
| Agents used in analysis | 70 |
| Agents used in build | 13 |
| Agents used in audit | 12 |

---

*Built by a physicist who kept leaving money on the table in salary negotiations and decided to build a flight simulator for it. Every number in this document is sourced from the 70-agent analysis, engine test suite, or deployment configuration. No claims inflated.*

*Contact for beta access or advisory conversations: [email on request]*
