# Architecture Review: DealSim MVP

**Reviewer scope:** All Python source, HTML, configs, and docs in the repository.
**Date:** 2026-03-19

---

## 1. Module Boundaries

The codebase follows a two-layer architecture: `core/` for domain logic and `api/` for HTTP concerns. This is a sound split. However, the boundary is blurred in several places.

**What works well:**
- `core/simulator.py`, `core/scorer.py`, `core/persona.py` form a clean domain triangle with unidirectional dependencies (simulator imports persona; scorer imports simulator).
- `core/session.py` acts as the orchestrator and is the only core module that touches persistence (via `core/store.py`).
- No circular imports exist. The dependency graph is a DAG.

**Boundary violations:**
- `core/analytics.py` (the legacy shim) is misplaced. It lives at `core/` but is just a delegation layer to the top-level `analytics.py` and `feedback.py`. This creates a confusing name collision: `core/analytics.py` and `api/analytics.py` serve completely different purposes.
- `app.py` defines admin endpoints inline (lines 147-267) rather than in a router. This 120-line HTML template embedded in the app factory violates separation of concerns.
- `core/session.py` imports from `core/store.py` and calls `_restore_from_file()` at module-load time (line 241), which means importing the module has side effects. This makes testing harder and creates hidden initialization order dependencies.

---

## 2. Coupling

**Dependency map (imports flow downward):**

```
app.py
  -> api/routes.py
       -> core/session.py
       -> api/debrief.py      (wraps core/debrief.py + core/playbook.py)
       -> api/offer_analyzer.py (wraps core/offer_analyzer.py)
       -> api/analytics.py
       -> analytics.py (top-level)
       -> feedback.py (top-level)

api/offer_analyzer.py
  -> core/offer_analyzer.py   (imports private helper _normalize_key)

core/session.py
  -> core/persona.py
  -> core/scorer.py
  -> core/simulator.py
  -> core/store.py
```

**Hidden dependencies:**
- `api/offer_analyzer.py` imports `_normalize_key` and `_get_location_multiplier` (prefixed with underscore, signalling "private") from `core/offer_analyzer.py`. This couples the API layer to internal implementation details of the core. If the core renames or refactors these helpers, the API breaks silently.
- `routes.py` directly accesses `_SESSIONS` in `conftest.py` via `from dealsim_mvp.core.session import _SESSIONS`. This is a test-only concern but it indicates the session store has no proper public interface for clearing state.
- `core/store.py` derives `_STORE_DIR` by walking four `parent` levels from `__file__` (line 27). This path calculation is fragile and breaks if the package structure changes.

---

## 3. Cohesion

**Well-cohesive modules:**
- `core/scorer.py` does one thing: score a negotiation. Six dimension scorers, one public entry point, clean output types. Textbook single-responsibility.
- `core/earnings.py` is a self-contained financial calculator with clear math, doctest examples, and no unnecessary dependencies.
- `core/email_audit.py` is similarly focused: regex-based email analysis with a single public function.
- `core/challenges.py` encapsulates all 30 daily challenges with a clean API.

**Cohesion problems:**
- `api/routes.py` is a 846-line God file. It defines 25+ Pydantic models inline AND 15+ route handlers AND helper functions. The models should live in `api/models.py` (which already exists but is noted as "partially unused" and contains duplicates of the inline models).
- `core/persona.py` (647 lines) mixes two concerns: the `NegotiationPersona` dataclass definition and 10 scenario-specific template dictionaries (each 30-50 lines of lambda-based persona factories). The templates should be a separate `core/scenarios.py` file.
- `api/offer_analyzer.py` (594 lines) is a near-complete reimplementation of offer analysis alongside the existing `core/offer_analyzer.py` (991 lines). Both parse offers, both have market benchmarks, both generate counter strategies. This is the most significant structural problem in the codebase (see section 4).

---

## 4. DRY Violations

### Critical: Dual offer analyzer implementations

`core/offer_analyzer.py` and `api/offer_analyzer.py` implement the same concept with different interfaces:

