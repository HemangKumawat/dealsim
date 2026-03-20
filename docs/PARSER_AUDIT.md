# Parser Audit: `parse_offer_text()` in `offer_analyzer.py`

**Date:** 2026-03-19
**Scope:** Regex-based text parser for extracting structured compensation data from unstructured offer letters.
**File:** `src/dealsim_mvp/core/offer_analyzer.py`, lines 922-990 (parser) and 726-837 (patterns/helpers).

---

## Architecture Summary

The parser uses a dictionary of pre-compiled regex patterns (`_PATTERNS`) organized by field name. For each field, it tries patterns in order and stops at the first match. Extracted strings are converted via `_parse_currency()` (handles `$120,000`, `$150K`) and `_parse_percent()`. Pay-period patterns (monthly, bi-weekly, semi-monthly) are auto-annualized via `_PAY_PERIOD_MULTIPLIERS`. Role and level are inferred from keyword matching against the full text.

---

## Test Case Results

### Case 1: "We're pleased to offer you a base salary of $165,000 per year"

**Extracted:**
- `base_salary`: $165,000 -- CORRECT. Matches pattern index 0 (`base salary of $165,000`) plus pattern index 1 confirms (`$165,000 per year`). Pattern 0 fires first.
- `role`: "general" (no role keywords present)
- `level`: "mid" (no level keywords present)
- `location`: "remote" (default)

**Missed:** Nothing significant. The parser correctly handles the most common offer format.

**Verdict:** PASS.

---

### Case 2: "Total compensation: $210K (base: $170K, bonus: 15%, RSU: $100K/4yr)"

**Extracted:**
- `base_salary`: Pattern 0 looks for "base salary/compensation/pay of|is|:" -- this text has "base:" without "salary" or "compensation" after "base". Pattern 0 fails. Pattern 1 looks for `CURRENCY per year/annum` -- not present. Patterns 2-4 (periodic) fail. Pattern 5: `salary of|is|: CURRENCY` -- no "salary" keyword. The parser falls through all base_salary patterns. However, "Total compensation: $210K" -- none of the patterns match "total compensation" as a base salary trigger. **BASE SALARY NOT EXTRACTED.** The `$210K` is the total comp, not base, so arguably correct to skip it -- but `$170K` (the actual base) is also missed because "base:" alone without "salary/compensation/pay" does not match pattern 0.
- `bonus_pct`: 15% -- CORRECT. Pattern `bonus\s*(?:of|is|:)?\s*(PERCENT)` matches "bonus: 15%".
- `equity`: $100K -- CORRECT. The RSU pattern matches "RSU... $100K". The `/4yr` suffix is not parsed but the dollar value is captured.
- `role`: "general"
- `level`: "mid"
- `location`: "remote"

