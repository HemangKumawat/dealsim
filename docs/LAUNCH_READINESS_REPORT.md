# DealSim Launch Readiness Report

**Reviewer:** CTO Final Review
**Date:** 2026-03-19
**Codebase:** ~9,400 lines Python backend, ~2,600 lines frontend (single HTML), ~2,700 lines tests
**Version:** 0.1.0

---

## 1. Ship or No Ship?

**SHIP — with conditions.**

DealSim is a well-structured MVP with solid engineering fundamentals. The core simulation engine works, the API is clean, the frontend is functional, and the test suite covers the critical paths. The codebase shows evidence of multiple review passes and bug fixes already applied.

The minimum bar for launch is met: a user can start a negotiation, chat with an AI opponent, get scored, view a debrief, and the product does not lose data under normal operation.

**Conditions for shipping:**
- Fix the 5 must-fix items below (estimated 2-4 hours of work)
- Set a real DEALSIM_ADMIN_KEY in production
- Replace `YOUR_DOMAIN` in nginx config before deploying

---

## 2. Top 5 Must-Fix Before Launch

### MF-1: Admin key in query parameter (HIGH)
The admin key is passed as `?key=` in the URL. This means it appears in browser history, server access logs, nginx logs, and any proxy logs. A single leaked URL exposes the entire admin dashboard.

**File:** `src/dealsim_mvp/app.py`, lines 163-164
**Fix:** Move admin auth to an `Authorization: Bearer <key>` header or `X-Admin-Key` header. Takes 15 minutes.

### MF-2: Session data lost on container restart with multiple workers (HIGH)
Sessions persist to a JSON file (good), but `--workers 1` is the only safe configuration. With >1 uvicorn worker, each process has its own in-memory `_SESSIONS` dict. Writes go through `threading.Lock` but that only protects within a single process. Two workers writing the same file will corrupt it.

**File:** `src/dealsim_mvp/core/session.py`, line 82; `Dockerfile`, line 28
**Fix:** This is safe at launch because `--workers 1` is set. Document this constraint prominently. Do NOT increase workers without switching to Redis or a database.

### MF-3: No Content-Security-Policy header (MEDIUM)
The frontend loads Tailwind CSS from `cdn.tailwindcss.com` and fonts from `fonts.googleapis.com`. There is no CSP header, so any injected script would execute freely. The nginx config adds several security headers but omits CSP.

**File:** `nginx/dealsim.conf`, line 56-61; `static/index.html`, line 7
**Fix:** Add a CSP header to nginx config:
```
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' fonts.googleapis.com; font-src fonts.gstatic.com;" always;
```

### MF-4: Rate limiter state not shared across restarts (MEDIUM)
The in-memory rate limiter (`_rate_store` in `app.py`) resets on every restart. An attacker can bypass rate limiting by timing requests around deploys. More critically, the rate limiter stores per-IP timestamps in an unbounded dict. A distributed attack from many IPs will grow memory without limit until the 60-second cleanup sweep runs.

**File:** `src/dealsim_mvp/app.py`, lines 42-70
**Fix:** The periodic cleanup (line 55-59) mitigates the memory issue. For launch this is acceptable since nginx also rate-limits. Add a hard cap: `if len(_rate_store) > 10000: _rate_store.clear()` as a safety valve.

### MF-5: `YOUR_DOMAIN` placeholder still in nginx config (CRITICAL for deploy)
The nginx config has `YOUR_DOMAIN` on lines 10, 35, 38, 39. Deploying without replacing these will result in a non-functional HTTPS setup.

**File:** `nginx/dealsim.conf`, lines 10, 35, 38, 39
**Fix:** Document this in the deploy checklist and/or use an environment variable substitution script.

---

## 3. Top 5 Nice-to-Have (Post-Launch, 1-2 Weeks)

### NH-1: Scenario type and difficulty input validation
`scenario_type` and `difficulty` accept any string. Invalid values silently fall back to defaults. This pollutes analytics and confuses the API contract. Add `Literal` type constraints to the Pydantic models.

### NH-2: Session expiry cleanup as background task
Sessions auto-clean on file load (1-hour TTL), but the in-memory dict grows until the next restart if no one reads the file. Add a periodic background task (e.g., every 5 minutes) to evict expired sessions from `_SESSIONS`.

