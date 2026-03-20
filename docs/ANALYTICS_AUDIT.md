# Analytics Pipeline Audit

**Date:** 2026-03-19
**Scope:** `analytics.py`, `feedback.py`, `core/analytics.py`, `app.py` (admin dashboard), `api/routes.py` (event endpoints)

---

## 1. Data Model: Events Tracked

Nine event types are defined in `VALID_EVENTS`:

| Event | Emitted From | Properties |
|---|---|---|
| `session_created` | `api_create_session` | session_id, scenario_type, difficulty, user_id |
| `message_sent` | `api_send_message` | session_id, round_number |
| `simulation_completed` | `api_complete_session` | session_id, overall_score, outcome |
| `debrief_viewed` | `api_get_debrief` | session_id |
| `playbook_generated` | `api_get_playbook` | session_id |
| `offer_analyzed` | `api_analyze_offer` | has_role, has_location |
| `challenge_completed` | `api_submit_challenge` | user_id |
| `feedback_submitted` | `api_submit_feedback` | session_id, rating, has_comment |
| `feature_used` | multiple (via `_feature()`) | feature_name, plus extras |

**Consistency issues:**

- The `VALID_EVENTS` whitelist in `analytics.py` and the `allowed` set in the `/events` POST endpoint diverge. The endpoint allows `page_view`, `score_viewed`, `email_audited`, and `earnings_calculated`, none of which are in `VALID_EVENTS`. The `track()` method does not enforce the whitelist -- it accepts any string. So `VALID_EVENTS` is documentary only, not enforced. This should be fixed: either enforce at write time or remove the dead constant.
- Events from the `/events` client-side POST endpoint bypass `VALID_EVENTS` entirely (they use a local `allowed` set). Two sources of truth for valid event types is a bug waiting to happen.
- The `earnings_calculated` and `email_audited` events are tracked via `_track()` in the tool endpoints but are not in `VALID_EVENTS`. Consistent, but the naming mismatch with `_feature("earnings_calculator")` / `_feature("email_auditor")` means a single user action writes two events with different feature names -- one from `_track` and one from `_feature`.
- Every endpoint calls both `_track()` and `_feature()`, producing two JSONL lines per request. This doubles storage for no analytical gain. The `_event_to_feature` mapping in `get_stats()` then re-derives feature usage from the core events anyway, so the explicit `_feature()` calls are redundant.

**Verdict:** Structurally sound schema (event + timestamp + properties). Undermined by duplicate writes and unenforced validation. Fix the dual-write pattern first.

---

## 2. Storage: JSONL Growth Rate

**Record size:** ~200-300 bytes per event line (JSON + properties).

**Growth model** (assuming 100 daily active users, ~15 events each):

| Timeframe | Events | File Size |
|---|---|---|
| 1 day | ~3,000 (1,500 real, doubled by _feature) | ~750 KB |
| 1 month | ~90,000 | ~22 MB |
| 6 months | ~540,000 | ~135 MB |
| 1 year | ~1,080,000 | ~270 MB |

At current dual-write rates, the file hits 10 MB (rotation threshold) in roughly two weeks of active use. This is fine for early-stage traffic. At 1,000 DAU it becomes unmanageable within days.

**Feedback file** grows much slower -- one record per completed session with feedback, typically 200-400 bytes. Even at scale this file stays small.

---

## 3. Aggregation: `get_stats()` Implementation

`get_stats()` calls `_read_all()`, which opens the JSONL file, parses every line with `json.loads()`, and returns a list. Then `get_stats()` makes **five full passes** over that list (sessions filter, completions filter, messages filter, feature counting loop, scenario counting loop) plus two partial passes (scores, daily counts).

**Performance characteristics:**

- At 10K events: ~50ms. Acceptable for an admin dashboard.
- At 100K events (the documented comfort threshold): ~500ms. Noticeable.
- At 500K events: ~2-3 seconds. The admin page feels broken.
- No caching. Every page load reparses the entire file from disk.

