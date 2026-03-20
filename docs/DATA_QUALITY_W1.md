# Data Quality Audit — Week 1

**Date:** 2026-03-19
**Scope:** `core/offer_analyzer.py` (primary engine) and `api/offer_analyzer.py` (API layer)
**Auditor:** Data Quality Analyst

---

## Executive Summary

Two separate offer analyzer implementations exist with **incompatible architectures**. The `core/` version uses role+level+location-multiplier design; the `api/` version uses role+location-as-key design with separate senior_ role entries. Neither is clearly canonical. This is the single biggest data quality risk: a user could get different market positioning depending on which code path runs.

Beyond the architectural split, salary data is labeled as "2024 approximations" — stale for a 2026 product. Several high-demand roles are missing, location coverage has gaps, and edge cases can produce misleading output.

---

## 1. Accuracy — Salary Benchmarks vs. 2026 Market

### core/offer_analyzer.py

Data is self-documented as "US-market 2024 data." For 2026, these numbers are 5-12% low across the board due to cumulative wage growth in tech (3-6% annually post-2023 recovery).

| Role | Level | Bundled p50 | Estimated 2026 p50 | Delta |
|------|-------|-------------|---------------------|-------|
| software_engineer | senior | $155,000 | $170,000-$180,000 | -10% to -14% |
| software_engineer | staff | $200,000 | $220,000-$240,000 | -9% to -17% |
| product_manager | senior | $160,000 | $175,000-$185,000 | -9% to -14% |
| data_scientist | senior | $160,000 | $175,000-$185,000 | -9% to -14% |
| designer | senior | $138,000 | $150,000-$160,000 | -8% to -14% |

**Verdict:** Systematically low. Users will be told their offers are higher-percentile than they actually are — directly harmful to negotiation outcomes.

### api/offer_analyzer.py

Same "2024" label. This version has per-city benchmarks which are closer to real market data for top metros (SF senior SWE p50 at $220K is reasonable for 2024 but still ~$240K in 2026). However, it only covers 5-7 cities per role and falls back to "national" — which is significantly lower.

**Recommendation:**
- Apply a blanket 1.08 inflation multiplier to all 2024 figures as a stopgap for 2026.
- Add a `DATA_VINTAGE` constant and a warning when data is >12 months old.
- Long-term: integrate a refresh mechanism (even if just a JSON file swap).

---

## 2. Coverage — Missing Roles

### Currently covered (core):
software_engineer, product_manager, data_scientist, designer, marketing_manager, sales_representative, general

### Missing high-demand roles:

| Missing Role | Why It Matters | Estimated 2026 p50 (senior, national) |
|-------------|----------------|---------------------------------------|
| data_engineer | One of the fastest-growing roles in tech | $165,000-$180,000 |
| devops_engineer / sre | Distinct comp bands from SWE | $160,000-$175,000 |
| engineering_manager | Management track diverges significantly from IC | $185,000-$210,000 |
| technical_program_manager | Common in FAANG, distinct from PM | $170,000-$195,000 |
| security_engineer | Premium over general SWE | $170,000-$190,000 |
| ai_ml_engineer | Massive premium in 2025-2026 market | $190,000-$230,000 |
| solutions_engineer / sales_engineer | Higher than pure sales base, different structure | $130,000-$155,000 |
| finance / accounting | Non-tech roles that negotiate too | $90,000-$120,000 |
| hr / people_ops | Common offer-negotiation users | $80,000-$110,000 |

The `_ROLE_KEYWORDS` mapping in `core/` groups "data_engineer" under "data_scientist" and "devops" under "software_engineer" — both are wrong. Data engineers earn differently from data scientists (higher base, less equity), and DevOps/SRE comp bands differ from general SWE.

**Recommendation:**
- Add at minimum: `data_engineer`, `engineering_manager`, `devops_engineer`, `ai_ml_engineer`.
- Fix `_ROLE_KEYWORDS` so "data engineer" does not map to "data_scientist".
- The `api/` version has `senior_software_engineer` as a separate role — good pattern, extend to other roles.

---

## 3. Location Multipliers

### core/offer_analyzer.py multipliers:

| City | Multiplier | Assessment |
|------|-----------|------------|
| san_francisco | 1.30 | **Low.** SF premium is 30-40% over national median in 2026. Should be 1.35-1.40. |
| new_york | 1.25 | Reasonable for 2024, slightly low for 2026. |
| seattle | 1.15 | **Low.** Seattle tech pay rivals NYC. Should be 1.20-1.25. |
| boston | 1.15 | Reasonable. |
| los_angeles | 1.12 | Reasonable. |
| austin | 1.00 | **Low.** Austin has appreciated significantly since 2020. Should be 1.05-1.08. |
| chicago | 0.95 | Reasonable. |
| dallas | 0.92 | Reasonable. |
| phoenix | 0.90 | Reasonable. |
| remote | 1.00 | Problematic — see note below. |

### Missing cities:

| City | Expected Multiplier | Relevance |
|------|-------------------|-----------|
| Miami | 1.05-1.10 | Growing tech hub, significant hiring |
| Raleigh-Durham | 0.95-1.00 | Research Triangle, major employer base |
| Salt Lake City | 0.92-0.95 | Growing tech presence |
| Philadelphia | 1.00-1.05 | Large metro, pharma tech |
| Detroit | 0.88-0.92 | Auto tech resurgence |
| Nashville | 0.90-0.95 | Healthcare tech hub |
| Columbus | 0.88-0.92 | Emerging tech market |
| Pittsburgh | 0.92-0.95 | AI/robotics cluster |

### Remote multiplier problem:

`remote: 1.00` is an oversimplification. Companies apply different remote policies:
- SF-anchored remote (levels.fyi pattern): 0.90-1.00 of SF rate
- National flat rate: typically p50 national
- Location-adjusted remote: varies by employee's location

**Recommendation:**
- Increase SF to 1.35, Seattle to 1.22, Austin to 1.06.
- Add Miami, Raleigh, Pittsburgh, Philadelphia at minimum.
- Consider splitting "remote" into "remote_sf_anchor" (1.10) and "remote_national" (1.00).

### api/offer_analyzer.py:

This version avoids multipliers entirely by embedding per-city benchmarks directly. This is more accurate but much sparser — only 5-7 cities per role. The fallback to "national" is a large drop (e.g., SF SWE p50 $170K vs national $130K = 30% cliff).