**Missed:**
- **Base salary ($170K)** -- the "base:" shorthand without "salary" is not matched. This is the most critical miss.
- The "Total compensation: $210K" figure is ignored (which is correct behavior -- it's not a base salary).

**Bug:** Pattern 0 requires `base\s+(?:salary|compensation|pay)` but the input uses bare "base:" without those qualifiers. A pattern like `base\s*:\s*CURRENCY` would catch this.

**Verdict:** FAIL -- misses the base salary in a very common compact format.

---

### Case 3: "Starting salary: $85/hour, expected 40hrs/week"

**Extracted:**
- `base_salary`: Pattern 5 (`salary of|is|: CURRENCY`) matches "salary: $85". The `/hour` suffix is NOT part of the captured group. No pay-period multiplier is applied (pattern index 5 has no entry in `_PAY_PERIOD_MULTIPLIERS`). Result: **$85 annual**. This is catastrophically wrong -- should be ~$176,800 ($85 x 2080 hours).
- `role`: "general"
- `level`: "mid"
- `location`: "remote"

**Missed:**
- Hourly rate detection entirely absent. No pattern handles `$/hour` or `$/hr` formats.
- The `40hrs/week` context is ignored.

**Bug:** The parser has no hourly-rate pattern and no hourly-to-annual conversion. Pattern 5 captures `$85` as if it were an annual salary.

**Verdict:** FAIL -- critically misinterprets hourly rate as $85/year annual salary.

---

### Case 4: "Annual salary of EUR95,000 with a signing bonus of EUR10,000"

(Using EUR symbol in the actual test input.)

**Extracted:**
- `base_salary`: Pattern 0 looks for "annual salary of CURRENCY". The `_CURRENCY_OR_K` regex is `(?:\$[\d,]+[kK]|\$?[\d,]+[kK]|\$[\d,]+(?:\.\d{2})?)`. Every branch requires either a `$` sign or a `K/k` suffix. The EUR symbol is not `$`. **BASE SALARY NOT EXTRACTED.**
- `signing_bonus`: Same issue -- pattern requires `$` prefix. **NOT EXTRACTED.**
- `role`: "general"
- `level`: "mid"
- `location`: "remote"

**Missed:** Everything. The parser is USD-only by design. No EUR, GBP, or other currency support.

**Bug:** Not necessarily a bug (docs state "All monetary values are USD annual") but a significant limitation. The parser silently returns no salary rather than warning that a non-USD currency was detected.

**Verdict:** FAIL -- silently drops all compensation data for non-USD offers.

---

### Case 5: "Base: 150K, OTE: 250K, equity: 0.5% over 4 years"

**Extracted:**
- `base_salary`: Same issue as Case 2. "Base:" alone without "salary/compensation/pay" does not trigger pattern 0. Pattern 5 needs "salary" keyword. "150K" without `$` prefix: `_CURRENCY_OR_K` branch 2 is `\$?[\d,]+[kK]` -- the `$` is optional here, so `150K` should match if a pattern reaches it. But no base_salary pattern matches the context "Base: 150K". **NOT EXTRACTED.**
- `equity`: The equity pattern looks for "equity... of|is|:|-|valued at|worth CURRENCY". Input has "equity: 0.5% over 4 years". The `0.5%` is not a currency value -- it's a percentage of company ownership. The `_CURRENCY_OR_K` regex will not match `0.5%`. **NOT EXTRACTED as dollar value** (correct -- it's a percentage, not a dollar amount). But 0.5% equity is meaningful data that the parser cannot represent.
- `bonus_pct`: "OTE" (On-Target Earnings) is not recognized. No pattern for OTE. **NOT EXTRACTED.**
- `role`: "general"
- `level`: "mid"
- `location`: "remote"

**Missed:**
- Base salary (150K) due to the bare "Base:" pattern gap.
- OTE / on-target earnings concept entirely absent.
- Equity as a percentage of company (startup-style) not supported -- only dollar-valued equity or share counts.

**Verdict:** FAIL -- extracts nothing from a standard sales/startup comp format.

---

### Case 6: "We can offer $7,500/month starting March 15"

**Extracted:**
- `base_salary`: Pattern 4 matches `CURRENCY per month|monthly|/mo|/month`. The regex is `(CURRENCY_OR_K)\s*(?:per\s+month|monthly|/\s*(?:mo|month))`. Input has "$7,500/month". The `/month` matches `/\s*(?:mo|month)`. Pattern index 4 has multiplier 12.0. Result: **$7,500 x 12 = $90,000**. CORRECT.
- `start_date`: Pattern matches "starting March 15" -- but the start_date regex expects a format like "March 15, 2024" or "3/15/2024" with a year. "March 15" alone (no year) may not match: the regex is `([A-Z][a-z]+\s+\d{1,2},?\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4})`. The `\d{4}` year is mandatory. **START DATE NOT EXTRACTED.**
- `role`: "general"
- `level`: "mid"
- `location`: "remote"

**Missed:**
- Start date without year is not captured.

**Verdict:** PARTIAL PASS -- base salary correctly annualized from monthly, but start date missed due to mandatory year in regex.

---

### Case 7: "Compensation: $130,000-$150,000 depending on experience"

**Extracted:**
- `base_salary`: None of the base_salary patterns match "Compensation:" -- pattern 0 requires "base salary/compensation/pay" but actually, re-reading pattern 0: `base\s+(?:salary|compensation|pay)|annual\s+(?:salary|compensation)`. It requires "base" or "annual" as a prefix. Bare "Compensation:" is not matched. Pattern 5 requires "salary". Patterns 1-4 need pay-period suffixes. **Not matched by any pattern.**
- Actually, wait -- re-examining: the word "Compensation" does appear. Pattern 0's alternation is `base\s+(?:salary|compensation|pay)|annual\s+(?:salary|compensation)`. Neither fires because "Compensation:" is standalone, not preceded by "base" or "annual".
- `role`: "general"
- `level`: "mid"
- `location`: "remote"

**Missed:**
- Salary range format (`$X-$Y`) not handled at all. The parser cannot represent ranges -- it has a single `base_salary` float field.
- "Compensation:" as a standalone keyword not recognized.

**Verdict:** FAIL -- extracts nothing from a salary range format.

---

### Case 8: "Total package worth approximately $300K including benefits"

