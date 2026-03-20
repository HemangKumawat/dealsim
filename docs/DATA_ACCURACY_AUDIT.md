# Data Accuracy Audit — DealSim Offer Analyzer

**Auditor:** Claude (data analyst review)
**Date:** 2026-03-19
**Files reviewed:**
- `src/dealsim_mvp/core/offer_analyzer.py`
- `src/dealsim_mvp/api/offer_analyzer.py`
- `src/dealsim_mvp/core/earnings.py`
- `src/dealsim_mvp/core/email_audit.py`

---

## 1. Salary Benchmarks — Realism Check

**Methodology claimed:** 2024 base data * 1.08 (+8% for 2025-2026 wage growth).

### Software Engineer (national, no location multiplier)

| Level  | DealSim p50 | Levels.fyi 2024 approx p50 | Expected 2026 (×1.08) | Verdict |
|--------|-------------|----------------------------|------------------------|---------|
| Junior | $102,600    | ~$95K-100K                 | $103K-108K             | OK      |
| Mid    | $129,600    | ~$120K-130K                | $130K-140K             | OK — slightly conservative |
| Senior | $167,400    | ~$155K-175K                | $167K-189K             | OK — low end of range |
| Staff  | $216,000    | ~$200K-240K                | $216K-259K             | OK — conservative but valid |
| Lead   | $194,400    | ~$180K-210K                | $194K-227K             | OK      |

**Assessment:** Benchmarks are reasonable for national averages across all companies (not FAANG-only). Levels.fyi skews toward large tech, where TC is higher. For a general-market tool, these numbers are appropriately conservative. The 8% cumulative adjustment for two years of wage growth is slightly generous (BLS shows ~4-5% cumulative tech wage growth 2024-2026) but within acceptable range.

### Non-SWE Roles Spot-Check

- **Engineering Manager senior p50 = $205,200** — reasonable, aligns with ~$190K base in 2024.
- **Designer junior p50 = $77,760** — reasonable, entry UX/product design.
- **Marketing Manager junior p50 = $66,960** — reasonable for early-career marketing.
- **Sales Representative junior p50 = $59,400** — reasonable for base (excludes commission, which is correct since this is base salary only).

**ISSUE:** Sales compensation is heavily commission-based. The tool should note that sales benchmarks are base-only and total OTE may be 1.5-2x base. Currently no such caveat exists.

**H1B data cross-reference:** H1B salary data (prevailing wage) for Software Engineer L3 (senior) in 2024 clusters around $150K-180K nationally. The $167,400 p50 falls squarely within that range after adjustment.

**Overall salary verdict: PASS** — benchmarks are realistic, slightly conservative, appropriate for a general-market tool.

---

## 2. Location Multipliers — Accuracy Check

| City            | DealSim | Expected Range | Verdict |
|-----------------|---------|----------------|---------|
| San Francisco   | 1.30    | 1.30-1.50      | OK — low end; SF is often 1.35-1.45 for tech |
| NYC             | 1.25    | 1.20-1.40      | OK — middle of range |
| Seattle         | 1.15    | 1.10-1.20      | OK |
| Boston          | 1.15    | 1.10-1.20      | OK |
| Los Angeles     | 1.12    | 1.10-1.20      | OK |
| Austin          | 1.00    | 1.00-1.10      | OK — conservative but defensible |
| Denver          | 1.00    | 1.00-1.05      | OK |
| Chicago         | 0.95    | 0.90-1.00      | OK |
| Dallas          | 0.92    | 0.88-0.95      | OK |
| Phoenix         | 0.90    | 0.85-0.95      | OK |
| Pittsburgh      | 0.94    | 0.85-0.95      | OK |
| Remote          | 1.00    | 0.95-1.05      | OK — reasonable default |

**ISSUE (minor):** SF at 1.30 is on the low end. For FAANG-tier companies in SF, 1.40-1.50 is more accurate. However, for a general-market tool, 1.30 is defensible since it includes non-tech employers.

