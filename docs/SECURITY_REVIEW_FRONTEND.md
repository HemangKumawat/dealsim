# DealSim Frontend Security Review

**Date:** 2026-03-19
**Scope:** `static/index.html` (2642 lines), `nginx/dealsim.conf`
**Reviewer:** Automated security audit

---

## Summary

The frontend is in solid shape for a pre-launch product. The developer has already implemented `escapeHtml()` and uses it consistently across dynamic content rendering. No critical vulnerabilities were found. The main gaps are a missing CSP header (known issue MF-3), Tailwind CDN without SRI, and minor hardening opportunities.

| Severity | Count |
|----------|-------|
| Critical | 0     |
| High     | 1     |
| Medium   | 3     |
| Low      | 4     |

---

## Findings

### HIGH-1: Missing Content Security Policy Header

**Severity:** High
**Location:** `nginx/dealsim.conf` (known issue MF-3)
**Status:** Known gap, not yet fixed

The nginx config has no `Content-Security-Policy` header. This is the single most important missing defense. Without CSP, any XSS that bypasses `escapeHtml()` has full DOM access and can exfiltrate data or hijack sessions.

**Risk:** If any future code path introduces innerHTML without escaping (or a dependency is compromised), there is no second line of defense.

**Fix:** Add to the HTTPS server block in `dealsim.conf`:

```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self';" always;
```

Note: `'unsafe-inline'` is required because all JS is inline in `index.html`. Migrating JS to an external file with a hash or nonce would allow removing `'unsafe-inline'` for a stronger policy.

---

### MEDIUM-1: Tailwind CDN Without Subresource Integrity (SRI)

**Severity:** Medium
**Location:** Line 7: `<script src="https://cdn.tailwindcss.com"></script>`

The Tailwind CSS CDN script loads without an `integrity` attribute. If the CDN is compromised or serves a modified file (supply chain attack, DNS hijack), arbitrary JavaScript executes in the user's browser with full page access.

**Risk:** Supply chain attack vector. The CDN build of Tailwind (`cdn.tailwindcss.com`) is a JIT compiler that runs JS, not just CSS. A compromised version could steal form input, session IDs, or redirect users.

**Fix (short-term):** Add SRI hash:
```html
<script src="https://cdn.tailwindcss.com"
  integrity="sha384-<hash>"
  crossorigin="anonymous"></script>
```

**Fix (long-term, recommended):** Bundle Tailwind at build time and serve from your own origin. This eliminates the CDN dependency entirely and enables a stricter CSP without the CDN allowlisted.

---

### MEDIUM-2: innerHTML Usage in Scorecard/Debrief Renderers

**Severity:** Medium
**Location:** Lines 1593-1609 (renderScorecard), 2033-2072 (analyzeOffer), 2131-2167 (runAudit), 2215-2261 (showDebrief), 2316-2337 (generatePlaybook)

Multiple functions build HTML strings and assign via `innerHTML`. The code consistently uses `escapeHtml()` on all dynamic data values, which is correct. However, the pattern is fragile:

- The scorecard dimension bar renderer (line 1607) builds complex HTML with string concatenation, passing values through `escapeHtml()`. Any future edit that misses an escape will introduce stored XSS (since the data comes from the API/AI opponent).
- The debrief renderer (lines 2215-2261) also uses `escapeHtml()` on all interpolated fields.
- The offer analyzer and audit results use the same pattern.

**Current status:** No active XSS found. All user-facing and API-returned data passes through `escapeHtml()`.

**Risk:** The opponent AI's responses are rendered via `bubble.textContent = text` in `appendBubble()` (line 1512) and `appendDemoBubble()` (line 1973), which is safe. But debrief data (`opponent_pressure`, `hidden_constraints`, `key_moments`, `best_move`, `biggest_mistake`, `move_analysis`) is rendered via innerHTML with escaping. If a developer later removes or forgets the escape, the AI response could inject HTML/JS.

**Fix:** Consider switching to DOM API (createElement/textContent) for all dynamic content, or add a code review checklist item: "Every innerHTML assignment must wrap dynamic values in escapeHtml()."

---

### MEDIUM-3: No CSRF Protection on API Calls

**Severity:** Medium
**Location:** All `fetch()` calls throughout the file

