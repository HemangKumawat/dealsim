# Code Quality Audit

**Simulated toolchain:** ruff, mypy, pylint
**Date:** 2026-03-19
**Scope:** `src/dealsim_mvp/` (22 files) + `tests/` (12 files)

---

## Summary

| Category | Critical | Warning | Info | Total |
|----------|----------|---------|------|-------|
| Style / PEP 8 | 0 | 4 | 3 | 7 |
| Type Safety | 2 | 6 | 2 | 10 |
| Complexity | 1 | 3 | 0 | 4 |
| Dead Code | 0 | 3 | 2 | 5 |
| Anti-Patterns | 2 | 4 | 0 | 6 |
| Naming | 0 | 1 | 2 | 3 |
| Comments / Docs | 0 | 2 | 3 | 5 |
| Imports | 1 | 3 | 1 | 5 |
| Constants / Magic Numbers | 0 | 5 | 3 | 8 |
| Testing | 0 | 4 | 2 | 6 |
| **Total** | **6** | **35** | **18** | **59** |

Overall the codebase is well-structured: consistent module docstrings, clean dataclass usage, and good test coverage. The issues below are what automated tooling would flag.

---

## 1. Style / PEP 8

### W-S01 Extra alignment whitespace in enum members
**File:** `src/dealsim_mvp/core/simulator.py`, lines 29-31
**Severity:** Info (ruff: E241)
```python
class TurnSpeaker(str, Enum):
    USER     = "user"
    OPPONENT = "opponent"
    SYSTEM   = "system"
```
**Fix:** Remove extra spaces. Use `USER = "user"` etc.

### W-S02 Extra alignment whitespace in dataclass fields
**File:** `src/dealsim_mvp/core/session.py`, lines 40-42
**Severity:** Info (ruff: E241)
Same pattern: `ACTIVE    = "active"`, `COMPLETED = "completed"`.
**Fix:** Single space around `=`.

### W-S03 Import not at top of file
**File:** `src/dealsim_mvp/core/session.py`, lines 140, 158
**Severity:** Warning (ruff: E402)
`_deserialize_session` contains late imports of `NegotiationStyle`, `PressureLevel`, `MoveType`, `TurnSpeaker` inside the function body.
**Fix:** These are from modules already imported at the top of the file. Move to top-level imports. The late import was likely added to avoid circular imports, but the same symbols are already imported transitively through `simulator` and `persona` at module scope.

### W-S04 Import not at top of file
**File:** `src/dealsim_mvp/app.py`, line 148
**Severity:** Warning (ruff: E402)
```python
from fastapi import Query as FastQuery
```
Imported inside `create_app()`. This is a function-scoped import in a factory function.
**Fix:** Move to top-level imports alongside other FastAPI imports on line 22.

### W-S05 Line length in HTML template string
**File:** `src/dealsim_mvp/app.py`, lines 205-266
**Severity:** Warning (ruff: E501)
The inline HTML template has lines exceeding 120 characters.
**Fix:** Move to a separate template file or use `textwrap.dedent`. If inline HTML is intentional for single-file deployment, add `# noqa: E501` or configure ruff to skip this block.

### W-S06 Trailing whitespace in alignment
**File:** `src/dealsim_mvp/core/simulator.py`, lines 133-136
**Severity:** Info (ruff: W291)
```python
offer   = persona.opening_offer
```
Extra spaces for visual alignment.
**Fix:** `offer = persona.opening_offer`.

### W-S07 Duplicate section comment
**File:** `src/dealsim_mvp/analytics.py`, lines 185 and 230
**Severity:** Info
Two identical `# -- Internal helpers -----` comment blocks.
**Fix:** Remove the duplicate on line 230, or rename it (e.g., `# -- File rotation --`).

---

## 2. Type Safety

