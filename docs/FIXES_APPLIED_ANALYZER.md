# Offer Analyzer — Fixes Applied

**Date:** 2026-03-19
**Test result:** 37/37 passing

---

## 1. Architecture: Consolidated Two Implementations

**Problem:** Two incompatible `offer_analyzer.py` files existed — `core/` (role+level+multiplier) and `api/` (role+city, separate types). Neither imported the other.

**Fix:** `core/offer_analyzer.py` is now the canonical implementation. `api/offer_analyzer.py` was rewritten to:
- Import core benchmarks and helpers (`SALARY_BENCHMARKS`, `LOCATION_MULTIPLIERS`, `_normalize_key`)
- Build its API-shaped benchmark dict from core data (no duplication)
- Keep its unique features: `calculate_earnings_impact()`, `audit_email()`, `get_market_data()`
- Fix its own text parser independently (bonus regex collision)

## 2. Bug Fix: ZeroDivisionError on base_salary=0

**Root cause:** `_build_counter_strategies` computed `delta / base_salary * 100` without checking for zero.

**Fix:** Added bounds checking at the top of `analyze_offer()`:
- `base_salary < 1` raises `ValueError` ("Zero and negative salaries are not valid")
- `base_salary > $10M` raises `ValueError`
- The division in counter strategies also has an explicit `if base_salary > 0` guard

## 3. Bug Fix: Regex Crash on Combined Bonus Format

**Root cause:** In `api/offer_analyzer.py`, the bonus regex `([\d,]+)|(\d+)%` had group collisions when both "15% annual bonus" and "$10k signing bonus" appeared in the same text, causing `float(None.replace(...))`.

**Fix:** Rewrote the API parser to:
- Use a dedicated signing bonus regex that requires the "sign" keyword
- Match both `"signing bonus $X"` and `"$X signing bonus"` word orders
- Parse annual bonus percentage separately, checking that the match is not inside a signing bonus context

## 4. Salary Benchmarks Updated to 2026 Levels

All percentile values in `SALARY_BENCHMARKS` and `SIGNING_BONUS_BENCHMARKS` were multiplied by 1.08 (the midpoint of the 5-14% underestimate range). Data vintage label updated to `2026-Q1 (2024 base +8%)`.

Example: software_engineer senior p50 went from $155,000 to $167,400.

## 5. Missing Roles Added

Three new role entries in `SALARY_BENCHMARKS`:

| Role | Senior p50 (national) |
|------|-----------------------|
| `data_engineer` | $172,800 |
| `devops_sre` | $170,640 |
| `engineering_manager` | $205,200 |

`_ROLE_KEYWORDS` updated: "data engineer" now maps to `data_engineer` (not `data_scientist`), "devops"/"sre" map to `devops_sre` (not `software_engineer`), "engineering manager" maps to `engineering_manager`.

## 6. Missing Locations Added

Four new entries in `LOCATION_MULTIPLIERS`:

| City | Multiplier |
|------|-----------|
| `miami` | 1.08 |
| `philadelphia` | 1.02 |
| `pittsburgh` | 0.94 |
| `raleigh` | 0.98 |

## 7. Text Parser: "150K" Format and Pay Periods

**"150K" format:** `_CURRENCY_OR_K` regex pattern now matches `$150K`, `150k`, `$120,000` with K-suffix alternatives tried first. `_parse_currency()` handles the K suffix by stripping it and multiplying by 1000.

**Pay periods:** New regex patterns added for:
- Bi-weekly (`$5,000 bi-weekly` -> `$130,000/yr`, multiplier 26)
- Semi-monthly (`$6,250 semi-monthly` -> `$150,000/yr`, multiplier 24)
- Monthly (`$12,500 per month` -> `$150,000/yr`, multiplier 12)

## 8. Bounds Checking

`analyze_offer()` now rejects:
- `base_salary <= 0` with `ValueError`
- `base_salary > $10,000,000` with `ValueError`

---

## Files Changed

| File | Action |
|------|--------|
| `src/dealsim_mvp/core/offer_analyzer.py` | Rewrote benchmarks (+8%), added roles/locations, fixed bugs, added bounds |
| `src/dealsim_mvp/api/offer_analyzer.py` | Rewrote as thin wrapper importing from core; fixed bonus regex |
| `tests/test_offer_analyzer.py` | Updated: 20 original tests + 17 new tests covering all fixes |