All API calls use `fetch()` with `Content-Type: application/json` but no CSRF token. The JSON content type provides partial implicit protection (browsers won't send JSON via form submission), but:

- `fetch()` from a malicious page on a different origin would be blocked by CORS (assuming the backend does not set `Access-Control-Allow-Origin: *`).
- If CORS is misconfigured on the backend, a cross-origin attacker could start sessions, send messages, or submit feedback on behalf of a logged-in user.

**Risk:** Low in current architecture (no authentication, no user accounts), but becomes meaningful if authentication is ever added.

**Fix:** Verify the backend does not set `Access-Control-Allow-Origin: *`. When authentication is added, implement CSRF tokens or use `SameSite=Strict` cookies.

---

### LOW-1: localStorage Data Exposure

**Severity:** Low
**Location:** Lines 1639-1640, 2402-2414, 2557-2579

Data stored in localStorage:
- `dealsim_session_count` (integer)
- `dealsim_scores` (array of score objects: date, score, outcome, scenario)
- `dealsim_last_challenge` (date string)

**Assessment:** No sensitive data is stored. Scores and session counts are not personally identifiable. The email field from the feedback form is sent directly to the API and never stored locally.

**Risk:** Minimal. An XSS attack could read localStorage, but the data has negligible value. The 50-entry cap on score history (line 2413) is a good practice.

**No fix needed.** Current usage is appropriate.

---

### LOW-2: No Clickjacking Protection in HTML

**Severity:** Low
**Location:** `index.html` (no `<meta>` frame protection)

The HTML itself has no frame-busting code. However, the nginx config includes `X-Frame-Options: SAMEORIGIN` (line 57), which is the correct server-side mitigation. The CSP `frame-ancestors 'self'` directive (proposed in HIGH-1 fix) would add a modern equivalent.

**Risk:** Mitigated by nginx header. If the page is ever served without nginx (dev server, CDN direct), it would be frameable.

**Fix (defense in depth):** Add to `<head>`:
```html
<meta http-equiv="X-Frame-Options" content="SAMEORIGIN">
```

---

### LOW-3: Email Field Sent Without Validation

**Severity:** Low
**Location:** Line 559 (feedback-email input), line 1683 (submitFeedback)

The feedback email field (`feedback-email`) has `type="email"` for browser validation, but the form uses `novalidate` on the parent (though the feedback form is not inside the `novalidate` form). The email is sent to `/api/feedback` without client-side format validation.

**Risk:** Invalid or malicious email strings reach the backend. The backend should validate, but client-side validation is a useful first filter.

**Fix:** Add explicit validation before submission:
```javascript
const email = document.getElementById('feedback-email').value.trim();
if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
  // show error
  return;
}
```

---

### LOW-4: API Key / Secret Exposure Check

**Severity:** Low (no issue found)
**Location:** Entire `index.html`

**Assessment:** No API keys, tokens, admin keys, or secrets are present in the frontend code. All API calls go to relative URLs (`/api/...`), meaning the backend handles authentication with any AI providers (OpenAI, Anthropic, etc.) server-side. The `state` object contains only session IDs and UI state.

**No fix needed.** This is correctly implemented.

---

## Nginx Configuration Review

### What is done well

1. **SSL hardening:** TLSv1.2+, strong cipher suite, OCSP stapling, session tickets disabled. This is production-grade.
2. **Security headers:** HSTS with preload, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy. All present and correct.
3. **Rate limiting:** Two zones (`api_general` with burst=20, `api_auth` with burst=10). The `/api/` path has stricter limits than the general path.
4. **Request size limits:** `client_max_body_size 1m` prevents large payload abuse.
5. **Scanner blocking:** Common attack paths (`.env`, `.git`, `wp-admin`, `phpmyadmin`) return 444 (connection drop).
6. **HTTP to HTTPS redirect:** Correctly configured with ACME challenge pass-through.
7. **HTTP/2 enabled.**

### Gaps

| Issue | Detail | Severity |
|-------|--------|----------|
| No CSP header | See HIGH-1 above | High |
| Rate limit zones defined externally | The `limit_req_zone` directives are not in this file (must be in `nginx.conf` or included conf). Verify they exist. | Info |
| WebSocket timeout | `/ws` has `proxy_read_timeout 86400` (24h). This is fine for WebSocket keepalive but verify no resource exhaustion risk with many idle connections. | Low |
| No `add_header` on static files | If static files are served through the `location /` block, they inherit all headers including HSTS. This is correct behavior. | Info |

---

## Content Injection Assessment

**Question:** Could opponent AI responses contain HTML/JS that gets rendered unsafely?

**Answer:** No, in the current code. The two primary rendering paths for opponent text are:

1. **Chat bubbles** (`appendBubble`, line 1512): Uses `bubble.textContent = text` -- safe, no HTML parsing.
2. **Demo chat bubbles** (`appendDemoBubble`, line 1973): Uses `bubble.textContent = text` -- safe.
3. **Debrief data** (lines 2215-2261): Uses `innerHTML` but wraps all API values in `escapeHtml()` -- safe as long as escaping is maintained.
4. **System messages** (`appendSystemMsg`, line 1541): Uses `el.textContent = text` -- safe.

The `escapeHtml()` implementation (line 1164-1168) uses the standard `div.textContent`/`div.innerHTML` technique, which correctly escapes `<`, `>`, `&`, `"`, and `'`.

---

## Recommendations Priority

1. **Add CSP header** to nginx (HIGH-1) -- strongest single improvement
2. **Add SRI to Tailwind CDN** or bundle locally (MEDIUM-1)
3. **Verify CORS policy** on backend to confirm CSRF mitigation (MEDIUM-3)
4. Consider migrating innerHTML patterns to DOM API for future-proofing (MEDIUM-2)
5. Add frame-busting meta tag for defense in depth (LOW-2)
6. Add client-side email validation (LOW-3)