### C-T01 `dict` used without type parameters in Pydantic models
**File:** `src/dealsim_mvp/api/routes.py`, lines 127, 137, 235-237, 289, 305
**Severity:** Critical (mypy: missing-type-parameters)
```python
dimensions: list[dict]       # line 127
transcript: list[dict]       # line 137
sessions: list[dict]         # line 235
challenge: dict              # line 289
properties: dict = Field(...)  # line 305
```
**Fix:** Use typed dicts or `dict[str, Any]` for explicit typing. Better: define nested Pydantic models (e.g., `DimensionItem` already exists in `api/models.py` -- use it in `CompleteResponse`).

### C-T02 Singleton pattern is not thread-safe
**File:** `src/dealsim_mvp/analytics.py`, lines 283-288; `src/dealsim_mvp/feedback.py`, lines 195-200
**Severity:** Critical (pylint: consider-using-lock)
```python
def get_tracker() -> AnalyticsTracker:
    global _tracker
    if _tracker is None:
        _tracker = AnalyticsTracker()
    return _tracker
```
Under concurrent requests (uvicorn workers), two threads could both see `None` and create two instances.
**Fix:** Use `threading.Lock()` around the singleton creation, or use `functools.lru_cache(maxsize=1)` on the factory function.

### W-T03 `Any` type used without necessity
**File:** `src/dealsim_mvp/core/offer_analyzer.py`, line 24
**Severity:** Warning (mypy)
```python
from typing import Any
```
`Any` is used for `other_components: dict[str, Any]` in `analyze_offer()`. This is acceptable but could be narrowed to `dict[str, str | int | float | bool]`.

### W-T04 Return type not annotated
**File:** `src/dealsim_mvp/app.py`, lines 102, 120, 138, 143, 163, 174
**Severity:** Warning (mypy: no-untyped-def)
Functions `rate_limit_middleware`, `health_check`, `serve_root`, `serve_root_fallback`, `admin_stats_json`, `admin_stats_html` lack return type annotations.
**Fix:** Add `-> Response`, `-> dict`, `-> HTMLResponse`, etc.

### W-T05 `_check_rate_limit` uses mutable global without thread safety
**File:** `src/dealsim_mvp/app.py`, lines 43-70
**Severity:** Warning (pylint: global-variable-not-assigned-to-lock)
`_rate_store` (a `defaultdict`) is mutated from multiple async contexts (the middleware runs per-request) with no locking. Under uvicorn with multiple workers, race conditions are possible.
**Fix:** Wrap mutations in a `threading.Lock`, or switch to an `asyncio.Lock` if staying single-worker async.

### W-T06 `Optional` vs `X | None` inconsistency
**File:** `src/dealsim_mvp/api/models.py` uses `float | None` (line 68)
**File:** `src/dealsim_mvp/core/store.py` uses `dict[str, Any]` (line 22)
**Severity:** Info
The codebase consistently uses `X | None` (PEP 604 syntax) which is correct for Python 3.10+. No `Optional[]` usage found. This is good -- no action needed, noted for completeness.

### W-T07 `_TOPIC_KEYWORDS` defined inside function
**File:** `src/dealsim_mvp/core/debrief.py`, lines 619-631
**Severity:** Warning (pylint: consider-moving-to-module-scope)
A large dict literal is rebuilt on every call to `_find_undiscovered_constraints`.
**Fix:** Move `_TOPIC_KEYWORDS` to module scope as a constant.

### W-T08 `field_validator` redundant with Field(gt=0)
**File:** `src/dealsim_mvp/api/models.py`, lines 43-48
**Severity:** Info
```python
target_value: float = Field(gt=0, ...)

@field_validator("target_value")
@classmethod
def target_must_be_positive(cls, v: float) -> float:
    if v <= 0:
        raise ValueError("target_value must be positive")
    return v
```
`Field(gt=0)` already enforces positivity. The validator is dead code.
**Fix:** Remove the `@field_validator` method.

### W-T09 Missing `from __future__ import annotations`
**File:** `src/dealsim_mvp/core/persona.py`
**Severity:** Warning (ruff: FA100)
Uses `list[str]` syntax in dataclass fields but lacks the future annotations import. This works at runtime on Python 3.10+ but will fail on 3.9.
**Fix:** Add `from __future__ import annotations` at the top, consistent with all other modules in the project.