**The `get_events()` method** is worse: it reads all events, optionally filters, then slices -- O(n) regardless of the requested limit.

**Feedback `get_summary()`** has the same pattern but on a much smaller file, so it is fine for now.

**Recommendations:**
- Add a TTL cache (30-60 seconds) on `get_stats()`. A `functools.lru_cache` with a time-based wrapper would eliminate repeated disk reads during admin browsing.
- After rotation, `_read_all` only reads the current file, so historical data silently vanishes from stats. This is likely unintentional -- stats should aggregate across rotated files or maintain a separate running-totals file.

---

## 4. Admin Dashboard

The HTML dashboard (`/admin/stats`) provides:
- Top-line KPIs: sessions, completions, completion rate, average score, total messages
- Feedback summary: total, average rating, comment count, email count
- Feature usage table (ranked)
- Scenario popularity table
- Recent feedback (10 most recent with stars, comment, timestamp)

**Strengths:**
- Clean dark UI, responsive grid layout.
- Protected by `DEALSIM_ADMIN_KEY` with `secrets.compare_digest` (timing-safe comparison).
- Both JSON and HTML endpoints exist, supporting both human and programmatic access.
- HTML-escapes all user-provided content.

**Weaknesses:**
- No time filtering. You see all-time stats or nothing. Cannot answer "how did last week compare to this week?"
- The daily_active_sessions array is computed in `get_stats()` but never rendered in the HTML dashboard. The data is available in the JSON endpoint only.
- No trend indicators (up/down arrows, percentage changes).
- Score distribution is computed but not displayed in the HTML dashboard.
- No export capability (CSV download for deeper analysis).
- Admin key is passed as a query parameter, which means it appears in server logs, browser history, and referrer headers. Should be a header (`X-Admin-Key`) or cookie instead.

**Verdict:** Useful for a quick health check. Not sufficient for week-over-week decision-making. The missing daily-sessions chart is the biggest gap -- the data is already computed.

---

## 5. Feedback Collection

The `FeedbackCollector.submit()` method accepts:
- `session_id` (required) -- links feedback to a negotiation
- `rating` (required, clamped 1-5)
- `comment` (optional, truncated to 1000 chars)
- `email` (optional, truncated to 200 chars)
- `score` and `scenario_type` (optional context)

**Well-designed aspects:**
- Input sanitization: rating clamped, strings truncated at reasonable lengths.
- Optional email -- respects the privacy-first philosophy.
- Session context (score, scenario) stored alongside rating enables correlation analysis (e.g., "do low-scoring users rate lower?").
- Pydantic validation in `FeedbackRequest` enforces `ge=1, le=5` before it reaches the collector.

**Issues:**
- No duplicate prevention. A user can submit feedback for the same session_id multiple times. This inflates averages and totals. Should deduplicate by session_id (keep latest or reject duplicates).
- No spam protection beyond the global rate limiter (100/min). A single IP could submit 100 fake feedback entries per minute.
- The email field is stored in plaintext in a JSONL file. If this file leaks, every user email is exposed. Consider hashing or encrypting emails at rest.
- `get_summary()` returns `feedback_with_email_count` but does not surface the emails themselves through the admin API, which is good. However, `get_all()` returns everything including emails, and it is exposed via `core/analytics.read_feedback()`.

---

## 6. Feature Usage Tracking

Feature usage is tracked via two mechanisms:

1. **Explicit `_feature()` calls** in route handlers emit `feature_used` events with a `feature_name` property.
2. **Implicit mapping** in `_event_to_feature()` derives feature names from core event types during aggregation.

The `ENDPOINT_FEATURE_MAP` dict maps URL paths to feature categories but is never referenced in any middleware or route handler. It appears to be dead code -- perhaps intended for a tracking middleware that was never implemented.

