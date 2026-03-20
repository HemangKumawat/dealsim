# DealSim Analytics Implementation Plan

**Agent 6 Output — Analytics & Conversion Tracking Architect**

---

## 1. Tool Recommendation: Custom Events + Plausible (Hybrid)

**Decision: Start with custom `analytics.js` (already implemented), add Plausible later for public dashboard.**

| Tool | Verdict | Reason |
|------|---------|--------|
| **Custom events (chosen)** | Primary | Zero external deps, full control over schema, works offline, no GDPR consent needed |
| **Plausible** | Add at scale | $9/mo, privacy-first by design, provides public dashboard URL for stakeholders, easy to add later via `<script>` tag |
| **Umami** | Good alternative | Self-hosted option if cost matters, but requires server management |
| **PostHog** | Overkill for launch | Session replay and feature flags are premature; adds 50KB+ JS bundle |

**Migration path:** Custom events now → add Plausible script tag when traffic hits 100+ daily visitors → export custom event data to Plausible custom goals.

---

## 2. Privacy Architecture

**Zero-consent design — GDPR compliance by architecture, not by banner:**

- **No cookies.** Session ID is a random UUID in JS memory only — dies on tab close.
- **No PII.** Email from feedback form goes to the feedback endpoint, never to analytics.
- **No fingerprinting.** No user-agent, screen size, IP hashing, or canvas fingerprinting.
- **No cross-site tracking.** Referrer is reduced to hostname only.
- **Data minimization.** Message content is never logged — only round counts and scores.
- **Aggregation-first.** Server-side analytics DB stores events without linking to individuals.

This design means: no consent banner needed under GDPR Article 6(1)(f) — legitimate interest for aggregated, anonymous usage statistics.

---

## 3. Event Schema

### 3.1 Event Envelope

Every event follows this structure:

```json
{
  "event": "negotiation_completed",
  "props": { ... },
  "sid": "a1b2c3d4-...",
  "ts": "2026-03-20T14:32:00.000Z",
  "path": "/",
  "referrer": "reddit.com",
  "theme": "arena"
}
```

### 3.2 Complete Event Catalog

| Event | Props | Funnel Step |
|-------|-------|-------------|
| `page_view` | `{ landing: true }` | 0 |
| `section_viewed` | `{ section: "sec-demo" }` | — |
| `scenario_configured` | `{ scenario, difficulty, has_custom_context }` | 1 |
| `negotiation_started` | `{ scenario, difficulty }` | 2 |
| `message_sent` | `{ round }` | 3 (repeated) |
| `negotiation_completed` | `{ scenario, overall_score, outcome, round_count, duration_seconds, dim_scores }` | 4 |
| `score_viewed` | `{ overall_score }` | 5 |
| `feedback_submitted` | `{ rating, has_comment }` | 6 |
| `negotiation_repeated` | `{ same_scenario }` | 7 |
| `theme_switched` | `{ from, to }` | — |
| `achievement_unlocked` | `{ achievement }` | — |
| `level_up` | `{ from_level, to_level }` | — |
| `demo_started` | `{}` | — |
| `demo_completed` | `{ overall_score }` | — |
| `playbook_generated` | `{}` | — |
| `debrief_viewed` | `{}` | — |
| `offer_analyzer_used` | `{}` | — |
| `audit_used` | `{}` | — |
| `daily_challenge_started` | `{}` | — |
| `score_shared` | `{ method }` | — |
| `error_occurred` | `{ context, message }` | — |

### 3.3 Negotiation-Specific Metrics (in `negotiation_completed`)

```json
{
  "scenario": "salary_negotiation",
  "overall_score": 78,
  "outcome": "deal_reached",
  "round_count": 6,
  "duration_seconds": 342,
  "dim_scores": {
    "Opening Strategy": 85,
    "Anchoring": 72,
    "Concession Pattern": 68,
    "Relationship Building": 80,
    "BATNA Leverage": 75,
    "Closing Technique": 70
  }
}
```

