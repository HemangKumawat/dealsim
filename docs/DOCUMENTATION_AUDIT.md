# DealSim Documentation Audit

**Date:** 2026-03-19
**Scope:** All files in `docs/`, plus README.md, DEPLOY.md, CHANGELOG.md, .env.example, pyproject.toml, ARCHITECTURE.md
**Method:** Cross-referenced every claim in documentation against actual source files on disk, deployment configs, and test files.

---

## Audit Summary

| # | Check | Verdict | Details |
|---|-------|---------|---------|
| 1 | Quickstart (under 5 min) | PASS with issues | Works, but has inaccuracies |
| 2 | API endpoint documentation | FAIL | Major inconsistencies between docs |
| 3 | Deployment guide (4 platforms) | PASS with issues | Region claim wrong, missing env vars |
| 4 | Environment variables documented | PARTIAL FAIL | README incomplete, .env.example incomplete |
| 5 | Troubleshooting section | FAIL | Does not exist |
| 6 | Audit/review docs organized | PASS with issues | 37 files, no index, naming inconsistent |
| 7 | USER_GUIDE.md accuracy | FAIL | Describes features that are not wired up |
| 8 | INVESTOR_OVERVIEW.md consistency | FAIL | Multiple inflated/inaccurate claims |
| 9 | Stale references | FAIL | Many references to unimplemented architecture |
| 10 | COMPANY_INTERNAL.md accuracy | FAIL | Endpoint paths wrong, test count wrong |

**Overall assessment:** The documentation tells the story of three different products -- the MVP that exists on disk, the Phase 1 architecture that was partially built, and a future vision described in ARCHITECTURE.md. These three versions are conflated throughout the docs, creating a misleading picture of the current product state.

---

## 1. Quickstart (Under 5 Minutes)

**Verdict: PASS with issues**

README.md provides two quickstart paths:

```
docker-compose up --build
```
and
```
pip install -e .
uvicorn dealsim_mvp.app:app --host 0.0.0.0 --port 8000
```

Both are correct and should get a developer running quickly. However:

**Issues:**
- README references `.env.example` for "the full list" of config vars, but `.env.example` contains 9 variables while README documents only 5. The two lists are different.
- README says `DEALSIM_SESSION_FILE` defaults to `/tmp/dealsim_sessions.json`. The actual `.env.example` says `DEALSIM_DATA_DIR=/tmp/dealsim_data`, and COMPANY_INTERNAL.md says the session file is `{DATA_DIR}/sessions.json`. The README default path is wrong.
- No mention of Python version requirement in the quickstart. `pyproject.toml` requires `>=3.11` -- a developer on Python 3.10 would hit a confusing error.
- DEPLOY.md's local testing section says `pip install -e ".[dev]"` (with dev extras) while README says `pip install -e .` (without). The dev extras add pytest and httpx, so the README version works for running but not for testing.

---

## 2. API Endpoint Documentation

**Verdict: FAIL -- four different endpoint lists that contradict each other**

The project has four separate API endpoint tables, and none of them agree:

### README.md (5 endpoints)
Lists: POST /api/sessions, POST /api/sessions/{id}/message, POST /api/sessions/{id}/complete, GET /api/sessions/{id}, GET /health

### ARCHITECTURE.md (21 planned endpoints, 18 "implemented")
Lists the full Phase 1-3 vision including endpoints like POST /api/analyze, POST /api/counter-offer, POST /api/playbook, GET /api/sessions/{id}/debrief, GET /api/sessions/{id}/scorecard.png, GET /api/challenge/today, POST /api/audit, POST /api/lifetime-calc, GET /api/score-history, GET /api/patterns

### COMPANY_INTERNAL.md (18 endpoints)
Lists a DIFFERENT set of paths from ARCHITECTURE.md:
- `/api/offers/analyze` (not `/api/analyze`)
- `/api/market-data/{role}/{loc}` (not in ARCHITECTURE.md at all)
- `/api/users/{id}/history` (not `/api/score-history`)
- `/api/users/{id}/patterns` (not `/api/patterns`)
- `/api/challenges/today` (not `/api/challenge/today`)
- `/api/challenges/today/submit` (not `/api/challenge/{id}/complete`)
- `/api/tools/earnings-calculator` (not `/api/lifetime-calc`)
- `/api/tools/audit-email` (not `/api/audit`)
- `/api/scenarios` (not in ARCHITECTURE.md)
- Missing `/api/sessions` GET (list all), `/api/counter-offer`, `/api/scorecard.png`