### W-T10 `app.py` line 107 potential `None` dereference
**File:** `src/dealsim_mvp/app.py`, line 107
**Severity:** Warning (mypy: union-attr)
```python
client_ip = request.client.host if request.client else "unknown"
```
This is correctly guarded, but `request.client` has type `Address | None` and mypy may still flag the `.host` access. Current code is fine at runtime.

---

## 3. Complexity

### C-CX01 `_parse_offer_components` is 125 lines
**File:** `src/dealsim_mvp/api/offer_analyzer.py`, lines 395-519
**Severity:** Critical (pylint: too-many-statements, ruff: C901)
This function has ~125 lines and handles regex extraction for 7 different component types inline.
**Fix:** Extract each component parser into a helper (e.g., `_extract_base_salary`, `_extract_signing_bonus`).

### W-CX02 `admin_stats_html` builds HTML inline (~90 lines)
**File:** `src/dealsim_mvp/app.py`, lines 174-267
**Severity:** Warning (pylint: too-many-statements)
An HTML template is constructed via f-string in a 90-line function.
**Fix:** Move the template to a Jinja2 template file or a separate string constant.

### W-CX03 `_analyse_moves` has high cyclomatic complexity
**File:** `src/dealsim_mvp/api/debrief.py`, lines 257-351
**Severity:** Warning (ruff: C901, estimated complexity ~14)
Nested match/case with multiple branches for user and opponent turns.
**Fix:** Split into `_analyse_user_move` and `_analyse_opponent_move` helper functions.

### W-CX04 `generate_playbook` in `api/debrief.py` is 105 lines
**File:** `src/dealsim_mvp/api/debrief.py`, lines 149-254
**Severity:** Warning (pylint: too-many-statements)
**Fix:** Extract the strengths/weaknesses analysis into a separate `_analyze_user_patterns(state)` function.

---

## 4. Dead Code

### W-DC01 Duplicate models in `api/models.py`
**File:** `src/dealsim_mvp/api/models.py`
**Severity:** Warning (pylint: duplicate-code)
The file header says "mirrors them for documentation and test import purposes" but `routes.py` defines its own identical models. The models in `api/models.py` are never imported by any production code.
**Fix:** Either use the models from `api/models.py` in `routes.py`, or delete `api/models.py` and keep models inline. Current state creates a maintenance burden -- changes to one must be mirrored in the other.

### W-DC02 Unused import: `Literal`
**File:** `src/dealsim_mvp/api/models.py`, line 13
**Severity:** Warning (ruff: F401)
```python
from typing import Any, Literal
```
`Literal` is imported but never used in the file.
**Fix:** Remove `Literal` from the import.

### W-DC03 `_USER_WANTS_DOWN` and `_USER_WANTS_UP` frozensets unused
**File:** `src/dealsim_mvp/core/simulator.py`, lines 262-268
**Severity:** Warning (ruff: F841)
```python
_USER_WANTS_DOWN = frozenset({...})
_USER_WANTS_UP = frozenset({...})
```
These are defined but never referenced by any function. The direction detection uses `_user_wants_more()` which checks anchors/persona, not these sets. They appear to be leftover from a refactor.
**Fix:** Remove both frozensets.

### I-DC04 `os` imported but only used via `Path`
**File:** `src/dealsim_mvp/core/session.py`, lines 17-18
**Severity:** Info
`import logging` and `import threading` are used, but the file also does `from dealsim_mvp.core.store import save_sessions, load_sessions` which handles all file operations. The session module itself doesn't use `os` directly.
**Fix:** No action needed -- `os` is not imported here. Noted as false positive.

### I-DC05 Redundant `field_validator` (see W-T08 above)
**File:** `src/dealsim_mvp/api/models.py`, lines 43-48
**Severity:** Info
Covered in W-T08. The validator is dead code given the `Field(gt=0)` constraint.

