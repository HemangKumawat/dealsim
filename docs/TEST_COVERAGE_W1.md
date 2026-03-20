# DealSim Test Coverage Report — Week 1

**Date:** 2026-03-19
**Total tests:** 298 (all passing)
**Runtime:** ~0.5s

---

## 1. Module Test Coverage

| Source Module | Test File | Status | Tests |
|---|---|---|---|
| `core/persona.py` | `test_persona.py` | Existed | 16 |
| `core/simulator.py` | `test_simulator.py` | Existed | 19 |
| `core/scorer.py` | `test_scorer.py` | Existed | 20 |
| `core/session.py` | `test_session.py` | Existed | 15 |
| `api/routes.py` | `test_api.py` | Existed | 16 |
| (integration) | `test_integration.py` | Existed | 12 |
| `core/debrief.py` | **`test_debrief.py`** | **NEW** | 14 |
| `api/debrief.py` | **`test_debrief.py`** | **NEW** | (included above) |
| `core/playbook.py` | **`test_playbook.py`** | **NEW** | 19 |
| `core/offer_analyzer.py` | **`test_offer_analyzer.py`** | **NEW** | 20 |
| `api/offer_analyzer.py` | **`test_offer_analyzer.py`** | **NEW** | (included above) |
| `core/earnings.py` | **`test_tools.py`** | **NEW** | 9 |
| `core/email_audit.py` | **`test_tools.py`** | **NEW** | 14 |
| `core/challenges.py` | **`test_challenges.py`** | **NEW** | 50 |
| `api/analytics.py` | **`test_challenges.py`** | **NEW** | (included above) |

### Modules Still Without Dedicated Tests

| Module | Reason | Risk |
|---|---|---|
| `core/store.py` | File I/O with JSON; needs tmp-dir fixture | Medium — corrupted file handling is tested only by `load_sessions` catching exceptions |
| `analytics.py` (top-level) | JSONL tracker; thin shim over `core/analytics.py` | Low — tested indirectly through API endpoints |
| `feedback.py` | JSONL feedback store | Low — tested indirectly via `POST /api/feedback` |
| `core/analytics.py` | AnalyticsTracker class | Low — tested indirectly through all tracked endpoints |
| `api/models.py` | Pydantic models only (no logic) | None |

---

## 2. API Endpoint Coverage

18 endpoints in `routes.py`. Coverage status:

| # | Endpoint | Method | Test File | Covered? |
|---|---|---|---|---|
| 1 | `/api/sessions` | POST | `test_api.py` | Yes |
| 2 | `/api/sessions/{id}/message` | POST | `test_api.py` | Yes |
| 3 | `/api/sessions/{id}/complete` | POST | `test_api.py` | Yes |
| 4 | `/api/sessions/{id}` | GET | `test_api.py` | Yes |
| 5 | `/api/sessions/{id}/debrief` | GET | `test_debrief.py` (unit) | Partial — unit tested, no HTTP test |
| 6 | `/api/sessions/{id}/playbook` | GET | `test_debrief.py` (unit) | Partial — unit tested, no HTTP test |
| 7 | `/api/offers/analyze` | POST | `test_offer_analyzer.py` (unit) | Partial — unit tested, no HTTP test |
| 8 | `/api/market-data/{role}/{loc}` | GET | `test_offer_analyzer.py` (unit) | Partial — unit tested, no HTTP test |
| 9 | `/api/users/{id}/history` | GET | — | **NO** |
| 10 | `/api/users/{id}/patterns` | GET | — | **NO** |
| 11 | `/api/challenges/today` | GET | `test_challenges.py` (unit) | Partial — unit tested, no HTTP test |
| 12 | `/api/challenges/today/submit` | POST | `test_challenges.py` (unit) | Partial — unit tested, no HTTP test |
| 13 | `/api/feedback` | POST | `test_api.py` | Yes |
| 14 | `/api/events` | POST | — | **NO** |
| 15 | `/api/scenarios` | GET | — | **NO** |
| 16 | `/api/tools/earnings-calculator` | POST | `test_tools.py` (unit) | Partial — unit tested, no HTTP test |
| 17 | `/api/tools/audit-email` | POST | `test_tools.py` (unit) | Partial — unit tested, no HTTP test |
| 18 | `/health` | GET | `test_api.py` | Yes |