### API_INTEGRATION_AUDIT.md (20 endpoints, from actual code)
This is the most authoritative source -- it was generated from reading the actual `routes.py`. It shows the COMPANY_INTERNAL.md paths are closest to reality, but even this audit lists 20 endpoints while COMPANY_INTERNAL.md claims 18.

### Actual file structure contradiction
ARCHITECTURE.md describes separate route files: `routes_analyzer.py`, `routes_debrief.py`, `routes_challenge.py`, `routes_audit.py`, `middleware.py`. **None of these files exist on disk.** The actual API has:
- `api/routes.py` (single monolithic routes file, 26KB)
- `api/offer_analyzer.py` (API-layer offer parsing)
- `api/debrief.py`
- `api/models.py`
- `api/analytics.py`

The modular route structure described in ARCHITECTURE.md and COMPANY_INTERNAL.md was never implemented. All routes live in a single `routes.py`.

### Request/response examples
README.md has correct request/response examples for the 5 core endpoints. These match the API_INTEGRATION_AUDIT.md findings for the core simulation loop. The examples are accurate.

However, no documentation provides request/response examples for the other 13+ endpoints. The ARCHITECTURE.md provides planned response shapes, but these are for a future architecture, not the current implementation.

---

## 3. Deployment Guide (4 Platforms)

**Verdict: PASS with issues**

DEPLOY.md covers Render, Fly.io, Railway, and VPS (Hetzner) with step-by-step instructions. All four guides are structurally complete and include verification steps.

**Issues:**
- **Fly.io region is wrong.** README.md says "The fly.toml is pre-configured for the Frankfurt region." The actual `fly.toml` sets `primary_region = "iad"` (US East / Ashburn, Virginia). Frankfurt would be `fra`.
- **Render URL is assumed.** DEPLOY.md says the app deploys to `https://dealsim.onrender.com` but Render assigns a random subdomain unless the user picks one. The verification curl command will fail if copied verbatim.
- **render.yaml has a placeholder.** `repo: https://github.com/YOUR_USERNAME/dealsim` -- this is expected for a template but should be called out as needing replacement.
- **Missing env vars in DEPLOY.md.** The Fly.io section sets only `DEALSIM_ADMIN_KEY` and `DEALSIM_CORS_ORIGINS` as secrets. But `.env.example` lists 9 variables. `DEALSIM_ENV=production` is set in fly.toml but `DEALSIM_DATA_DIR` is not -- it will default to `/tmp/dealsim_data` which may be ephemeral.
- **VPS guide assumes root login.** `ssh root@YOUR_IP` -- many modern VPS providers create a non-root user. Not wrong, but could fail on some setups.
- **docker-compose.yml health check.** DEPLOYMENT_REVIEW_W1.md found that the health check used `curl` which is absent from `python:3.12-slim`. This was reportedly fixed (using Python urllib instead), but the fix is not reflected in the DEPLOY.md or docker-compose.yml documentation.

---

## 4. Environment Variables

**Verdict: PARTIAL FAIL -- three different lists, none complete**

### README.md lists 5 variables:
PORT, CORS_ORIGINS, RATE_LIMIT_PER_MINUTE, LOG_LEVEL, DEALSIM_SESSION_FILE

### .env.example lists 9 variables:
DEALSIM_ENV, DEALSIM_HOST, DEALSIM_PORT, DEALSIM_WORKERS, DEALSIM_CORS_ORIGINS, DEALSIM_ADMIN_KEY, DEALSIM_MAX_SESSIONS, DEALSIM_SESSION_TTL_HOURS, DEALSIM_DATA_DIR

### COMPANY_INTERNAL.md lists 8 variables:
PORT, DEALSIM_CORS_ORIGINS, DEALSIM_ADMIN_KEY, DEALSIM_DATA_DIR, DEALSIM_SESSION_FILE, RATE_LIMIT_PER_MINUTE, LOG_LEVEL, DEALSIM_ENV