**Recommendation:** Add `remote_us` data for all roles in the API version (it's only present for SWE currently).

---

## 4. Negotiability Scores

### core/offer_analyzer.py:

| Component | Score | Assessment |
|-----------|-------|------------|
| base_salary | HIGH | Correct. |
| signing_bonus | HIGH | Correct. |
| equity | MEDIUM | **Incorrect for most contexts.** At startups and public tech cos, equity is HIGH negotiability — it's often the primary lever for senior hires. At non-tech or small companies, it may be LOW (no equity to give). A flat "medium" is misleading. |
| annual_bonus | LOW | Correct for formula-based bonuses. **But target bonus % is MEDIUM negotiable at many companies.** |
| remote_days | MEDIUM | Correct post-2024 — many companies have hardened RTO policies making this LOW in 2026. |
| start_date | HIGH | Correct. |
| title | MEDIUM | Correct. |
| review_cycle | HIGH | **Overrated.** Few candidates successfully negotiate accelerated review cycles. MEDIUM is more realistic. |
| relocation | MEDIUM | Correct. |
| pto_days | LOW | Correct at scale companies. MEDIUM at startups/small cos. |

### api/offer_analyzer.py:

This version has a different mapping — notably it rates equity as HIGH and RSU as MEDIUM, which is backwards (RSUs are the primary equity vehicle at public companies and are highly negotiable; generic "equity" at a startup is often less negotiable because the pool is fixed).

**Recommendation:**
- Make negotiability context-dependent. At minimum, add company-type as a parameter: `startup`, `public_tech`, `non_tech`, `enterprise`. Equity negotiability varies from HIGH (public tech, startup) to LOW (non-tech).
- Downgrade `review_cycle` to MEDIUM in `core/`.
- Add a 2026 note for `remote_days`: negotiability is trending LOW as RTO policies harden.

---

## 5. Counter-Offer Strategies

### core/offer_analyzer.py strategy tiers:

| Tier | Salary Target | Signing Multiplier | Risk |
|------|--------------|-------------------|------|
| Conservative | p50 | 1.0x | Very low |
| Balanced | p75 | 1.3x | Low-moderate |
| Aggressive | p90 | 1.6x | Moderate |

**Issues found:**

1. **Conservative is too timid.** Targeting p50 means "ask for the median" — that is not a counter-offer, that is accepting market rate. If the offer is already at p50, conservative produces no adjustment. **Fix:** Conservative should target p60 (interpolate between p50 and p75).

2. **Signing bonus multiplier compounding.** The aggressive tier applies 1.6x to the location-adjusted signing benchmark at p90. For a senior in SF: `$75,000 * 1.30 * 1.6 = $156,000` signing bonus. That is unrealistically high outside of FAANG principal+ offers. **Fix:** Cap signing bonus suggestions at 1.5x the p75 benchmark.

3. **Equity upside is annualized by dividing by 4.** This is correct for RSU vesting, but the upside figure is then mixed with annual salary and signing bonus deltas without labeling — a user might think the "estimated upside" is annual when it is actually a mix of annual (salary, bonus), one-time (signing), and annualized-from-4yr (equity). **Fix:** Break estimated_upside into `annual_upside`, `one_time_upside`, and `equity_4yr_upside`.

4. **Missing components always suggest asking for them, even in conservative.** A conservative strategy should not suggest asking for 3+ new components — that contradicts the "preserve goodwill" framing. **Fix:** Conservative should suggest at most 1 missing component (the highest-negotiability one).

5. **No total-comp ceiling check.** The aggressive strategy could suggest a total comp package that exceeds the role's realistic ceiling. E.g., a junior SWE in Phoenix could be told to ask for p90 salary + p90 signing + equity — totaling well above what any employer would offer for that level. **Fix:** Add a sanity cap: total suggested comp should not exceed 1.3x the p90 total comp benchmark for the role/level.

### api/offer_analyzer.py strategies:

Much simpler: flat +10-15% counter, add missing signing bonus at 10% of base, add equity if missing, package optimization. These are safe but generic — they do not use the benchmark data at all. The counter is always 15% regardless of whether the offer is at p25 or p90.

**Recommendation:** The API version should use the benchmark data it has. A +15% counter on an already-p90 offer is bad advice.

---

## 6. Text Parser

### core/offer_analyzer.py parser (more sophisticated):

Tested mentally against common formats:

| Input Pattern | Expected Parse | Actual Parse | Status |
|--------------|---------------|--------------|--------|
| "base salary of $150,000" | base_salary: 150000 | Correct | PASS |
| "$150,000 per year" | base_salary: 150000 | Correct | PASS |
| "salary: $150,000" | base_salary: 150000 | Correct | PASS |
| "signing bonus of $25,000" | signing_bonus: 25000 | Correct | PASS |
| "sign-on bonus: $25,000" | signing_bonus: 25000 | Correct | PASS |
| "RSU grant of $200,000" | equity: 200000 | Correct | PASS |
| "10,000 RSUs" | equity_shares: 10000 | Correct (stored in other) | PASS |
| "target bonus of 15%" | bonus_pct: 15 | Correct | PASS |
| "150k base" | base_salary: ? | **FAIL** — no pattern handles "150k" format | FAIL |
| "$150K/yr" | base_salary: ? | **FAIL** — no "K" suffix handling | FAIL |
| "annual comp of $150,000" | base_salary: ? | **FAIL** — "comp" not in pattern set | FAIL |
| "OTE of $250,000" | ? | **FAIL** — OTE (on-target earnings) not handled | FAIL |
| "TC: $350K" | ? | **FAIL** — total comp abbreviation not handled | FAIL |
| "$2,500 bi-weekly" | base_salary: 2500? | **MISLEADING** — would need 26x conversion | FAIL |

### api/offer_analyzer.py parser:

Handles "K/k" suffix (good), but has its own gaps:
- The "last resort" fallback grabs ANY number with $ as base_salary — highly error-prone. A "$5,000 relocation" could become base_salary.
- No market positioning is applied to parsed components (the `market_position` field stays None).

**Recommendation:**
- Add "K/k" suffix handling to `core/` parser: `r"\$?\s*([\d,]+(?:\.\d{1,2})?)\s*[kK]"` with 1000x multiplier.
- Add "OTE", "total comp", "TC", "total compensation", "annual comp" patterns.
- Add bi-weekly/monthly to annual conversion: detect "bi-weekly", "biweekly", "semi-monthly", "monthly" and multiply appropriately.
- Remove the "grab any number" fallback from `api/` — it causes more harm than good.

---

## 7. Edge Cases

### $0 salary:

In `core/`: `_estimate_percentile(0, benchmarks)` will compute synthetic p0 as `benchmarks["p25"] * 0.70` (e.g., $56,000 for a mid SWE). Since 0 < 56,000, it returns percentile 0. The counter strategies will then suggest asking for p50/p75/p90 — reasonable behavior. **No crash, but no warning** that a $0 salary is likely a data entry error.

### $10M salary:

`_estimate_percentile(10_000_000, benchmarks)` hits the synthetic p100 ceiling (`p90 * 1.15`, e.g., ~$189,750 for mid SWE). Returns percentile 100. Counter strategies say "Already at or above target — hold firm." **Correct behavior** for a legitimate outlier, but there should be a warning for likely data entry errors (>p99 could flag "This salary is unusually high for the role — please verify.").

### Missing base_salary:

`core/analyze_offer()` requires `base_salary` as a positional argument — cannot be None. Good.
`api/analyze_offer()` accepts free text and may produce an empty components list. The overall_score defaults to 50, which is misleading for a "we found nothing" result.

### Negative values:

No validation. `analyze_offer(base_salary=-50000)` will produce a negative percentile position and counter strategies suggesting you "ask for" the p50 benchmark. **Fix:** Add `if base_salary <= 0: raise ValueError`.

### Non-US currencies:

Both parsers assume USD. Input like "base salary of 80,000 GBP" would parse as $80,000 USD. No currency detection exists.

### Very high equity with low base:

An offer of $80K base + $2M equity (early-stage startup) would show the base at a low percentile but equity off the charts. The market_comparison text handles this okay, but the counter strategies would still suggest raising the base to p75 without considering that total comp is already very high.

**Recommendation:**
- Add input validation: salary must be > 0 and < $5,000,000 (or flag with warning).
- Add a "data entry check" tier: if base < $30K, warn "This may be a monthly or hourly rate."
- Add currency detection (at minimum, recognize GBP/EUR/CAD suffixes and warn).
- API version: return a clear "insufficient data" status when no components are parsed.
- Add total-comp awareness: if base is low but equity is high, note this in the analysis.

---

## 8. Architectural Inconsistency Between Two Files

This is the highest-priority issue. Two implementations exist:

| Aspect | core/offer_analyzer.py | api/offer_analyzer.py |
|--------|----------------------|---------------------|
| Benchmark structure | role -> level -> percentiles, with location multiplier | role (with level baked in) -> city -> percentiles |
| Equity benchmarks | Ratio-based (fraction of base) | Not included |
| Signing bonus | Separate benchmark table | Not included (10% of base heuristic) |
| Counter strategies | Market-data-driven, 3 tiers | Flat +10-15%, generic |
| Text parser | Regex-based, returns dict | Regex-based, returns OfferComponent list |
| Missing component detection | Yes | No |
| Earnings impact calculator | No | Yes |
| Email audit | No | Yes |

Neither file imports the other. They share no code.

**Recommendation:** Pick one as canonical and deprecate the other. The `core/` version has better benchmark depth (equity, signing, levels). The `api/` version has better per-city data and useful extras (earnings impact, email audit). Merge the best of both into `core/`, make `api/` a thin wrapper.

---

## Priority Fixes (ordered by user-impact)

### Critical (ship-blocking):

1. **Update salary data to 2026 levels.** Apply 1.08 multiplier at minimum. Label data vintage.
2. **Reconcile the two implementations.** Users must not get different answers from different code paths.
3. **Add input validation.** Reject negative salaries, warn on extreme outliers.

### High (quality-of-life):

4. **Add missing roles:** data_engineer, engineering_manager, devops_engineer, ai_ml_engineer.
5. **Fix K/k suffix parsing** in core parser.
6. **Make equity negotiability context-dependent** (startup vs public vs non-tech).
7. **Fix conservative strategy** — target p60, not p50.
8. **Cap aggressive strategy suggestions** with a total-comp ceiling.

### Medium (completeness):

9. Add missing cities: Miami, Raleigh, Pittsburgh, Philadelphia.
10. Update Seattle multiplier from 1.15 to 1.22.
11. Add OTE/TC/bi-weekly parsing patterns.
12. Break down estimated_upside into annual/one-time/equity components.
13. Add "remote_us" data for all roles in API version.

### Low (polish):

14. Add currency detection and warning for non-USD inputs.
15. Downgrade review_cycle negotiability to MEDIUM.
16. Add total-comp awareness to counter strategies.
17. Add the `calculate_earnings_impact` function to the core module.