### NH-3: Bundle Tailwind CSS locally
Loading Tailwind from CDN (`cdn.tailwindcss.com`) adds a third-party dependency to every page load. If the CDN goes down, the UI breaks completely. Build a static CSS bundle and serve it from `/static/`.

### NH-4: Structured JSON logging
The current logging format is plaintext (`%(asctime)s [%(levelname)s]...`). In production with Docker, structured JSON logs are much easier to search, filter, and alert on. Switch to `python-json-logger` or equivalent.

### NH-5: Add request ID tracking
No request ID is generated or propagated. When debugging production issues, correlating a user report to a specific request in logs is impossible. Add a middleware that generates a UUID per request and includes it in all log lines and error responses.

---

## 4. Security Posture

**Grade: B-**

**Strengths:**
- No SQL database = no SQL injection surface
- No authentication for users = no credential storage to breach
- Admin endpoint uses `secrets.compare_digest` (timing-attack safe)
- Frontend uses `textContent` for chat bubbles and `escapeHtml()` for all dynamic HTML rendering -- XSS is well-mitigated
- Admin dashboard HTML uses `html.escape()` on all dynamic values
- Session IDs are validated as UUID4 format before use
- nginx config includes HSTS, X-Frame-Options, X-Content-Type-Options, server_tokens off
- Rate limiting at both nginx and application layers
- Docker runs as non-root user
- File writes use atomic `os.replace()` pattern

**Weaknesses:**
- Admin key in URL query string (see MF-1)
- No CSP header (see MF-3)
- No authentication on user history endpoints -- anyone can query `/api/users/{user_id}/history` if they guess/know a user_id
- `user_id` field has no character validation -- could inject newlines into JSONL files
- `properties` dict in `/api/events` is unbounded -- an attacker could send megabytes of nested JSON per request
- CORS defaults to localhost only (safe), but misconfiguration with `*` disables credentials (correctly handled in code)
- No CSRF protection (acceptable for API-only with no cookies/sessions)

**Assessment:** Safe to expose to the internet behind nginx. The attack surface is small because there is no user authentication, no database, and no PII beyond optional emails in feedback. The main risk is DoS, which nginx rate limiting mitigates.

---

## 5. Data Safety

**Will user data survive...**

| Scenario | Survives? | Notes |
|---|---|---|
| Application crash | YES | Sessions persist to `.dealsim_sessions.json` on every state change using atomic writes (fsync + os.replace). Analytics/feedback append to JSONL files. |
| Container restart | YES | File store is mounted as a Docker volume (`dealsim-data`). Data survives restarts. |
| Bad deploy | MOSTLY | Volume data survives. Corrupt JSON file is detected and archived as `.corrupt.{timestamp}`. In-memory state is rebuilt from file on module load. |
| Server reboot | YES | Docker volumes persist across reboots. `restart: unless-stopped` auto-restarts containers. |
| Disk full | PARTIAL | File writes fail silently (caught exceptions, logged as warnings). Sessions continue in-memory but are not persisted. Analytics events are lost. |
| Multi-worker corruption | NO | See MF-2. Stick to `--workers 1`. |

**Data retention:**
- Sessions: auto-cleaned after 1 hour (configurable via `_MAX_AGE_SECONDS`)
- Analytics: JSONL files rotate at 10 MB, keep 3 rotated copies (~40 MB max)
- Feedback: Same rotation policy as analytics

**Backup strategy:** None built in. The production docker-compose does not include backup automation. Recommend adding a daily cron job to copy the data volume.

---

## 6. Performance Estimate

**Architecture:** Single uvicorn process, synchronous FastAPI endpoints, in-memory session store, file-based persistence.

**Bottleneck analysis:**
- The main bottleneck is the synchronous file write on every session state change (`_persist_all()` serializes ALL sessions to JSON on every message). With 100 concurrent sessions, this means writing a ~500KB JSON file on every user message.
- Analytics and feedback use append-only JSONL (fast).
- `get_stats()` reads the entire events.jsonl file on every admin dashboard load (O(n) with file size).

**Estimated capacity:**
- 20-50 concurrent active negotiation sessions comfortably
- 100+ concurrent sessions if you accept 50-100ms write latency per message
- 500+ requests/minute for read-only endpoints (scenarios, market data, health)
- The 256MB Fly.io VM is tight -- recommend at least 512MB for production