---

## 5. Anti-Patterns

### C-AP01 Bare `except` clauses
**File:** `src/dealsim_mvp/core/analytics.py`, line 57
**File:** `src/dealsim_mvp/analytics.py`, lines 241-242, 257-258
**File:** `src/dealsim_mvp/feedback.py`, lines 169-170, 185-186
**File:** `src/dealsim_mvp/core/store.py`, lines 69, 94, 135
**File:** `src/dealsim_mvp/core/session.py`, lines 222, 237
**Severity:** Critical (ruff: E722, pylint: bare-except)
Multiple `except Exception:` clauses that silently swallow errors with only a `logger.debug/warning`. While this is intentional (analytics should never break the API), there are some `except Exception: pass` blocks (e.g., `routes.py` lines 78-79, 85-86) that lose all diagnostic information.
**Fix:** At minimum, add `logger.debug("...", exc_info=True)` to the bare `pass` handlers in `routes.py`. The existing `except Exception: logger.warning(...)` pattern in analytics/feedback/store is acceptable for non-critical I/O.

### C-AP02 Global mutable state for rate limiting without locking
**File:** `src/dealsim_mvp/app.py`, lines 43-70
**Severity:** Critical (see W-T05)
`_rate_store` and `_last_cleanup` are global mutable state modified without synchronization.
**Fix:** Add a module-level `_rate_lock = threading.Lock()` and wrap the cleanup and append operations.

### W-AP03 `md5` used for challenge selection
**File:** `src/dealsim_mvp/api/analytics.py` (via `core/analytics.py`), line 310
**Severity:** Warning (pylint: insecure-hash)
```python
idx = int(hashlib.md5(today.encode()).hexdigest(), 16) % len(CHALLENGE_POOL)
```
While this is not a security context (just deterministic selection), `md5` is flagged by linters as insecure.
**Fix:** Use `hashlib.sha256` instead, or use `hash(today) % len(CHALLENGE_POOL)` since this is not a crypto context.

### W-AP04 Side effect at module import time
**File:** `src/dealsim_mvp/core/session.py`, line 241
**Severity:** Warning (pylint: import-side-effect)
```python
_restore_from_file()
```
This runs at import time, reading from disk. If the file is corrupt, the import could log warnings, and tests must clear `_SESSIONS` before each test (which they do).
**Fix:** Consider lazy initialization (restore on first access) or an explicit `init()` call in `app.py`.

### W-AP05 `_check_rate_limit` deletes from dict while iterating keys
**File:** `src/dealsim_mvp/app.py`, lines 64-65
**Severity:** Warning
```python
_rate_store[client_ip] = [t for t in timestamps if t > window]
if not _rate_store[client_ip]:
    del _rate_store[client_ip]
```
Line 67 then checks `len(_rate_store[client_ip])` which could KeyError if the delete on line 65 fired.
**Fix:** Restructure: filter timestamps, check length, then either append or delete.

### W-AP06 `_STORE_DIR` computed via `__file__` navigation
**File:** `src/dealsim_mvp/core/store.py`, lines 27-28
**Severity:** Warning
```python
_STORE_DIR = Path(__file__).resolve().parent.parent.parent.parent
```
Four `.parent` calls is fragile -- any restructuring breaks this.
**Fix:** Use an environment variable (e.g., `DEALSIM_DATA_DIR`) with fallback, consistent with how `analytics.py` and `feedback.py` handle their data directories.

---

## 6. Naming

### W-N01 Leading-underscore function exported in `__all__` equivalent
**File:** `src/dealsim_mvp/core/offer_analyzer.py`, `_normalize_key`, `_get_location_multiplier`
**Severity:** Warning
These private functions are imported by `api/offer_analyzer.py`:
```python
from dealsim_mvp.core.offer_analyzer import _normalize_key, _get_location_multiplier
```
Importing private functions breaks encapsulation.
**Fix:** Rename to `normalize_key` and `get_location_multiplier` (drop the underscore), or add a public wrapper.