**Extracted:**
- `base_salary`: No pattern matches "Total package worth" as a salary trigger. "approximately" is not a recognized prefix. **NOT EXTRACTED.**
- `equity`: The equity patterns look for "equity|stock|RSU" keywords. Not present. **NOT EXTRACTED.**
- `role`: "general"
- `level`: "mid"
- `location`: "remote"

**Missed:**
- Total compensation / total package concept not supported. The $300K is a package value, not decomposed.
- This is arguably correct behavior -- the parser should not guess how to decompose a total package. But it should at minimum flag that a dollar amount was detected but unclassifiable.

**Verdict:** EXPECTED FAIL -- vague input, but parser gives no signal that it found monetary values it could not classify.

---

### Case 9: FAANG-style -- "Base: $185,000. Sign-on: Year 1 $50,000, Year 2 $30,000. RSU: 150 shares vesting over 4 years. Target bonus: 15%."

**Extracted:**
- `base_salary`: "Base: $185,000" -- same bare "Base:" problem as Cases 2 and 5. **However**, pattern 5 is `salary\s*(?:of|is|will\s+be|:)\s*CURRENCY`. No "salary" keyword present. What about pattern 1? `CURRENCY per year` -- no "per year". **NOT EXTRACTED.** The $185,000 base salary is lost.
- `signing_bonus`: Pattern is `sign(?:ing|[\s-]*on)\s+bonus\s*(?:of|is|:)?\s*CURRENCY`. Input has "Sign-on:" without "bonus" after it. The text says "Sign-on: Year 1 $50,000" -- the pattern expects "sign-on bonus", but the input uses "Sign-on:" alone. **NOT EXTRACTED.**
- `equity`: RSU pattern matches "RSU: 150 shares" via pattern `(\d[\d,]*)\s*(?:shares|options|rsus|units)`. Extracts `equity_shares: 150` into `other_components`. No dollar value computed (correct -- needs stock price). **PARTIALLY EXTRACTED.**
- `bonus_pct`: "Target bonus: 15%" -- pattern `(?:target|annual|yearly)\s+bonus\s*(?:of|is|:)?\s*(PERCENT)`. Matches. **15.0 EXTRACTED.** CORRECT.
- `role`: "general"
- `level`: "mid"
- `location`: "remote"

**Missed:**
- Base salary ($185,000) -- the "Base:" shorthand gap again.
- Sign-on bonus ($50,000 Year 1, $30,000 Year 2) -- "Sign-on:" without "bonus" not matched. Also, multi-year sign-on structure (Year 1 vs Year 2) cannot be represented.
- RSU share count captured but dollar value cannot be computed without stock price.

**Verdict:** FAIL -- only captures bonus percentage and share count from a 4-component FAANG offer.

---

### Case 10: Startup offer -- "Salary: $120K. Equity: 0.15% (10,000 shares at current 409A of $2.50). No signing bonus."