**Scaling path:** Replace `_persist_all()` with per-session file writes or Redis. This is a ~2 hour change given the clean interface (`_store_session` / `_load_session`).

---

## 7. Monitoring Plan

**What exists today:**
- Health check endpoint (`/health`) monitored by Docker healthcheck every 30 seconds
- Structured log output to stdout (captured by Docker json-file logging driver)
- Admin dashboard at `/admin/stats` with session counts, completion rates, feature usage, feedback

**What is missing:**
- No external uptime monitoring (UptimeRobot, Pingdom, or similar)
- No alerting on error rate spikes
- No disk space monitoring
- No memory usage tracking
- No request latency percentiles

**Recommended minimum monitoring setup for launch:**
1. Free UptimeRobot ping on `/health` endpoint (5-minute interval)
2. `docker stats` cron job every 5 minutes, alert if memory > 80%
3. Check admin dashboard daily for the first week
4. Set up log forwarding to a free tier service (Logtail, Better Stack) for searchability

---

## 8. First-Week Plan

| Day | Action |
|---|---|
| Day 0 (Launch) | Deploy to production. Verify health endpoint. Run one full negotiation end-to-end. Check admin dashboard loads. Share link with 3-5 trusted testers. |
| Day 1 | Check analytics for any crashes or 500 errors in logs. Monitor memory usage. Review first feedback submissions. |
| Day 2 | Check completion rate -- if below 30%, investigate UX friction. Review any feedback comments. |
| Day 3 | Apply any hot-fixes from Day 1-2 feedback. Check disk usage on data volume. |
| Day 4 | Bundle Tailwind CSS locally (NH-3) to remove CDN dependency. |
| Day 5 | Add structured JSON logging (NH-4) and request ID tracking (NH-5). |
| Day 6 | Review all analytics data: which scenarios are most popular? Where do users drop off? What features are unused? |
| Day 7 | Write Week 1 retrospective. Prioritize Week 2 roadmap based on real usage data. Set up automated daily backup of data volume. |

---

## 9. Kill Criteria

Pull the plug immediately if:

1. **Data corruption:** The session store file becomes corrupt AND the recovery mechanism (archive + restart) fails, causing all users to see errors.
2. **Security breach:** Evidence of unauthorized access to admin endpoints, data exfiltration, or injection attacks succeeding.
3. **Persistent 500 errors:** Error rate exceeds 10% of requests for more than 15 minutes after a deploy.
4. **Memory exhaustion:** Container OOM-killed repeatedly (>3 times in 1 hour) with no clear fix.
5. **Scoring bugs in production:** Users report scores that are clearly wrong (e.g., 0/100 for a good negotiation, or 100/100 for accepting the first offer) -- this destroys product credibility.

**Recovery procedure:**
- Roll back to previous Docker image (`docker compose pull` from a known-good tag)
- If data is corrupted: stop container, restore from backup, restart
- If memory leak: restart container (buys 1 hour of session TTL before data loss)

---

## 10. Overall Grade

### B+

**Justification:**

The product is well-engineered for an MVP. The codebase is clean, well-documented, and shows thoughtful architecture decisions (abstract simulator base class, atomic file writes, proper error handling, XSS prevention). The test suite at 2,700 lines covers the important paths. The deployment stack (Docker + nginx + Let's Encrypt) is production-appropriate.

What keeps it from an A:
- Single-process file persistence is a known scaling ceiling
- No external monitoring or alerting
- Admin key in URL is a security smell
- No backup automation
- The `_persist_all()` pattern (serialize all sessions on every write) will not scale past ~100 concurrent sessions

What makes it a solid B+:
- The architecture is clean enough that every weakness above can be fixed incrementally without rewriting
- The security posture is genuinely good for an MVP -- no SQL injection surface, proper HTML escaping, rate limiting at two layers, non-root Docker user
- The product actually works end-to-end: 10 scenario types, 6 scoring dimensions, debrief, playbook, offer analyzer, daily challenges, email audit, earnings calculator
- The admin dashboard provides real-time product metrics from day one
- File persistence with atomic writes is honest engineering -- better than a "we'll add a database later" TODO

**Bottom line:** This is a shippable MVP. Fix the 5 must-fix items (2-4 hours), deploy, and start getting real users. The scaling limitations are well-understood and the code is structured to address them when needed.