### I-N02 Inconsistent variable abbreviation
**File:** various
**Severity:** Info
`conc_count` (debrief), `t` (for transparency, persona), `opp` (opponent), `sc` (scorecard) -- these are short but context-clear within their functions. Acceptable, but a style guide could standardize.

### I-N03 Mixed class naming in test files
**File:** `tests/test_debrief.py`, `tests/test_playbook.py`
**Severity:** Info
Test helper functions use `_persona()`, `_state_with_transcript()`, `_make_state()` -- different naming conventions across test files.
**Fix:** Standardize on one pattern (e.g., `make_persona`, `make_state`).

---

## 7. Comments / Docs

### W-D01 TODO in codebase
**File:** None found
No TODO/FIXME comments were found. This is good.

### W-D02 Stale module docstring in `api/models.py`
**File:** `src/dealsim_mvp/api/models.py`, lines 7-8
**Severity:** Warning
```
NOTE: The canonical models used at runtime are defined inline in routes.py.
This file mirrors them for documentation and test import purposes.
```
If this is intentional, it should be enforced (e.g., tests that verify parity). Currently nothing ensures the two sets of models stay in sync.
**Fix:** Either delete the file or use its models as the single source of truth.

### W-D03 Outdated `api/analytics.py` module docstring
**File:** `src/dealsim_mvp/api/analytics.py` (via `core/analytics.py`), line 1
**Severity:** Warning
Docstring says "Extended analytics: user progress tracking, pattern detection, daily challenges" but the file also contains the legacy CHALLENGE_POOL, `submit_challenge_response` with inline `import re`, and file I/O. The responsibilities have grown beyond what the docstring describes.
**Fix:** Update docstring or split the module.

### I-D04 BUG-XX fix comments
**File:** `src/dealsim_mvp/core/simulator.py` (BUG-01, BUG-02, BUG-05), `src/dealsim_mvp/core/scorer.py` (SCORE-01), `src/dealsim_mvp/core/debrief.py` (DEBRIEF-01, DEBRIEF-02), `src/dealsim_mvp/core/playbook.py` (PLAY-01, DEBRIEF-03), `src/dealsim_mvp/core/persona.py` (PERSONA-01, PERSONA-04)
**Severity:** Info
Multiple `# BUG-XX fix:` and `# PERSONA-XX fix:` comments reference an issue tracking system. These are useful for history but add noise for new contributors.
**Fix:** Keep them, but consider linking to a docs file or commit SHAs for context.

### I-D05 Inline `import re` inside function
**File:** `src/dealsim_mvp/api/analytics.py` (via `core/analytics.py`), line 318
**Severity:** Info
```python
def submit_challenge_response(user_id: str, response_text: str) -> dict:
    import re
```
Lazy import inside a function. `re` is a stdlib module with no import cost.
**Fix:** Move to top-level imports.

### I-D06 Long docstring examples could be doctests
**File:** `src/dealsim_mvp/core/email_audit.py`, lines 389-409
**Severity:** Info
The `audit_negotiation_email` docstring has properly formatted `>>>` examples that could run as doctests. Currently they are not wired into the test suite.
**Fix:** Add `pytest --doctest-modules` to the test configuration or explicitly test these in `test_tools.py`.

---

## 8. Imports