**Can you tell which features users engage with?** Yes, reasonably well. The `feature_usage` dict in stats output ranks features by count. The `feature_usage_order` list gives a ranked view. Combined with `scenario_popularity`, you can answer "what do users do?" at a feature level.

**What you cannot tell:**
- Feature depth: "user opened offer analyzer" is tracked, but not "user read all 5 counter-strategies" vs "user bounced after seeing the score."
- Feature sequences: no funnel analysis. You cannot reconstruct session_created -> message_sent (x5) -> simulation_completed -> debrief_viewed -> playbook_generated as a journey.
- Per-user feature adoption: no user_id on most feature_used events (only session_created and challenge_completed carry user_id).

---

## 7. File Rotation

Rotation is implemented identically in both `AnalyticsTracker` and `FeedbackCollector`:

- **Threshold:** 10 MB (`_MAX_FILE_BYTES`)
- **Mechanism:** Shift existing `.1` -> `.2` -> `.3`, then rename current file to `.1`. Keep at most 3 rotated copies.
- **Trigger:** Checked on every `_append()` call, under the write lock.

**What happens at scale:**

| File Size | Behavior |
|---|---|
| < 10 MB | Normal operation |
| 10 MB | Rotates to `.1`. Stats now only reflect new data. |
| 40 MB total (10 + 10 + 10 + 10) | Oldest `.3` is deleted. Data loss. |
| 100 MB sustained | Only most recent ~10 MB visible to `get_stats()`. 90% of history gone. |
| 1 GB sustained | Same -- only latest 10 MB visible. Rotation handles the disk usage, but analytics are blind to history. |

**Critical problem:** `_read_all()` only reads the current file, not rotated files. After rotation, `get_stats()` resets to zero for all historical data. The dashboard will show a sudden drop in all metrics, which looks like a catastrophic outage when it is actually just a file rotation.

**Recommendations:**
- At minimum, `_read_all()` should read across `.1`, `.2`, `.3` files too.
- Better: maintain a separate `stats_snapshot.json` that persists running totals across rotations. Update it atomically on each rotation.

---

## 8. Corruption Recovery

**Write path:** `json.dumps(record) + "\n"` is appended in a single `f.write()` call. On most OS/filesystem combinations, writes under 4KB to an append-mode file are atomic. A 200-300 byte event record is well under this threshold.

**Read path:** `_read_all()` wraps each `json.loads()` in a try/except `JSONDecodeError` and silently skips corrupt lines with `continue`. This is the right behavior -- one bad line does not poison the entire file.

**Failure scenarios:**

| Scenario | Outcome |
|---|---|
| Process crash mid-write | Partial JSON line on disk. Skipped on next read. At most one event lost. |
| Disk full | `_append` catches the exception, logs a warning, and returns. The event is lost but the app continues. |
| File deleted while running | Next `_append` recreates it (append mode creates if missing). Reads return empty. No crash. |
| Concurrent processes (multiple workers) | Thread lock protects in-process concurrency. Multiple Gunicorn workers with separate processes would interleave writes. JSONL format is tolerant (each line is independent), but lines could merge mid-byte. This is a real risk in production multi-worker deployments. |

**Missing:** No write-ahead log, no checksums, no fsync. Acceptable for analytics (losing one event is not business-critical), but the multi-worker interleaving risk should be documented or mitigated with `fcntl.flock` / file locking.

---

## 9. Migration Path

**Current state:** JSONL files, full-file reparse on read, no indexing.

**When to move to SQLite:**
- When events exceed 100K (the documented threshold) or `get_stats()` latency exceeds 500ms.
- When you need time-range queries ("last 7 days" stats).
- When you need cross-file joins (correlating feedback with events by session_id).
- SQLite handles concurrent reads well and single-writer workloads. It solves the multi-worker write problem via its own locking.
- Migration effort: low. The schema maps directly to two tables (`events`, `feedback`). The `_append` / `_read_all` interface stays the same.