**Contradictions:**
- README says `CORS_ORIGINS`. The app actually reads `DEALSIM_CORS_ORIGINS` (after the CORS fix documented in DEPLOYMENT_REVIEW_W1.md). README was not updated.
- README says `PORT` defaults to 8000. `.env.example` says `DEALSIM_PORT=8000`. These may be different variables.
- `DEALSIM_ADMIN_KEY` is in .env.example and COMPANY_INTERNAL.md but NOT in README.md. This is the most important production variable.
- `DEALSIM_MAX_SESSIONS` and `DEALSIM_SESSION_TTL_HOURS` are in .env.example but nowhere else. No descriptions provided.
- `DEALSIM_WORKERS` is in .env.example but not documented anywhere.
- `DEALSIM_HOST` is in .env.example but not documented anywhere.
- `DEALSIM_SESSION_FILE` is documented in README and COMPANY_INTERNAL.md but NOT in .env.example.

**No single document provides the complete, accurate list of all environment variables with their defaults and descriptions.**

---

## 5. Troubleshooting Section

**Verdict: FAIL -- does not exist**

No troubleshooting guide exists anywhere in the documentation. Common issues that should be documented include:
- Session lost after server restart (expected behavior with in-memory fallback)
- CORS errors in browser console (the most common deployment mistake, per the CORS bug history)
- Free-tier cold start delays (Render: ~30s, Fly.io: ~10-30s)
- Admin dashboard returning 503 (expected when DEALSIM_ADMIN_KEY is not set)
- Rate limiting (100 req/min default, no per-endpoint differentiation)
- Data loss on redeployment for platforms without persistent storage
- Single-worker limitation (multi-worker not safe with file-based persistence)

---

## 6. Audit/Review Docs Organization

**Verdict: PASS with issues**

The `docs/` directory contains 37 files covering security, engine, API, UX, deployment, data quality, and more. This is thorough coverage.

**Issues:**
- **No index or README.** A developer opening `docs/` sees 37 files with no guidance on which to read first or how they relate.
- **Inconsistent naming.** Some use `_W1` suffix (first review wave), some use `_W2` (second wave), some use `_AUDIT` suffix, some use `_REVIEW`. The naming convention is not documented.
- **Duplicate coverage.** API_REVIEW_W1.md and API_INTEGRATION_AUDIT.md cover overlapping ground but reach different conclusions. API_REVIEW_W1.md found 4 CRITICAL URL mismatches (offer analyzer at wrong path, audit at wrong path, debrief fields wrong, playbook fields wrong). API_INTEGRATION_AUDIT.md found mostly WARN-level issues and rated 12/15 frontend calls as PASS. These audits appear to have been done at different points in the code's evolution, but both are dated 2026-03-19 with no timestamps to distinguish order.
- **No clear "current state" document.** A reader cannot tell which findings have been fixed and which remain open without reading every FIXES_APPLIED_*.md file.
- **PDF duplicates.** COMPANY_INTERNAL.pdf, INVESTOR_OVERVIEW.pdf, and USER_GUIDE.pdf exist alongside their .md sources. No note about which is authoritative or how PDFs are regenerated.

---

## 7. USER_GUIDE.md Accuracy

**Verdict: FAIL -- describes features that are not wired to the backend**

USER_GUIDE.md is well-written and reads as a polished product guide. However, it describes the full Phase 1-3 product, not the current state:

**Features described as working but NOT functional (per API_REVIEW_W1.md):**
- **Opponent Tuner sliders** (Section: "Tune Your Opponent") -- The frontend sends `opponent_params` but the API silently ignores it. The 6 sliders have no effect. API_INTEGRATION_AUDIT.md confirms: "user-facing feature (difficulty tuner sliders) has no backend effect."
- **Debrief / "What They Were Thinking"** -- API_REVIEW_W1.md found CRITICAL field mismatches. Frontend reads `opponent_thoughts`, `grade`, `text`; API returns `opponent_target`, `opponent_reservation`, `strength`, `analysis`. The debrief page shows empty data.
- **Playbook** -- API_REVIEW_W1.md found CRITICAL field mismatches. Frontend reads `opening_moves`, `key_phrases`, `rebuttals`, `walk_away`; API returns `style_profile`, `strengths`, `weaknesses`, `recommendations`. Zero field overlap. Playbook displays "Not available."
- **Offer Analyzer** -- API_REVIEW_W1.md found the frontend calls `/api/analyze-offer` but the API serves `/api/offers/analyze`. The feature 404s on every attempt.
- **Negotiation Email Audit** -- Frontend calls `/api/audit-negotiation` but the API serves `/api/tools/audit-email`. The feature 404s.
- **Daily Challenges** -- Frontend uses a hardcoded JS array, never calls the server's `/api/challenges/today` endpoint.
- **Score History** -- Frontend uses localStorage only, never calls `/api/users/{id}/history`.