---

## 4. Funnel Definition

```
visitor (page_view)
    │
    ├──► scenario_configured     ← "How many configure vs just browse?"
    │         │
    │         └──► negotiation_started    ← "API call succeeded, session created"
    │                   │
    │                   └──► message_sent (x N)    ← "Engagement depth"
    │                           │
    │                           └──► negotiation_completed    ← "Finished vs abandoned"
    │                                       │
    │                                       ├──► feedback_submitted    ← "Satisfaction signal"
    │                                       │
    │                                       └──► negotiation_repeated    ← "Retention signal"
    │
    └──► demo_started → demo_completed    ← "Demo conversion path"
```

**Key conversion rates to compute:**

| Metric | Formula |
|--------|---------|
| Configuration rate | `scenario_configured / page_view` |
| Start rate | `negotiation_started / scenario_configured` |
| Completion rate | `negotiation_completed / negotiation_started` |
| Feedback rate | `feedback_submitted / negotiation_completed` |
| Repeat rate | `negotiation_repeated / negotiation_completed` |
| Demo-to-full rate | `negotiation_started (after demo_completed in same session)` |

---

## 5. Dashboard KPIs for Launch Week

### Tier 1: Health Metrics (check daily)

| KPI | Target | Alert If |
|-----|--------|----------|
| Daily visitors | — | <10 (marketing not working) |
| Completion rate | >60% | <40% (UX friction or API errors) |
| Error rate | <2% | >5% (system issue) |
| Avg session duration | 3-8 min | <1 min (confusion) or >15 min (stuck) |

### Tier 2: Product Metrics (check daily, optimize weekly)

| KPI | Target | Signal |
|-----|--------|--------|
| Avg overall score | 55-70 | Too high = too easy, too low = frustrating |
| Avg rounds per negotiation | 4-8 | <3 = giving up early |
| Repeat rate | >20% | Product-market fit signal |
| Demo completion rate | >70% | Onboarding effectiveness |
| Feedback rating avg | >3.5/5 | Satisfaction |

### Tier 3: Growth Metrics (weekly review)

| KPI | Signal |
|-----|--------|
| Referrer distribution | Which channels drive traffic |
| Scenario popularity ranking | What to build more of |
| Theme preference distribution | Design investment decisions |
| Achievement unlock rates | Gamification engagement |
| Dimension score distributions | Where users struggle most (content opportunity) |

---

## 6. Integration Points in index.html

Add these calls to the existing functions (minimal changes — one line each):

```javascript
// In showSection():
DealSimAnalytics.sectionViewed(id);

// In the scenario form submit / startNegotiation():
DealSimAnalytics.scenarioConfigured({
  scenario: document.getElementById('scenario-type').value,
  difficulty: document.querySelector('.diff-btn.selected')?.textContent,
  customContext: document.getElementById('custom-context')?.value,
});

// After successful session creation:
DealSimAnalytics.negotiationStarted({
  scenario: state.scenario,
  difficulty: state.difficulty,
});

// In sendMessage(), after successful response:
DealSimAnalytics.messageSent(state.round);

// In renderScorecard():
DealSimAnalytics.negotiationCompleted({
  scenario: state.scenario,
  overallScore: data.overall_score,
  outcome: data.outcome,
  dimensions: dims,
  roundCount: state.round,
});

// In submitFeedback():
DealSimAnalytics.feedbackSubmitted({
  rating: currentRating,
  hasComment: !!document.getElementById('feedback-comment').value.trim(),
});

// In tryAgain():
DealSimAnalytics.negotiationRepeated({ sameScenario: true });

// In startDemo():
DealSimAnalytics.demoStarted();

// In shareScore():
DealSimAnalytics.scoreShared('clipboard');

// In generatePlaybook():
DealSimAnalytics.playbookGenerated();

// In showDebrief():
DealSimAnalytics.debriefViewed();
```

### Script Tag (add to index.html `<head>`, after gamification.js):