**Extracted:**
- `base_salary`: Pattern 5 matches "Salary:... $120K". `salary\s*(?:of|is|will\s+be|:)\s*CURRENCY`. "Salary: $120K" matches. `_parse_currency("$120K")` returns 120000.0. **$120,000 EXTRACTED.** CORRECT.
- `equity`: Equity patterns search for "equity... CURRENCY". Input has "Equity: 0.15%". The 0.15% is not a dollar value. Pattern 2 (`(\d[\d,]*)\s*shares`) matches "10,000 shares". **equity_shares: 10000** stored in other_components. The $2.50 409A valuation is not captured, nor is the implied total value ($25,000).
- `signing_bonus`: "No signing bonus" -- the pattern `sign(?:ing|[\s-]*on)\s+bonus\s*(?:of|is|:)?\s*CURRENCY` requires a dollar amount. "No signing bonus" has no amount. **NOT EXTRACTED** (arguably correct -- it's explicitly absent).
- `bonus_pct`: No bonus mentioned. **NOT EXTRACTED** (correct).
- `role`: "general"
- `level`: "mid"
- `location`: "remote"

**Missed:**
- Equity percentage (0.15%) not captured -- no pattern for `X%` equity ownership.
- 409A valuation ($2.50/share) not captured -- could compute total grant value ($25,000).
- The explicit "No signing bonus" is not recorded as a structured negative signal.

**Verdict:** PARTIAL PASS -- gets base salary right, captures share count, but misses equity valuation and ownership percentage.

---

## Adversarial Input Analysis

### ADV-1: "$$$$$"
- `_parse_currency` would receive `$$$$$` if a pattern matched. But no pattern matches bare dollar signs without digits. The `_CURRENCY_OR_K` regex requires `\d` after `$`.
- **Result:** Empty parse (role/level/location defaults only). No crash.

### ADV-2: "salary: -50000"
- Pattern 5 regex: `salary\s*(?:of|is|will\s+be|:)\s*CURRENCY_OR_K`. The `_CURRENCY_OR_K` pattern is `(?:\$[\d,]+[kK]|\$?[\d,]+[kK]|\$[\d,]+(?:\.\d{2})?)`. None of the branches handle a leading `-`. The `-` character blocks the match.
- **Result:** Empty parse. No crash. **But:** if this value somehow reached `analyze_offer()`, the bounds check (`SALARY_MIN = 1`) would reject it with a `ValueError`.

### ADV-3: "salary: 99999999999999"
- Same as ADV-2 -- `_CURRENCY_OR_K` requires either `$` prefix or `K/k` suffix. Plain `99999999999999` does not match any branch.
- **Result:** Empty parse. If it somehow reached `analyze_offer()`, the bounds check (`SALARY_MAX = 10_000_000`) would reject it.
- **Note:** `_parse_currency("$99999999999999")` would produce `99999999999999.0` -- no overflow (Python floats handle this). But the regex won't match without `$`.

### ADV-4: Empty string ""
- All regex searches return `None`. `_infer_role("")` returns "general". `_infer_level("")` returns "mid".
- **Result:** `{"role": "general", "level": "mid", "location": "remote"}`. No crash.

### ADV-5: Only whitespace
- Same behavior as empty string. No crash.

### ADV-6: HTML injection -- `<script>alert(1)</script> salary: $100,000`
- Pattern 5 matches "salary: $100,000" through the HTML tags.
- **Result:** `base_salary: 100000.0`. The HTML is ignored by the regex. No XSS risk at the parser layer (it returns data, not HTML). Downstream rendering would need to sanitize.

### ADV-7: Unicode currency (yen symbol)
- Same as Case 4 (euro). Non-`$` currency symbols are not matched. **Result:** Empty parse.

### ADV-8: Very long input (100KB+)
- Regex `.search()` on a ~100KB string. The patterns are not pathological (no nested quantifiers). Performance should be fine -- Python's `re` module handles linear scans well.
- **Result:** Correctly parses `salary of $100,000` from the beginning. No crash or hang.

### ADV-9: Regex bomb attempt -- "$" followed by 500 comma-separated "000" groups
- Constructs something like `salary: $000,000,000,...,000`. The `_CURRENCY_OR_K` regex `\$[\d,]+` would match the entire thing. `_parse_currency` strips `$` and `,`, producing `float("000000...000")` = 0.0.
- If this reached `analyze_offer()`, the bounds check catches `0 < SALARY_MIN`. No crash, but the parsed value is nonsensical (0.0).

### ADV-10: Null bytes -- "salary:\x00 $150,000"
- Python regex treats `\x00` as a character. The `\s*` between "salary:" and the currency may or may not match `\x00`. In Python's `re`, `\s` matches `[ \t\n\r\f\v]` but NOT `\x00`. So pattern 5 would try to match `salary:\x00` where the `(?:of|is|will\s+be|:)\s*` part matches `:` but then `\x00` blocks the currency match (it's not `$`).
- **Result:** Depends on exact regex engine behavior. Likely fails to match, returning empty parse. No crash.

---

## Summary of Bugs and Gaps

### Critical (breaks common inputs)

| ID | Issue | Affected Cases | Fix Complexity |
|----|-------|---------------|----------------|
| C1 | **Bare "Base:" not matched** -- `base_salary` patterns require "base salary", "base compensation", or "base pay" but real offers often use just "Base:" | Cases 2, 5, 9 | Low -- add pattern: `base\s*:\s*CURRENCY` |
| C2 | **No hourly rate support** -- `$X/hour` is parsed as `$X` annual | Case 3 | Medium -- add pattern + 2080x multiplier |
| C3 | **"Sign-on:" without "bonus"** not matched | Case 9 | Low -- relax signing_bonus pattern to allow "sign-on:" alone |

### High (misses significant data)

| ID | Issue | Affected Cases | Fix Complexity |
|----|-------|---------------|----------------|
| H1 | **No salary range support** -- `$X-$Y` format produces no output | Case 7 | Medium -- new pattern, decide on midpoint vs low/high storage |
| H2 | **No non-USD currency support** -- EUR, GBP, etc. silently dropped | Case 4 | Medium -- extend `_CURRENCY_OR_K` or add parallel patterns |
| H3 | **"Compensation:" standalone** not recognized as salary keyword | Case 7 | Low -- add to pattern 0's alternation |
| H4 | **Equity as ownership percentage** (0.15%, 0.5%) not captured | Cases 5, 10 | Medium -- new field `equity_pct` |
| H5 | **OTE (On-Target Earnings)** not recognized | Case 5 | Low -- add pattern |
| H6 | **Multi-year sign-on** (Year 1, Year 2) cannot be represented | Case 9 | High -- data model change needed |
| H7 | **409A valuation** not extracted for equity dollar computation | Case 10 | Medium -- pattern + share_count x price calculation |