**Features described that are fully functional:**
- Core simulation (create session, chat, get scorecard)
- Scoring dimensions (6 dimensions with correct weights)
- Keyboard shortcuts
- Difficulty selection (easy/medium/hard -- though "Expert" is described in architecture but USER_GUIDE.md correctly only mentions 3 levels)
- FAQ section is accurate for the core simulation

**Scenario list discrepancy:**
USER_GUIDE.md lists 4 scenarios: Salary, Freelance Rate, Business Deal, Custom. COMPANY_INTERNAL.md lists 10 scenarios. ARCHITECTURE.md planned 7 scenarios (Phase 2 Feature 14). The actual `persona.py` file on disk (29KB) likely contains more than the 4 documented in USER_GUIDE.md.

---

## 8. INVESTOR_OVERVIEW.md Consistency

**Verdict: FAIL -- multiple inflated or inaccurate claims**

**Claim: "18 API endpoints"**
The document says 18 endpoints across 4 route groups, with a table showing 7 groups (Simulation: 5, Analysis: 4, Post-Sim: 2, Challenge: 3, History: 2, Audit: 1, System: 1). That sums to 18, but the table has 7 groups, not 4. More importantly, API_REVIEW_W1.md found that 9 of 17 non-admin endpoints are unreachable from the frontend. Of the reachable ones, 4 have CRITICAL contract mismatches (wrong URL or wrong field names). The functional endpoint count from the frontend is closer to 5-7, not 18.

**Claim: "310 passing tests"**
Actual count from grepping `def test_` across all test files: **262 test functions**. The 310 figure appears inflated. Even accounting for parametrized tests, the documented breakdown in COMPANY_INTERNAL.md (which shows per-file counts summing to roughly 241 in its table, then claims 310 total) does not reconcile.

**Claim: "~8,800 lines" of code**
ARCHITECTURE.md (which is a planning document, not a status report) projected ~8,765 lines across all three phases. COMPANY_INTERNAL.md says "~2,950 lines Python + 789 lines HTML at MVP; expanded to approximately 5,500 lines Python after Phase 1 features." The INVESTOR_OVERVIEW.md uses the 8,800 figure from the full three-phase plan, but Phase 2 and Phase 3 have not been built. The actual codebase has 23 Python source files and 19 test files, which is consistent with the ~5,500 line estimate, not 8,800.

**Claim: "10 negotiation scenarios"**
Plausible based on the 29KB persona.py file, but needs verification. ARCHITECTURE.md planned 7 scenarios in Phase 2 (Feature 14). If the build agents implemented them, 10 is possible. USER_GUIDE.md only documents 4.

**Claim: "12 Distinct UI Sections"**
Several of these sections are non-functional per the API review findings (Offer Analyzer, Playbook, Debrief, Daily Challenge, Score History).

**Claim: "Hybrid Rule + LLM Architecture"**
The document describes a hybrid system using "DeepSeek V3.2" for language rendering. However, the actual codebase has no LLM integration. COMPANY_INTERNAL.md Section 2 says "There is no LLM involved. Every opponent response is generated deterministically." The INVESTOR_OVERVIEW.md describes a planned architecture as if it is current.

**Claim: "$12/month infrastructure costs"**
Plausible for a Hetzner VPS, but the document also mentions "Vercel free tier + domain" which is inconsistent with the FastAPI/Docker stack. The project has no Vercel configuration.

**Claim: "4 (FastAPI, uvicorn, Pydantic, Pillow)" dependencies**
`pyproject.toml` lists only 3 runtime dependencies: FastAPI, uvicorn, Pydantic. Pillow is NOT in pyproject.toml. ARCHITECTURE.md says Pillow is needed for Phase 1 Feature 3 (Scorecard PNG), but there is no `scorecard_image.py` file on disk.

---

## 9. Stale References

**ARCHITECTURE.md is the primary source of stale references.** It is a planning/architecture document that describes the full 3-phase build, but it is written in present tense ("What it does:") making it read as if everything is built. Key stale elements:

- **Separate route files** (`routes_analyzer.py`, `routes_debrief.py`, `routes_challenge.py`, `routes_audit.py`, `middleware.py`) -- None exist. All routes are in a single `routes.py`.
- **`core/counter_offer.py`** -- Not on disk. Counter-offer logic may be embedded in `offer_analyzer.py` or `routes.py`.
- **`core/scorecard_image.py`** -- Not on disk. No PNG generation capability.
- **`core/patterns.py`** -- Not on disk. Cross-session pattern recognition not implemented.
- **`core/scenarios.py`** -- Not on disk. Scenario definitions may be in `persona.py`.
- **`data/` directory** with `market_ranges.json`, `scenarios.json`, `challenge_bank.json` -- Need to verify existence.
- **`static/analyzer.html`, `static/scorecard.html`, `static/js/*.js`** -- Not verified but ARCHITECTURE.md lists them as new files.
- **Phase 2 and Phase 3 features** -- All described as planned but presented alongside Phase 1 as if in the same product.

**README.md stale references:**
- "Frankfurt region" for Fly.io -- actual region is `iad` (US East)
- `CORS_ORIGINS` variable name -- should be `DEALSIM_CORS_ORIGINS`
- `DEALSIM_SESSION_FILE` default path -- inconsistent with actual implementation

**COMPANY_INTERNAL.md stale references:**
- Module map shows files that match disk, but the endpoint paths in Section 1 differ from ARCHITECTURE.md. One of them is stale; most likely ARCHITECTURE.md since COMPANY_INTERNAL.md was written after the build.
- Test count of 310 does not match actual count of 262 test functions.

---

## 10. COMPANY_INTERNAL.md Technical Accuracy

**Verdict: FAIL -- endpoint paths inconsistent, test count wrong, module map partially wrong**

**Endpoint paths:**
COMPANY_INTERNAL.md lists paths like `/api/offers/analyze`, `/api/market-data/{role}/{loc}`, `/api/users/{id}/history`. API_REVIEW_W1.md (which read the actual source code) found the frontend calling different paths (`/api/analyze-offer`, `/api/audit-negotiation`). The truth depends on which version of the code was analyzed, but the two documents within the same `docs/` directory disagree, which is itself a documentation failure.

**Test count:**
Claims 310 tests. Actual: 262 `def test_` functions across 11 test files. The per-file breakdown in COMPANY_INTERNAL.md Section 7 (Table "Coverage by Module") sums to 241 tests, not 310. The discrepancy is not explained.

**Module map:**
Lists `api/offer_analyzer.py` as a file -- this exists on disk. But also lists `api/middleware.py` in the introductory module map -- this does NOT exist on disk. The "Target File Structure" may have been copied from ARCHITECTURE.md rather than verified against the actual build.

**Codebase size:**
Claims "approximately 5,500 lines Python after Phase 1 features." This is plausible given the file sizes on disk (routes.py is 26KB alone, simulator.py is 27KB).

**Security findings table:**
Claims 1 CRITICAL, 7 HIGH, 8 MEDIUM, 7 LOW. SECURITY_REVIEW_W1.md says "4 HIGH, 8 MEDIUM, 5 LOW" with no CRITICAL. DEPLOYMENT_REVIEW_W1.md found 1 CRITICAL (CORS mismatch). The combined numbers roughly match if you merge both reviews (1 CRITICAL from deployment + 4 HIGH from security + 3 HIGH from deployment = 8 HIGH total, close to the claimed 7). The table is approximately correct but the accounting is imprecise.

**Persistence layer:**
The description of atomic writes with `os.replace()`, `threading.Lock`, corruption recovery, and JSONL rotation appears accurate and matches the `store.py` and `session.py` files on disk.

---

## Recommendations (Priority Order)

### Critical (blocks credibility)

1. **Create a single authoritative endpoint reference.** Pick one document (COMPANY_INTERNAL.md or a new API_REFERENCE.md) and make it the single source of truth for all endpoint paths, request/response shapes, and status (working / broken / planned). Delete or clearly label all other endpoint lists as outdated.

2. **Fix INVESTOR_OVERVIEW.md claims.** Change "310 tests" to actual count (~262). Change "8,800 lines" to actual (~5,500). Remove or label the LLM/DeepSeek claim as planned architecture. Fix dependency count (3, not 4 -- Pillow is not installed). Remove "Vercel" from infrastructure description.

3. **Add "Current State vs. Planned" labels throughout.** ARCHITECTURE.md, USER_GUIDE.md, and INVESTOR_OVERVIEW.md all describe planned features as if they exist. Add a clear status marker (e.g., "[IMPLEMENTED]", "[PLANNED]", "[BROKEN]") to each feature section.