```html
<script src="/analytics.js" defer></script>
```

---

## 7. Server-Side Endpoint Blueprint

```python
# Add to main.py — minimal append-only analytics endpoint

from datetime import datetime
import json
from pathlib import Path

ANALYTICS_LOG = Path("data/analytics.jsonl")

@app.post("/api/analytics")
async def receive_analytics(request: Request):
    """Append-only event log. No processing at ingest time."""
    try:
        body = await request.json()
        events = body.get("events", [])

        # Rate limit: max 50 events per batch
        events = events[:50]

        # Sanitize: strip any field not in allowlist
        ALLOWED_EVENTS = {
            'page_view', 'section_viewed', 'scenario_configured',
            'negotiation_started', 'message_sent', 'negotiation_completed',
            'score_viewed', 'feedback_submitted', 'negotiation_repeated',
            'theme_switched', 'achievement_unlocked', 'level_up',
            'demo_started', 'demo_completed', 'playbook_generated',
            'debrief_viewed', 'offer_analyzer_used', 'audit_used',
            'daily_challenge_started', 'score_shared', 'error_occurred',
        }

        with open(ANALYTICS_LOG, "a") as f:
            for event in events:
                if event.get("event") not in ALLOWED_EVENTS:
                    continue
                # Strip any unexpected top-level keys
                clean = {
                    "event": event["event"],
                    "props": event.get("props", {}),
                    "sid": str(event.get("sid", ""))[:64],
                    "ts": event.get("ts", datetime.utcnow().isoformat()),
                    "path": str(event.get("path", "/"))[:200],
                    "referrer": str(event.get("referrer", ""))[:200] if event.get("referrer") else None,
                    "theme": str(event.get("theme", ""))[:20],
                    "received_at": datetime.utcnow().isoformat(),
                }
                f.write(json.dumps(clean) + "\n")

        return {"status": "ok"}
    except Exception:
        return {"status": "ok"}  # Never fail — analytics is fire-and-forget
```

### Launch-Week Dashboard Query (Python script for JSONL):

```python
# scripts/analytics_dashboard.py
import json
from collections import Counter
from pathlib import Path

events = [json.loads(line) for line in Path("data/analytics.jsonl").read_text().splitlines()]

# Funnel
funnel = Counter(e["event"] for e in events)
print("=== FUNNEL ===")
for step in ['page_view', 'scenario_configured', 'negotiation_started',
             'negotiation_completed', 'feedback_submitted', 'negotiation_repeated']:
    print(f"  {step}: {funnel.get(step, 0)}")

# Avg score
scores = [e["props"]["overall_score"] for e in events if e["event"] == "negotiation_completed"]
if scores:
    print(f"\nAvg score: {sum(scores)/len(scores):.1f}")
    print(f"Completion rate: {len(scores)/max(funnel.get('negotiation_started',1),1)*100:.0f}%")

# Theme preference
themes = Counter(e["theme"] for e in events)
print(f"\nTheme usage: {dict(themes)}")

# Top scenarios
scenarios = Counter(e["props"].get("scenario") for e in events if e["event"] == "negotiation_started")
print(f"\nScenario popularity: {scenarios.most_common(5)}")
```

---

## 8. File Delivered

**`static/analytics.js`** — Drop-in analytics module.

Features:
- Batched event sending (5 events or 10s, whichever first)
- `sendBeacon` on page unload for reliable delivery
- Auto-wires to gamification events (achievements, level-ups)
- Auto-fires `page_view` on load
- All methods are no-throw (analytics never breaks the app)
- Zero external dependencies, ~3KB unminified

**Next steps for integration:**
1. Add `<script src="/analytics.js" defer></script>` to index.html
2. Add the one-liner `DealSimAnalytics.*` calls to existing functions (section 6 above)
3. Add the `/api/analytics` endpoint to the Python backend
4. Run for 48 hours, then check `data/analytics.jsonl` with the dashboard script