| Concern | `core/offer_analyzer.py` | `api/offer_analyzer.py` |
|---------|-------------------------|------------------------|
| Offer parsing | `parse_offer_text()` with 20+ regex patterns | `_parse_offer_components()` with 8 simpler regexes |
| Market benchmarks | `SALARY_BENCHMARKS` (10 roles x 5 levels) | `SALARY_BENCHMARKS` derived from core, senior-level only |
| Counter strategies | `_build_counter_strategies()` (3 tiers, percentile-targeted) | `_generate_counter_strategies()` (simpler, 10-15% bumps) |
| Email audit | Not present | `audit_email()` (basic keyword scorer) |
| Email audit (real) | Not present (core) | `core/email_audit.py` (full regex engine, 464 lines) |

The core version is more sophisticated (percentile interpolation, location multipliers on all benchmarks, pay-period detection, equity ratio benchmarks). The API version is simpler but provides different output types. Neither delegates cleanly to the other.

Similarly, `core/email_audit.py` and the `audit_email()` function in `api/offer_analyzer.py` are two independent email analysis implementations. The core version (464 lines, pattern libraries, rewriter) is far more capable than the API version (95 lines, keyword checks).

### Other duplications:
- File rotation logic is copy-pasted between `analytics.py` (lines 192-228) and `feedback.py` (lines 120-156). Identical code, different file paths.
- JSONL read/write helpers (`_append`, `_read_all`, `_ensure_dir`) appear in `analytics.py`, `feedback.py`, and `api/analytics.py`. Three copies of the same pattern.
- Direction detection logic (`_user_wants_more` / `_detect_direction` / `_negotiation_direction`) appears in `core/simulator.py`, `core/playbook.py`, and `core/debrief.py` with slightly different implementations. Each checks `reservation_price > opening_offer` but with different fallback behavior.
- The `_round_to_clean` helper in `core/playbook.py` (lines 197-205) is nearly identical to `_round_offer` in `core/simulator.py` (lines 457-464), differing only in rounding granularity.

---

## 5. Naming

**Strengths:**
- Module names are descriptive: `scorer`, `simulator`, `persona`, `playbook`, `debrief`.
- Enum values use clear domain language: `NegotiationStyle.COLLABORATIVE`, `MoveType.BATNA_SIGNAL`.
- Private helpers are consistently prefixed with underscore.

**Issues:**
- `core/analytics.py` (the shim) vs `api/analytics.py` (user progress) vs `analytics.py` (top-level tracker). Three files with the same name at different paths. A developer searching for "analytics" will find the wrong one.
- `OfferAnalysis` is defined in both `core/offer_analyzer.py` and `api/offer_analyzer.py` with different fields. Same class name, different modules, incompatible shapes.
- `CounterStrategy` exists in both `core/offer_analyzer.py` (dataclass with `adjustments` dict) and `api/offer_analyzer.py` (dataclass with `suggested_counter` string). Same name, different semantics.
- `generate_debrief` is defined in both `core/debrief.py` and `api/debrief.py` with different signatures and return types. `core/` returns `DebriefResult`; `api/` returns `DebriefReport`.
- `generate_playbook` exists in both `core/playbook.py` (returns `PlaybookResult`) and `api/debrief.py` (returns `Playbook`). Different parameters, different output shapes.
- The `_fmt` helper in `simulator.py` is too terse for a 712-line file. `_format_currency` (used in `core/offer_analyzer.py`) is the same function with a clearer name.
- `EarningsImpact` is defined in both `core/earnings.py` and `api/offer_analyzer.py` with completely different fields.

---

## 6. Type Hints

The codebase is well-typed. Nearly every function has parameter and return type annotations, including union types (`float | None`), generics (`dict[str, list[float]]`), and dataclass fields.

**Gaps:**
- `routes.py` endpoint functions return Pydantic models but several return `dict` instead (e.g., `api_submit_feedback` returns `{"status": "ok"}` without a response model).
- `api/analytics.py` functions like `get_user_history` and `get_user_patterns` return `dict` instead of typed dataclasses. The route handler then manually unpacks with `**`.
- `core/session.py` `_serialize_session` and `_deserialize_session` use `dict` for their serialized format rather than a TypedDict, making the schema implicit.
- The `scenario` parameter in `create_session` and `generate_playbook` is typed as `dict | None` when it has a well-known shape (`type`, `target_value`, `difficulty`). A `ScenarioConfig` dataclass would catch key errors at static analysis time.