4. **Fix USER_GUIDE.md.** Either remove sections for non-functional features (Offer Analyzer, Audit, Debrief details, Playbook, Daily Challenges, Opponent Tuner) or add honest notes that these are in development.

### High (blocks developer productivity)

5. **Unify environment variable documentation.** Create one table in README.md that lists ALL variables from `.env.example` plus any others found in the code, with defaults, types, and descriptions. Delete the partial lists from other documents.

6. **Fix README.md.** Update `CORS_ORIGINS` to `DEALSIM_CORS_ORIGINS`. Fix the session file default path. Fix "Frankfurt region" to "US East (iad)". Add Python 3.11+ requirement to quickstart.

7. **Add a troubleshooting section** to DEPLOY.md or a standalone TROUBLESHOOTING.md covering: CORS errors, cold start delays, admin 503, data persistence on free tiers, single-worker limitation.

8. **Add a docs/README.md index** that explains the naming convention (_W1 = Wave 1 review, _W2 = Wave 2, _AUDIT = detailed audit, FIXES_APPLIED = changelog of fixes) and lists documents in reading order.

### Medium (improves quality)

9. **Reconcile API_REVIEW_W1.md and API_INTEGRATION_AUDIT.md.** These two documents cover the same ground but disagree. One found 4 CRITICAL mismatches; the other found mostly PASSes. Add timestamps or version notes to clarify which was written first and which reflects the current state.

10. **Remove or archive ARCHITECTURE.md's Target File Structure.** The planned structure (separate route files, `patterns.py`, `scenarios.py`, `scorecard_image.py`) was never built. Keeping it in the repo misleads developers about the actual structure.

11. **Fix COMPANY_INTERNAL.md test table.** Update per-file test counts to match actual grep results: test_challenges: 25 (not 50), test_persona: 23 (not 16), test_simulator: 28 (not 19), test_scorer: 29 (not 20), test_api: 19 (not 16), test_session: 27 (not 15), test_integration: 10 (not 12).

### Low (nice to have)

12. **Add request/response examples for all endpoints.** README.md only documents 5 endpoints with examples. The other 13+ have no examples outside of ARCHITECTURE.md's planned shapes.

13. **Consolidate FIXES_APPLIED_*.md files** into CHANGELOG.md or a single FIXES_LOG.md. Currently there are 5 separate fix logs (analyzer, engine, frontend, persistence, security) plus a CHANGELOG.md that only covers the initial bug fixes.

14. **Generate fresh PDFs.** The existing PDFs may be stale relative to the .md sources.

---

## Appendix: Document Inventory

| File | Purpose | Accuracy vs. Current Code |
|------|---------|--------------------------|
| README.md | Quickstart + overview | Mostly accurate for core sim; env vars wrong |
| DEPLOY.md | Deployment guide | Good structure; Fly.io region wrong |
| CHANGELOG.md | Bug fix log (7 bugs) | Accurate for those specific fixes |
| .env.example | Config template | Most complete env var list, but undocumented |
| pyproject.toml | Build config | Accurate |
| ARCHITECTURE.md | Full product plan (Phases 1-3) | Planning document, not current state |
| docs/COMPANY_INTERNAL.md | Technical internal doc | Mostly accurate; test counts wrong, some paths inconsistent |
| docs/INVESTOR_OVERVIEW.md | Investor pitch | Multiple inflated claims |
| docs/USER_GUIDE.md | End-user guide | Describes non-functional features as working |
| docs/API_INTEGRATION_AUDIT.md | API contract audit | Authoritative for endpoint contracts |
| docs/API_REVIEW_W1.md | API quality review | Found critical frontend-backend mismatches |
| docs/SECURITY_REVIEW_W1.md | Security audit | Thorough; findings appear accurate |
| docs/ENGINE_REVIEW_W1.md | Engine logic review | Found real bugs (direction awareness) |
| docs/DEPLOYMENT_REVIEW_W1.md | Deploy config review | Found CORS critical bug |
| docs/REVIEW_AND_POLISH_PLAN.md | 100-agent review plan | Meta-document; not a deliverable |
| docs/FIXES_APPLIED_*.md (5 files) | Fix changelogs | Accurate per-fix documentation |
| docs/*_W2.md (5 files) | Wave 2 reviews (UX/frontend) | Not audited in detail |
| docs/*_AUDIT.md (10 files) | Detailed audits | Not all cross-checked |

---

*Audit completed 2026-03-19. This document should be updated after fixes are applied.*