### Low (edge cases)

| ID | Issue | Affected Cases | Fix Complexity |
|----|-------|---------------|----------------|
| L1 | **Start date without year** not captured | Case 6 | Low -- make year optional in regex |
| L2 | **"No signing bonus"** not recorded as explicit absence | Case 10 | Low -- detect negation patterns |
| L3 | **Total package / total comp** gives zero signal | Case 8 | Medium -- new "unclassified_amounts" list |
| L4 | **"Salary:" lowercase in "Salary: $120K"** -- pattern 5 is case-insensitive so this works, but the capitalization variant is worth noting as tested | Case 10 | N/A -- works correctly |

### Robustness (adversarial)

| ID | Finding | Severity |
|----|---------|----------|
| R1 | No crashes on any adversarial input tested | Good |
| R2 | Bounds checking in `analyze_offer()` catches extreme values | Good |
| R3 | No ReDoS vulnerability detected (patterns are linear) | Good |
| R4 | Null bytes silently break matching rather than crashing | Acceptable |
| R5 | HTML/script injection passes through (no sanitization) | N/A at parser layer -- downstream concern |
| R6 | Regex bomb via long comma-separated numbers produces 0.0 rather than a meaningful error | Low risk |

---

## Parser Success Rate

| Case | Base Salary | Signing Bonus | Equity | Bonus % | Other | Overall |
|------|-------------|---------------|--------|---------|-------|---------|
| 1    | PASS        | n/a           | n/a    | n/a     | --    | PASS    |
| 2    | **FAIL**    | n/a           | PASS   | PASS    | --    | FAIL    |
| 3    | **WRONG**   | n/a           | n/a    | n/a     | --    | FAIL    |
| 4    | **FAIL**    | **FAIL**      | n/a    | n/a     | --    | FAIL    |
| 5    | **FAIL**    | n/a           | MISS   | n/a     | --    | FAIL    |
| 6    | PASS        | n/a           | n/a    | n/a     | MISS  | PARTIAL |
| 7    | **FAIL**    | n/a           | n/a    | n/a     | --    | FAIL    |
| 8    | **FAIL**    | n/a           | n/a    | n/a     | --    | FAIL    |
| 9    | **FAIL**    | **FAIL**      | PARTIAL| PASS    | --    | FAIL    |
| 10   | PASS        | n/a           | PARTIAL| n/a     | --    | PARTIAL |

**Overall: 1 full pass, 2 partial passes, 7 failures out of 10 test cases.**

Base salary extraction -- the single most important field -- succeeds on only 3 of 10 inputs (Cases 1, 6, 10). Case 3 extracts a wrong value ($85 instead of ~$176,800).

---

## Recommended Fixes (Priority Order)

1. **Add bare "Base:" pattern** to `_PATTERNS["base_salary"]`: `re.compile(r"base\s*:\s*CURRENCY_OR_K", re.IGNORECASE)`. Fixes Cases 2, 5, 9.

2. **Add hourly rate pattern** with 2080x annual multiplier: `re.compile(r"CURRENCY_OR_K\s*/\s*(?:hour|hr)\b", re.IGNORECASE)` at index 5+ with `_PAY_PERIOD_MULTIPLIERS` entry of `2080.0`. Fixes Case 3.

3. **Relax sign-on pattern** to match "sign-on:" without requiring "bonus": `sign(?:ing|[\s-]*on)\s*(?:bonus)?\s*(?:of|is|:)?\s*CURRENCY`. Fixes Case 9 partially.

4. **Add "Compensation:" as standalone salary keyword** in pattern 0. Fixes Case 7 partially (still needs range support).

5. **Add salary range pattern** that captures low and high values. Requires a data model change to support `base_salary_low` / `base_salary_high` or a `salary_range` tuple.

6. **Add EUR/GBP currency support** or at minimum detect and warn. Requires extending `_CURRENCY_OR_K` to `(?:[$\u20ac\u00a3])` and flagging non-USD.

7. **Add equity percentage pattern** for startup-style offers (`X%` equity/ownership).

8. **Make start_date year optional** in the regex.