---

## 7. Docstrings

**Strengths:**
- Every module has a file-level docstring explaining purpose, unit conventions, and design decisions. This is excellent practice.
- `core/offer_analyzer.py` and `core/earnings.py` include doctest-compatible examples.
- `core/scorer.py` explains its scoring philosophy in the module docstring.
- Functions that implement non-obvious logic (e.g., `_compute_opponent_offer`, `_estimate_percentile`) document the algorithm.

**Gaps:**
- `api/routes.py` endpoint functions have FastAPI `summary` metadata but no Python docstrings explaining error conditions or side effects.
- `api/debrief.py` private helper `_analyse_moves` (352 lines) has no docstring.
- Several `core/playbook.py` helpers (`_build_opening_line`, `_build_danger_phrases`) lack docstrings despite having non-obvious behavior.
- `core/store.py` `_STORE_DIR` calculation (line 27) has no comment explaining the 4-parent traversal.

---

## 8. Configuration

**Environment variables (documented in `.env.example`):**
- `DEALSIM_ENV`, `DEALSIM_HOST`, `DEALSIM_PORT`, `DEALSIM_WORKERS`
- `DEALSIM_CORS_ORIGINS`, `DEALSIM_ADMIN_KEY`
- `DEALSIM_MAX_SESSIONS`, `DEALSIM_SESSION_TTL_HOURS`
- `DEALSIM_DATA_DIR`, `STATIC_DIR`, `LOG_LEVEL`, `RATE_LIMIT_PER_MINUTE`

**Magic numbers not extracted to configuration:**
- `MAX_ROUNDS = 20` in `session.py` is a constant but not configurable.
- `_MAX_AGE_SECONDS = 3600` (1 hour) in `store.py` is hardcoded; `.env.example` documents `DEALSIM_SESSION_TTL_HOURS` but `store.py` does not read it.
- Rate limit `100` is in the error message string (line 112, `app.py`) separately from the `RATE_LIMIT` variable.
- `_MAX_FILE_BYTES = 10 * 1024 * 1024` in `analytics.py` and `feedback.py` is hardcoded.
- `_MAX_ROTATED_FILES = 3` is hardcoded in two places.
- Scorer dimension weights (`_WEIGHTS` dict in `scorer.py`) are hardcoded. This is defensible for an MVP but a candidate for configuration if scoring needs tuning.
- All salary benchmarks in `core/offer_analyzer.py` are hardcoded Python dicts rather than external data files. This is documented as intentional ("bundled data") but means updating benchmarks requires a code deploy.

**Configuration inconsistency:**
- `.env.example` lists `DEALSIM_SESSION_TTL_HOURS=1` but the code uses `_MAX_AGE_SECONDS = 3600` without reading the env var. These are disconnected.
- `DEALSIM_MAX_SESSIONS` appears in `.env.example` but is never read by any code.

---

## 9. Extensibility

### Adding a new scenario type

**Current process:** Add a template dict to `core/persona.py` (e.g., `NEW_SCENARIO_TEMPLATES`), add the key to the `templates` dict in `generate_persona_for_scenario`, add the scenario type to `_USER_WANTS_DOWN` or `_USER_WANTS_UP` in `simulator.py`, and add a description to `_build_scenario_summary` in `playbook.py`. Optionally add a `ScenarioItem` to the `SCENARIOS` list in `routes.py`.

**Assessment:** This requires touching 3-4 files with no registry or plugin mechanism. It works at the current scale (10 scenarios) but would benefit from a scenario registry that auto-discovers templates and wires up direction detection. The direction sets (`_USER_WANTS_DOWN`, `_USER_WANTS_UP`) in `simulator.py` are a maintenance trap: forget to add a new type and direction detection silently falls back to the wrong default.

### Adding a new scoring dimension

**Current process:** Add a scorer function `_score_new_dimension` in `scorer.py`, add its weight to `_WEIGHTS` (which must sum to 1.0, so all other weights must be adjusted), and add it to the `dimensions` list in `generate_scorecard`. The debrief and playbook modules would need corresponding updates to handle the new dimension in their analysis.