**ISSUE (missing cities):** No entries for major tech hubs: San Jose, Cupertino, Mountain View (distinct from SF/bay_area in some data sets). Also missing: Salt Lake City, Columbus, Charlotte, Nashville — all growing tech markets. The "default" 1.00 fallback handles these, which is acceptable.

**Overall location verdict: PASS** — multipliers are within expected ranges. SF is on the conservative side.

---

## 3. Equity Benchmarks — Reasonableness by Stage/Size

Equity is expressed as a fraction of base salary (4-year total grant).

### Software Engineer Equity Ratios

| Level  | p50 ratio | Example (at $167K base p50) | Assessment |
|--------|-----------|----------------------------|------------|
| Junior | 0.5x      | $51K over 4yr ($12.8K/yr)  | Reasonable for mid-market; FAANG gives more |
| Mid    | 0.8x      | $104K over 4yr ($26K/yr)   | OK |
| Senior | 1.2x      | $201K over 4yr ($50K/yr)   | OK for mid-market; FAANG senior RSUs can be 2-4x |
| Staff  | 2.0x      | $432K over 4yr ($108K/yr)  | OK — FAANG staff can be much higher |
| Lead   | 1.5x      | $291K over 4yr ($73K/yr)   | OK |

**ISSUE (significant):** The equity benchmarks are applied against the **p50 salary benchmark** (line 444: `abs_equity_bench = {k: v * adj_salary_bench["p50"]`), NOT against the candidate's actual base salary. This means equity percentile is measured against what the median person's equity would look like. This is technically defensible (it's a market benchmark, not a personal ratio), but should be documented more clearly for users.

**ISSUE:** No distinction between company stages. A Series A startup offering 0.1% of the company in options ($0 current value) vs a public company offering $200K in RSUs are fundamentally different. The tool treats all equity as a dollar value, which works for RSUs but poorly for pre-IPO options. The `parse_offer_text` function does handle share counts separately (stores as `equity_shares` in `other_components`), but there's no way to input a strike price or company valuation to convert options to estimated value.

**ISSUE:** The `general` equity benchmarks have p25=0.0 for junior roles, which means the percentile interpolation for $0 equity would yield ~percentile 25 (not 0). This is misleading — many non-tech roles genuinely have zero equity.

**Overall equity verdict: PASS with caveats** — reasonable for public-company RSU grants. Inadequate for startup option grants. No company-stage differentiation.

---

## 4. Counter-Offer Strategy — Edge Case Testing

### Edge Case 1: $50K Senior SWE in SF (obvious lowball)

- Location multiplier: 1.30
- Adjusted senior SWE benchmarks: p50 = $167,400 * 1.30 = **$217,620**
- Offer of $50K: percentile calculation...
  - Synthetic p0 anchor: p25 * 0.70 = $140,400 * 1.30 * 0.70 = **$127,764**
  - $50K < $127,764, so percentile = **0**
- Conservative strategy: target p50 = $217,620, delta = +$167,620 (+335%)
- Balanced: target p75 = $259,740, delta = +$209,740 (+419%)
- Aggressive: target p90 = $294,840, delta = +$244,840 (+490%)

**Verdict:** The system correctly identifies this as an extreme lowball (0th percentile). The counter-strategies correctly suggest massive increases. The percentage display ("+335%") might alarm users but is mathematically correct. **PASS** — the system handles lowball offers well.

### Edge Case 2: $300K Junior SWE in Rural Area (obviously high)

- Location multiplier: 1.00 (default/rural)
- Junior SWE benchmarks: p25=$86,400, p50=$102,600, p75=$124,200, p90=$140,400
- Synthetic p100 anchor: p90 * 1.15 = $161,460
- $300K > $161,460, so percentile = **100**
- All strategies: "Already at or above target — hold firm."

**Verdict:** The system correctly identifies this as above-market (100th percentile) and tells the user to hold firm on base. It would still suggest asking for missing components (signing bonus, equity, etc.), which is sensible advice. **PASS.**

### Edge Case 3: $0 Equity in a Startup Offer

- If `equity=0` is passed, the equity percentile calculation would evaluate 0 against the equity benchmarks.
- For senior SWE general equity: p25=0.3, p50=0.8 → absolute p50 = 0.8 * $167,400 = $133,920
- Synthetic p0 = p25_abs * 0.70 = 0.3 * $167,400 * 0.70 = $35,154
- $0 < $35,154, so percentile = **0**
- Counter strategies would suggest requesting equity grants.

**Verdict: PASS** — correctly identifies $0 equity as below-market and suggests asking for it.

**BUT:** If `equity=None` (not provided), it appears in `missing_components` and is surfaced as a negotiation lever. If `equity=0` (explicitly zero), it's treated as "provided but at 0th percentile." Both paths work correctly. **PASS.**

### Edge Case 4: base_salary = $1 (minimum boundary)

- Passes validation (SALARY_MIN = 1).
- Would produce percentile 0, and all counter-strategies would suggest large increases.
- Division in `_build_counter_strategies` line 634: `pct = delta / base_salary * 100` — with base_salary=1, this produces enormous percentages but no crash.

**Verdict: PASS** — handles gracefully, if unrealistically.

### Edge Case 5: base_salary = 0

- Raises `ValueError` per SALARY_MIN check. **PASS.**

---

## 5. Text Parser — Offer Letter Format Handling

### Formats tested (mental walkthrough):

| Input Format | Expected Parse | Verdict |
|---|---|---|
| "base salary of $150,000" | base_salary = 150000 | PASS |
| "salary: $150K" | base_salary = 150000 | PASS |
| "$120,000 per year" | base_salary = 120000 | PASS |
| "$5,769.23 bi-weekly" | base_salary = 5769.23 * 26 = ~$150K | PASS |
| "$6,250 semi-monthly" | base_salary = 6250 * 24 = $150K | PASS |
| "$12,500 per month" | base_salary = 12500 * 12 = $150K | PASS |
| "signing bonus of $25,000" | signing_bonus = 25000 | PASS |
| "RSU grant of $200,000" | equity = 200000 | PASS |
| "10,000 shares" | equity_shares = 10000 (in other_components) | PASS |
| "target bonus of 15%" | bonus_pct = 15 | PASS |
| "20 days of PTO" | pto_days = 20 | PASS |

**ISSUE (core parser):** The `_CURRENCY_OR_K` pattern `(?:\$[\d,]+[kK]|\$?[\d,]+[kK]|\$[\d,]+(?:\.\d{2})?)` has a subtlety: `$?[\d,]+[kK]` would match bare numbers followed by K even without a dollar sign. In practice this is usually fine but could false-match text like "150K users" as a salary.

**ISSUE (API parser):** The API-layer parser (`api/offer_analyzer.py` `_parse_offer_components`) is a completely separate implementation from the core parser. The two parsers have different regex patterns and may produce different results for the same input. This is a maintenance risk. The API parser lacks the pay-period annualization logic (bi-weekly, monthly) that the core parser has.

**ISSUE (API parser):** The API parser does not call the core `analyze_offer()` function at all. It builds its own `OfferAnalysis` dataclass (different fields from core's). The API layer does not use the core's percentile calculations, location multipliers, or counter-strategy generation. The `_generate_counter_strategies` in the API layer is much simpler — it just suggests +10-15% on base without any market-data backing.

**This is the most significant finding in the audit.** The API layer and core layer are diverged implementations. A user hitting the API gets a substantially different (and less sophisticated) analysis than what the core module produces.

**Overall parser verdict: PARTIAL PASS** — core parser is solid. API parser is a separate, weaker implementation.

---

## 6. Percentile Calculation — Mathematical Correctness

The `_estimate_percentile` function uses linear interpolation between synthetic anchor points:

```
(0,   p25 * 0.70)    — synthetic p0
(25,  p25)
(50,  p50)
(75,  p75)
(100, p90 * 1.15)    — synthetic p100
```

### Verification with senior SWE national benchmarks:
- p25 = $140,400, p50 = $167,400, p75 = $199,800, p90 = $226,800
- Synthetic p0 = $140,400 * 0.70 = $98,280
- Synthetic p100 = $226,800 * 1.15 = $260,820

**Test: value = $167,400 (should be percentile 50)**
- Falls in segment (25, $140,400) to (50, $167,400)
- fraction = ($167,400 - $140,400) / ($167,400 - $140,400) = 1.0
- percentile = 25 + 1.0 * (50 - 25) = **50** ✓

**Test: value = $153,900 (midpoint of p25-p50)**
- fraction = ($153,900 - $140,400) / ($167,400 - $140,400) = 0.5
- percentile = 25 + 0.5 * 25 = **37** ✓ (rounding to int)

**Test: value = $98,280 (synthetic p0 boundary)**
- Falls at points[0][1], returns **0** ✓

**ISSUE (mathematical):** The synthetic p0 anchor at p25 * 0.70 means the function maps the range [p25*0.70, p25] to percentiles [0, 25]. This creates a non-linear mapping because the p0-p25 span is 30% of p25, while the p25-p50 and p50-p75 spans are actual market data. The result is that below-p25 values have compressed percentiles (small dollar differences produce large percentile swings), while above-p90 values have expanded percentiles (the p90-to-p100 synthetic span is 15% of p90). This is a reasonable approximation but should be disclosed.

**ISSUE (mathematical):** The function maps p90 to percentile 75 in the interpolation points (the 4th point is `(75, p75)` and the 5th is `(100, p90*1.15)`). Wait — re-reading: the points are (0, p25*0.70), (25, p25), (50, p50), (75, p75), (100, p90*1.15). So p90 itself falls in the (75, p75) to (100, p90*1.15) segment. Let me verify:

**Test: value = $226,800 (p90)**
- Segment: (75, $199,800) to (100, $260,820)
- fraction = ($226,800 - $199,800) / ($260,820 - $199,800) = $27,000 / $61,020 = 0.4425
- percentile = 75 + 0.4425 * 25 = **86** (int)

So p90 data maps to ~86th percentile, not 90th. **This is a systematic error.** The function underestimates percentiles for values near p90. A value that is literally at the 90th percentile of market data will be reported as ~86th percentile.

**Root cause:** The interpolation maps the p90 value into a segment that extends beyond it to a synthetic p100 anchor, so the actual 90th percentile value no longer maps to 90.

**Severity:** Medium. The error is ~4 percentile points at the p90 level. Users near the top of market will see slightly deflated percentiles.

**Fix suggestion:** Change the interpolation points to: (0, p25*0.70), (25, p25), (50, p50), (75, p75), (90, p90), (100, p90*1.15). This adds a 5th real anchor.

**Overall percentile verdict: PASS with known bias** — math is correct for the chosen interpolation scheme, but the scheme systematically underreports percentiles above p75.

---

## 7. Compound Interest Math — Manual Verification (earnings.py)

### API layer: `calculate_earnings_impact` (api/offer_analyzer.py)

Formula: `sum(diff * (1.03)^i for i in range(years))`

**Manual check: diff = $10,000, 5 years, 3% raises**
- Year 0: $10,000.00
- Year 1: $10,300.00
- Year 2: $10,609.00
- Year 3: $10,927.27
- Year 4: $11,255.09
- Sum: **$53,091.36**

Geometric series formula: $10,000 * (1.03^5 - 1) / (1.03 - 1) = $10,000 * (1.15927 - 1) / 0.03 = $10,000 * 5.30914 = **$53,091.36** ✓

### Core layer: `calculate_lifetime_impact` (core/earnings.py)

**Manual check: increase=$10,000, 5 years, 0% raises, 10% contribution, 50% match, 0% returns**
- Each year: salary_diff = $10,000
- Cumulative salary after 5 years: **$50,000** ✓ (matches doctest)
- Employee contrib/yr = $10,000 * 10% = $1,000
- Employer match/yr = $1,000 * 50% = $500
- Total retirement contribution/yr = $1,500
- After 5 years (0% return): $1,500 * 5 = **$7,500** ✓ (matches doctest)

**Manual check: increase=$10,000, 1 year, 0% raises, 10% contribution, 100% match, 0% returns**
- Employee contrib = $1,000
- Employer match = $1,000 * 100% = $1,000
- Retirement = **$2,000** ✓ (matches doctest)

**Manual check with investment returns: increase=$10,000, 3 years, 3% raises, 10% contribution, 50% match, 7% returns**
- Year 1: salary_diff = $10,000; contrib = $1,000 + $500 = $1,500; balance = 0 * 1.07 + $1,500 = $1,500.00
- Year 2: salary_diff = $10,300; contrib = $1,030 + $515 = $1,545; balance = $1,500 * 1.07 + $1,545 = $1,605 + $1,545 = $3,150.00
  - Actually: $1,500 * 1.07 = $1,605.00; + $1,545 = **$3,150.00**
- Year 3: salary_diff = $10,609; contrib = $1,060.90 + $530.45 = $1,591.35; balance = $3,150 * 1.07 + $1,591.35 = $3,370.50 + $1,591.35 = **$4,961.85**

The formula `balance = balance * (1 + invest_rate) + employee_contrib + employer_contrib` correctly implements end-of-year contribution with beginning-of-year compounding on prior balance. **PASS.**

**Overall earnings math verdict: PASS** — both implementations are mathematically correct.

---

## 8. Email Audit Scoring — Calibration Review (core/email_audit.py)

### Scoring Model

- Starts at 100, deducts per issue:
  - HIGH severity: -15 points
  - MEDIUM severity: -8 points
  - LOW severity: -4 points
- Bonus: +3 per power phrase (max +10)
- Floor: 0, ceiling: 100

### Calibration Test Cases

**Perfect email** (gratitude + anchor + justification + power phrases + proper close):
- No deductions
- Power phrase bonus: +10
- Score: **100** — appropriate ✓

**Terrible email** ("I was hoping if possible to maybe get a raise. Sorry to ask. I feel like I deserve more."):
- Hedging: "i was hoping" (-15), "if possible" (-15), "sorry to ask" (-15), "i feel like" (-15)
- Missing anchor: -15
- Missing justification: -15
- Too short (<30 words): -4
- Missing gratitude: -4
- Missing specific close: -8
- Total deductions: -106
- Score: max(0, 100 - 106) = **0** (before power phrase bonus)
- No power phrases: final = **0**

This is harsh but appropriate — that email would genuinely torpedo a negotiation. ✓

**Mediocre email** ("Thank you for the offer. I'd like to request $95,000 based on my research."):
- No hedging: 0
- Has anchor ($95,000): 0
- Has justification ("based on"): 0
- Too short (~15 words): -4
- Has gratitude opening: 0
- Has specific close ("I'd like to request"): 0
- Score: 100 - 4 = 96
- Power phrases: "based on my research" (+3), "I'd like to request" is in SPECIFIC_ASK_CLOSERS not POWER_PHRASES... checking: "based on my research" matches "based on my research" in POWER_PHRASES → +3
- Final: min(100, 96 + 3) = **99**

**ISSUE:** A very short email (15 words) that happens to hit all the keyword triggers scores 99. The length penalty (-4) is too light for such a brief email. In practice, a 15-word negotiation email would be ineffective regardless of keyword coverage.

**ISSUE:** The scoring is purely additive/subtractive based on keyword presence. It cannot detect:
- Contradictory statements (hedging in one sentence, demanding in the next)
- Logical incoherence
- Missing context about what specifically is being negotiated
- Tone mismatches (formal opener with casual closer)

This is acknowledged in the docstring ("regex/keyword-based — no LLM dependency") and is a reasonable tradeoff for a no-LLM tool.

**ISSUE (API layer email audit):** The `audit_email` function in `api/offer_analyzer.py` is a completely separate implementation from `core/email_audit.py`. It has different scoring (starts at 50, not 100), different keyword lists, and no rewriter. Again, two diverged implementations.

### Deduction Weights Assessment

| Check | Severity | Deduction | Fair? |
|-------|----------|-----------|-------|
| Hedging phrase (each) | HIGH | -15 | Yes — each hedge compounds damage |
| Missing anchor | HIGH | -15 | Yes — the single most impactful element |
| Missing justification | HIGH | -15 | Yes — unsupported asks fail |
| Passive voice (each) | MEDIUM | -8 | Yes — impacts clarity but not fatal |
| Emotional language (each) | MEDIUM | -8 | Yes — can damage relationship |
| Too long (>300 words) | MEDIUM | -8 | OK — could argue this should be LOW |
| Missing specific close | MEDIUM | -8 | Yes — clear next-step matters |
| Missing gratitude opening | LOW | -4 | Yes — nice to have, not critical |
| Too short (<30 words) | LOW | -4 | Too light — should be MEDIUM (-8) |

**Overall email audit verdict: PASS** — scoring criteria are well-calibrated for a keyword-based system. Minor issue with short-email penalty being too light.

---

## 9. Critical Finding: API/Core Divergence

The most significant issue found in this audit is that the API layer (`api/offer_analyzer.py`) and the core layer (`core/offer_analyzer.py`) are **diverged implementations** that produce different results:

| Feature | Core | API |
|---------|------|-----|
| Salary benchmarks | Role + level + location | Role + location (senior level only) |
| Location adjustment | Applied to benchmarks | Applied to benchmarks (via core import) |
| Percentile calculation | Linear interpolation with 5 anchor points | Not implemented — uses above/below/at |
| Counter strategies | 3 tiers targeting specific percentiles | Generic +10-15%, add signing, add equity |
| Email audit | Starts at 100, 15+ checks, rewriter | Starts at 50, ~8 checks, no rewriter |
| Text parser | 6+ patterns per component, pay-period annualization | Separate regex set, no annualization |

**Impact:** Depending on which module is called, users get fundamentally different quality of analysis. The core module is substantially more sophisticated.

**Recommendation:** The API layer should delegate to the core module rather than reimplementing analysis logic. The API `analyze_offer` should call `core.offer_analyzer.parse_offer_text` + `core.offer_analyzer.analyze_offer` and then transform the result into the API's `OfferAnalysis` dataclass.

---

## Summary of Findings

| Area | Verdict | Issues |
|------|---------|--------|
| Salary benchmarks | **PASS** | Conservative but realistic; sales should note base-only |
| Location multipliers | **PASS** | SF slightly low (1.30 vs 1.35-1.45); missing some cities |
| Equity benchmarks | **PASS with caveats** | No company-stage differentiation; startup options poorly served |
| Counter strategies | **PASS** | All edge cases handled correctly |
| Text parser (core) | **PASS** | Solid regex coverage including pay periods |
| Text parser (API) | **PARTIAL PASS** | Weaker, diverged implementation |
| Percentile math | **PASS with known bias** | p90 maps to ~86th percentile due to interpolation scheme |
| Compound interest | **PASS** | Both implementations verified manually |
| Email audit (core) | **PASS** | Well-calibrated; short-email penalty too light |
| Email audit (API) | **PARTIAL PASS** | Simpler, diverged implementation |

### Priority Fixes

1. **HIGH: Unify API and core analysis paths.** The API layer should wrap the core, not reimplement it.
2. **MEDIUM: Fix percentile interpolation.** Add p90 as a real anchor point: `(90, p90)` between `(75, p75)` and `(100, p90*1.15)`.
3. **LOW: Add sales compensation caveat.** Note that sales benchmarks are base-only, excluding commission/OTE.
4. **LOW: Increase short-email penalty** in `core/email_audit.py` from LOW (-4) to MEDIUM (-8).
5. **LOW: Add startup equity guidance.** When equity is provided as share count with no dollar value, flag that options require valuation context.