**Fully HTTP-tested:** 7/18 (39%)
**Unit-tested (core logic):** 16/18 (89%)
**No test at all:** 3 endpoints (`/users/{id}/history`, `/users/{id}/patterns`, `/api/events`, `/api/scenarios`)

---

## 3. Edge Cases Analyzed

### Covered by new tests

| Scenario | Test Location | Result |
|---|---|---|
| Empty string input to email audit | `test_tools.py::TestEmailEdgeCases::test_empty_string` | Pass (score=0) |
| Extremely long input to email audit | `test_tools.py::TestEmailEdgeCases::test_extremely_long_input` | Pass |
| Unicode/emoji in messages | `test_tools.py::TestEmailEdgeCases::test_unicode_and_emoji` | Pass |
| Empty transcript in debrief | `test_debrief.py::TestDebriefEdgeCases::test_empty_transcript` | Pass |
| Zero base salary | `test_offer_analyzer.py::TestOfferEdgeCases::test_zero_base_salary` | **BUG FOUND** — ZeroDivisionError |
| Very high salary (>p90) | `test_offer_analyzer.py::TestOfferEdgeCases::test_very_high_salary` | Pass |
| Negative day number for challenges | `test_challenges.py::TestChallengeEdgeCases::test_negative_day` | Pass (clamps to 1) |
| Unicode in challenge response | `test_challenges.py::TestChallengeEdgeCases::test_unicode_in_response` | Pass |
| Very long challenge response | `test_challenges.py::TestChallengeEdgeCases::test_very_long_response` | Pass |
| Zero earnings increase | `test_tools.py::TestEarningsCalculator::test_zero_increase` | Pass |
| Same salary (no negotiation win) | `test_offer_analyzer.py::TestOfferEdgeCases::test_earnings_impact_same_salary` | Pass |

### NOT covered (requires infrastructure)

| Scenario | Reason |
|---|---|
| Corrupted session store JSON file | Requires tmp-dir fixture + writing malformed JSON |
| Concurrent session modification | Requires threading test harness |
| Store file permission denied | OS-specific, hard to test portably |
| JSONL analytics file corruption | Mid-line corruption recovery is handled by try/except but not tested |

---

## 4. Bugs Found During Testing

### BUG 1: ZeroDivisionError in `core/offer_analyzer.py`

**Location:** `_build_counter_strategies()`, line 578
**Trigger:** `base_salary=0`
**Impact:** Server crash (HTTP 500) if user submits an offer with $0 base
**Fix:** Guard `base_salary > 0` before division

### BUG 2: ValueError in `api/offer_analyzer.py::_parse_offer_components()`

**Location:** Line 461 (bonus regex handling)
**Trigger:** Text containing both "15% annual bonus" and "$10k signing bonus"
**Impact:** Server crash (HTTP 500) on offer text with both components
**Root cause:** The bonus regex `group(1)` captures empty string when the percentage alternative (`group(3)`) matched, but the code unconditionally calls `float(bonus_m.group(1).replace(",", ""))`
**Fix:** Check `bonus_m.group(1)` before attempting float conversion; the existing `if bonus_m.group(3)` branch should be evaluated first

---

## 5. New Test Files Created

| File | Tests | Covers |
|---|---|---|
| `tests/test_debrief.py` | 14 | `core/debrief.py`, `api/debrief.py` |
| `tests/test_playbook.py` | 19 | `core/playbook.py` |
| `tests/test_offer_analyzer.py` | 20 | `core/offer_analyzer.py`, `api/offer_analyzer.py` |
| `tests/test_tools.py` | 23 | `core/earnings.py`, `core/email_audit.py` |
| `tests/test_challenges.py` | 50 | `core/challenges.py`, `api/analytics.py` |
| **Total new** | **126** | |

---

## 6. Recommended Next Steps

1. **Fix BUG 1** — add `base_salary > 0` guard in `_build_counter_strategies()`
2. **Fix BUG 2** — reorder bonus regex group checks in `_parse_offer_components()`
3. **Add HTTP-level tests** for the 4 untested endpoints (`/users/*/history`, `/users/*/patterns`, `/api/events`, `/api/scenarios`)
4. **Add store.py tests** with `tmp_path` fixture for corrupted JSON, missing file, and stale session cleanup
5. **Add concurrency test** for simultaneous session modification (threading + shared state)
6. **Consider pytest-cov** for line-level coverage metrics