**Assessment:** Moderately difficult. The weight normalization is manual and error-prone. A registration pattern (list of `(scorer_fn, weight)` tuples) would make this safer.

### Adding a new simulator engine (LLM backend)

**Current process:** Subclass `SimulatorBase`, override `generate_response`. Pass the new instance to `create_session(simulator=...)`.

**Assessment:** Well-designed. The abstract base class pattern is the right call. The `NegotiationState` dataclass is flat and JSON-serializable, ready for LLM context injection. This is the most extensible part of the architecture.

---

## 10. Technical Debt: Two-Day Refactor Plan

### Day 1: Eliminate the dual offer analyzer (4-6 hours)

This is the highest-impact refactor. Currently, `core/offer_analyzer.py` and `api/offer_analyzer.py` duplicate offer parsing, market benchmarks, and counter-strategy generation.

**Action:**
1. Make `core/offer_analyzer.py` the single source of truth for all analysis logic.
2. Reduce `api/offer_analyzer.py` to a thin adapter that maps core output types to API response shapes (like `api/debrief.py` should be doing, but for offers).
3. Consolidate the two email audit implementations: route through `core/email_audit.py` and delete the 95-line `audit_email()` in `api/offer_analyzer.py`.
4. Consolidate `EarningsImpact`: route through `core/earnings.py` and map to the API response shape.
5. Stop importing private helpers (`_normalize_key`, `_get_location_multiplier`) from core; either make them public or add proper delegation functions.

### Day 1 continued: Extract JSONL infrastructure (1-2 hours)

Create a `core/jsonl_store.py` with a generic `JsonlStore` class that handles:
- Thread-safe append
- Read-all with JSON error tolerance
- File rotation
- Directory creation

Replace the three copies in `analytics.py`, `feedback.py`, and `api/analytics.py` with instances of this class.

### Day 2: Split the God file and fix naming collisions (3-4 hours)

**Action:**
1. Move all Pydantic models from `routes.py` to `api/models.py`. Delete the existing duplicate models in `api/models.py` and replace with the authoritative set from `routes.py`.
2. Extract the admin HTML dashboard from `app.py` into `api/admin.py` (a separate router).
3. Rename `core/analytics.py` (the legacy shim) to `core/analytics_compat.py` or delete it entirely if no code depends on the old import path.
4. Consider renaming `api/analytics.py` to `api/user_progress.py` to disambiguate from the event-tracking `analytics.py`.

### Day 2 continued: Consolidate direction detection (1-2 hours)

Create a single `core/direction.py` (or add to a shared `core/utils.py`) with one canonical `detect_negotiation_direction(persona, state=None)` function. Replace the three independent implementations in `simulator.py`, `playbook.py`, and `debrief.py`.

### Day 2 continued: Fix configuration drift (1 hour)

- Make `store.py` read `DEALSIM_SESSION_TTL_HOURS` from the environment.
- Either implement `DEALSIM_MAX_SESSIONS` or remove it from `.env.example`.
- Extract the duplicated rate-limit number from the error message string.
- Remove the module-load side effect in `session.py` (line 241) by making `_restore_from_file` lazy (call on first access, not on import).

---

## Summary Scorecard

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Module boundaries | B | Clean core/api split, but blurred by inline admin + shim file |
| Coupling | B+ | Mostly unidirectional; private-import leak is the main issue |
| Cohesion | C+ | `routes.py` is a God file; `persona.py` mixes data and logic |
| DRY | D+ | Dual offer analyzer is a serious violation; JSONL helpers x3 |
| Naming | C+ | Three files named `analytics`; two `OfferAnalysis` classes |
| Type hints | A- | Consistently typed; minor gaps in API return types |
| Docstrings | A- | Module-level docs are excellent; some helper gaps |
| Configuration | B- | Env vars documented but some are disconnected from code |
| Extensibility | B+ | Simulator swap point is well-designed; scenario addition is manual |
| Overall | B- | Solid domain modeling with a clear duplication problem in the API layer |

The domain core (`simulator.py`, `scorer.py`, `persona.py`) is well-engineered. The technical debt is concentrated in the API adaptation layer, where rapid feature addition created parallel implementations rather than proper delegation. The two-day refactor plan above would bring the codebase to a B+ overall.