**When to move to PostgreSQL:**
- When you need multi-server deployments (SQLite is single-node).
- When you want real-time dashboards with complex aggregations (window functions, materialized views).
- When analytics data feeds into other systems (marketing, billing, ML pipelines).
- When you need proper user-level analytics with foreign keys to a users table.
- Likely at 1M+ events or when DealSim moves to a multi-instance deployment.

**Recommended migration sequence:**
1. Now: fix the dual-write issue, add TTL cache on `get_stats()`, read across rotated files.
2. At 50K events: migrate to SQLite. Add indexes on `event`, `timestamp`, `properties->session_id`.
3. At product-market fit (paying customers, multiple servers): PostgreSQL with TimescaleDB extension for time-series analytics.

---

## 10. Missing Metrics

**High priority (directly affects product decisions):**

| Metric | Why It Matters | Implementation |
|---|---|---|
| Session duration | Tells you if users are engaged or confused. A 2-minute session is qualitatively different from a 20-minute one. | Store `started_at` on `session_created`, compute delta on `simulation_completed`. |
| Drop-off point | Where do users quit? After round 2? After seeing their score? Before completing? | Track `session_abandoned` when a session times out or the user navigates away. |
| Messages per session | Proxy for engagement depth. | Already trackable by counting `message_sent` per session_id, but not aggregated in `get_stats()`. |
| Retry rate | Do users start a second session after completing one? Indicates both engagement and frustration. | Count distinct session_created events per user_id within a time window. |
| Time between messages | Distinguishes fast back-and-forth from long deliberation pauses. | Add timestamp to each `message_sent` event (already present as the event timestamp). |

**Medium priority (useful for growth):**

| Metric | Why It Matters |
|---|---|
| Referrer / UTM source | Where do users come from? (Can be tracked via `page_view` properties.) |
| Return rate | Same user_id appearing in sessions on different days. |
| Feature discovery rate | How many sessions pass before a user tries the offer analyzer or playbook? |
| Debrief-to-playbook conversion | What percentage of users who view the debrief also generate a playbook? |
| Score improvement over time | Per-user trend. The `score_trend` field exists in user history but is not fed back into analytics. |

**Low priority (nice to have):**

| Metric | Why It Matters |
|---|---|
| API response times | Detect degradation before users complain. |
| Error rates by endpoint | Which features are flaky? |
| Browser/device breakdown | If tracked via page_view properties. |

---

## Summary of Findings

| Area | Rating | Key Issue |
|---|---|---|
| Data model | B | Consistent schema, but dual-write inflates storage and `VALID_EVENTS` is unenforced |
| Storage | B- | JSONL is fine for now; growth math works at current scale |
| Aggregation | C | Full reparse on every call, no caching, stats reset after rotation |
| Admin dashboard | B- | Useful KPIs but no time filtering, missing chart for daily sessions |
| Feedback | B+ | Well-sanitized, good schema, missing dedup and email encryption |
| Feature tracking | B | Feature counts work, but no depth/sequence/funnel analysis |
| Rotation | C- | Implemented but stats silently lose history after rotation |
| Recovery | B | Corrupt lines skipped gracefully, but multi-worker writes are unsafe |
| Migration readiness | B+ | Clean interfaces make SQLite swap straightforward |

**Top 3 actions, ordered by impact:**

1. **Fix the stats-after-rotation blindness.** Read across rotated files in `_read_all()`, or maintain a running-totals snapshot. This is the most dangerous current bug -- it will erase dashboard metrics silently.
2. **Eliminate dual writes.** Remove the `_feature()` calls from route handlers. The `_event_to_feature` mapping in `get_stats()` already derives feature usage from core events. This halves storage growth and simplifies the data model.
3. **Add a TTL cache on `get_stats()`.** A 30-second cache prevents redundant full-file reparses when an admin refreshes or multiple people view the dashboard.