### C-I01 Circular import risk: `session.py` imports at module level then again locally
**File:** `src/dealsim_mvp/core/session.py`
**Severity:** Critical
Module-level imports include `from dealsim_mvp.core.persona import NegotiationPersona, generate_persona_for_scenario` and `from dealsim_mvp.core.simulator import NegotiationState, RuleBasedSimulator, SimulatorBase, Turn`. Then `_deserialize_session` (line 140) re-imports `NegotiationStyle, PressureLevel` from `persona` and `MoveType, TurnSpeaker` from `simulator` locally. This is not a circular import (the modules don't import `session`), but the redundant local import is confusing.
**Fix:** Import all needed names at module level.

### W-I02 `core/analytics.py` depends on `api/analytics.py` via `app.py` re-export
**File:** `src/dealsim_mvp/api/routes.py`, line 60-67
**Severity:** Warning
`routes.py` imports from both `api.analytics` and `core.analytics` (indirectly via `core.session`). The two `analytics` modules (`core/analytics.py` and the top-level `analytics.py`) have confusingly similar names.
**Fix:** Rename `src/dealsim_mvp/core/analytics.py` to `core/user_analytics.py` or merge with `api/analytics.py` to reduce naming confusion.

### W-I03 `secrets` imported but only used in one branch
**File:** `src/dealsim_mvp/app.py`, line 15
**Severity:** Warning (ruff: F401-conditional)
`secrets` is used in `_verify_admin` which only runs if `DEALSIM_ADMIN_KEY` is set. The import itself is fine, but pylint may flag it as "could be lazy".
**Fix:** No change needed -- stdlib imports are cheap. Add `# noqa` if the linter insists.

### W-I04 `re` imported at function scope
**File:** `src/dealsim_mvp/api/analytics.py` (via `core/analytics.py`), line 318
**Severity:** Warning
Same as I-D05. `import re` inside `submit_challenge_response`.
**Fix:** Move to module-level.

### I-I05 Import order: fastapi before stdlib
**File:** `src/dealsim_mvp/app.py`
**Severity:** Info (ruff: I001)
Imports are generally well-ordered (stdlib, then third-party, then local). However, `from html import escape as html_escape` (stdlib) appears after several other stdlib imports, and `from fastapi import Query as FastQuery` is inside the function.
**Fix:** Run `ruff --fix` with isort rules to auto-sort.

---

## 9. Constants / Magic Numbers

### W-MN01 Hardcoded rate limit message
**File:** `src/dealsim_mvp/app.py`, line 110
**Severity:** Warning
```python
content={"detail": "Rate limit exceeded. Max 100 requests per minute."},
```
The message hardcodes "100" but the actual limit is `RATE_LIMIT` (configurable via env var).
**Fix:** Use `f"Rate limit exceeded. Max {RATE_LIMIT} requests per minute."`.

### W-MN02 Hardcoded `"salary"` and `"medium"` defaults in routes
**File:** `src/dealsim_mvp/api/routes.py`, lines 445-446
**Severity:** Warning
```python
scenario_type="salary",
difficulty="medium",
```
In `api_complete_session`, when recording user history, the scenario type and difficulty are hardcoded rather than read from the session state.
**Fix:** Read from the session's scenario metadata. This is a bug as well as a magic string issue.

### W-MN03 Magic numbers in scoring thresholds
**File:** `src/dealsim_mvp/core/scorer.py`, various lines
**Severity:** Warning
Values like `0.20`, `0.10`, `0.02`, `0.40`, `70`, `78`, `95`, `55`, `30` appear as raw numbers in scoring logic.
**Fix:** Define named constants: `ANCHOR_STRONG_THRESHOLD = 0.20`, `ANCHOR_MODERATE_THRESHOLD = 0.10`, etc.

### W-MN04 Magic numbers in concession scoring
**File:** `src/dealsim_mvp/core/scorer.py`, lines 294-302
**Severity:** Warning
`0.03`, `0.07` thresholds for average concession percentage.
**Fix:** Constants: `CONCESSION_SMALL_THRESHOLD = 0.03`, `CONCESSION_LARGE_THRESHOLD = 0.07`.

### W-MN05 Hardcoded port/host defaults scattered
**File:** `src/dealsim_mvp/app.py`, line 91
**Severity:** Info
`"http://localhost:3000", "http://localhost:8000"` hardcoded as fallback CORS origins.
**Fix:** Define as module constants: `DEFAULT_CORS_ORIGINS = [...]`.

### I-MN06 `_MAX_AGE_SECONDS = 3600` is well-named
**File:** `src/dealsim_mvp/core/store.py`, line 31
**Severity:** Info
Good practice -- named constant with comment. No action needed.

### I-MN07 `MAX_ROUNDS = 20` is well-named
**File:** `src/dealsim_mvp/core/session.py`, line 79
**Severity:** Info
Good. No action needed.

### I-MN08 Scoring weights well-structured
**File:** `src/dealsim_mvp/core/scorer.py`, lines 51-58
**Severity:** Info
`_WEIGHTS` dict is clean and self-documenting. No action needed.

---

## 10. Testing

### W-TS01 `api_get_session` returns persona name as `status`
**File:** `src/dealsim_mvp/api/routes.py`, line 492
**Severity:** Warning (this is a bug caught by reviewing test behavior)
```python
status=state.persona.name,
```
The `SessionStateResponse.status` field receives the opponent's name instead of the session status. No test catches this because `test_api.py` line 147 only checks `assert data["session_id"] == sid`.
**Fix:** Change to `status=session_status.value` or similar. Add assertion in `test_api.py`: `assert data["status"] in ("active", "completed", "abandoned")`.

### W-TS02 Test accesses private `_SESSIONS`
**File:** `tests/conftest.py`, lines 15, 101, 114
**Severity:** Warning (pylint: protected-access)
```python
from dealsim_mvp.core.session import _SESSIONS
```
Tests directly manipulate the private session store.
**Fix:** Add a public `clear_all_sessions()` function to `session.py` for test use, or use a test-specific fixture that patches the store.

### W-TS03 No tests for `core/store.py` directly
**File:** `tests/`
**Severity:** Warning
The file persistence layer (`save_sessions`, `load_sessions`, `clear_store`) has no direct unit tests. It is exercised indirectly through integration tests, but edge cases (corrupt JSON, missing directory, concurrent writes) are untested.
**Fix:** Add `tests/test_store.py` with tests for corrupt file handling, missing directory creation, and the auto-clean logic.

### W-TS04 Random seed not controlled in all persona tests
**File:** `tests/test_persona.py`, lines 100-122
**Severity:** Warning
Tests for difficulty adjustment use `random.seed(42)` to control template selection, but other tests (`test_salary_scenario_returns_persona`) don't seed and could theoretically produce different templates on different runs.
**Fix:** Use `random.seed()` in a fixture or parametrize over all template keys.

### I-TS05 `test_api.py` missing tests for debrief/playbook/offer endpoints
**File:** `tests/test_api.py`
**Severity:** Info
API-level tests exist for sessions, feedback, and health, but the debrief, playbook, offer analysis, earnings calculator, email audit, challenges, and user history endpoints have no API-level tests (only unit tests via `test_debrief.py`, `test_offer_analyzer.py`, etc.).
**Fix:** Add integration tests in `test_api.py` that hit the full HTTP endpoints for these features.

### I-TS06 No negative test for `CreateSessionRequest` with missing `target_value`
**File:** `tests/test_api.py`
**Severity:** Info
The API tests don't verify that `POST /api/sessions` with no `target_value` returns 422.
**Fix:** Add: `r = client.post("/api/sessions", json={}); assert r.status_code == 422`.

---

## High-Priority Fixes (do these first)

1. **C-AP01** -- Add logging to bare `except: pass` blocks in `routes.py` (lines 78-79, 85-86).
2. **C-T02** -- Thread-safe singletons in `analytics.py` and `feedback.py`.
3. **C-AP02** -- Thread-safe rate limiter in `app.py`.
4. **W-TS01** -- Bug: `api_get_session` returns persona name as session status.
5. **W-MN02** -- Bug: hardcoded `"salary"`/`"medium"` in `api_complete_session` user history recording.
6. **W-DC01** -- Resolve duplicate Pydantic models between `api/models.py` and `routes.py`.
7. **W-DC03** -- Remove unused `_USER_WANTS_DOWN` / `_USER_WANTS_UP` frozensets.
