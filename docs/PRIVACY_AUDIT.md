# DealSim Privacy & GDPR Compliance Audit

**Date:** 2026-03-19
**Scope:** Full application — backend (`src/dealsim_mvp/`), frontend (`static/index.html`), data storage layer
**Deployment target:** UpCloud Frankfurt (EU)

---

## 1. Personal Data Inventory

### 1.1 Email addresses (feedback form)
- **Where:** `feedback.py` stores optional email in `data/feedback.jsonl` (field: `"email"`).
- **Collection point:** Feedback form in `index.html` line 554 — `<input id="feedback-email" type="email" placeholder="Email for updates (optional)">`.
- **Severity:** MEDIUM. Email is personal data under GDPR Art. 4(1). Collection is optional and user-initiated, which is good. However:
  - No explicit consent checkbox or privacy notice accompanies the field.
  - No indication of what "updates" means, how long the email is retained, or who processes it.
  - The placeholder text "Email for updates (optional)" implies a mailing list but no mechanism for that exists.

### 1.2 IP addresses (rate limiter)
- **Where:** `app.py` lines 43-70. `_rate_store` is an in-memory `dict[str, list[float]]` mapping client IPs to request timestamps.
- **Retention:** In-memory only. Evicted after 60 seconds of inactivity (line 56). Never written to disk.
- **Severity:** LOW. IP addresses are personal data under GDPR (CJEU Breyer ruling, C-582/14). However, this is a legitimate interest use case (security/abuse prevention, Art. 6(1)(f)) with minimal retention. No persistent logging of IPs was found.

### 1.3 Negotiation session content
- **Where:** `core/store.py` persists sessions to `.dealsim_sessions.json`. `core/simulator.py` defines `NegotiationState` containing full transcript (`Turn` objects with `text` field — the user's actual typed messages).
- **Retention:** Auto-cleaned after 1 hour (`_MAX_AGE_SECONDS = 3600`, line 31).
- **Severity:** MEDIUM. User-typed negotiation messages could contain personal data (salary figures, company names, role details). The `CreateSessionRequest` also accepts a free-text `context` field (max 500 chars) where users describe their situation.
- **Positive:** 1-hour auto-cleanup is good data minimization practice.

### 1.4 Analytics events
- **Where:** `analytics.py` stores events in `data/events.jsonl`.
- **Content:** Event type, UTC timestamp, properties dict (scenario type, scores, feature names).
- **Severity:** LOW. The docstring explicitly states "No cookies, no PII, no third-party services." Events contain no user identifiers — no session ID linkage, no IP, no email. Events are aggregate behavioral data (e.g., "session_created with scenario_type=salary").

### 1.5 User-pasted email/message content (Negotiation Audit tool)
- **Where:** Frontend sends to `/api/tools/audit-email` with field `email_text`. Processed by `core/email_audit.py` (regex-based, no LLM).
- **Severity:** HIGH. Users paste real emails and message threads. This content likely contains names, email addresses, salary figures, and other PII belonging to third parties. The content is processed server-side. No evidence it is persisted to disk (good), but it passes through server memory and could appear in application logs if `LOG_LEVEL=DEBUG`.

### 1.6 localStorage data (client-side)
- **Where:** `index.html` uses three `localStorage` keys:
  - `dealsim_session_count` — integer counter of completed sessions
  - `dealsim_scores` — JSON array of past scores
  - `dealsim_last_challenge` — date string of last daily challenge
- **Severity:** LOW. No PII stored. All data is aggregate scores and counts. However, localStorage persists indefinitely and has no expiry mechanism. Under ePrivacy Directive Art. 5(3), storing data on the user's device requires consent unless "strictly necessary."

---

## 2. Missing Privacy Infrastructure

### 2.1 No privacy policy
**CRITICAL.** No privacy policy exists anywhere in the application. GDPR Art. 13 requires informing data subjects at the point of collection about:
- Identity of the controller
- Purpose of processing
- Legal basis
- Retention periods
- Rights (access, rectification, erasure, portability, objection)
- Right to lodge a complaint with a supervisory authority

**Action required:** Draft and publish a privacy policy. Link it from the footer and near the email input field.

### 2.2 No cookie/storage banner
**HIGH.** The application uses `localStorage` (3 keys) and loads two external resources that may set cookies:
- `https://cdn.tailwindcss.com` — CDN JavaScript
- `https://fonts.googleapis.com` — Google Fonts

Under the ePrivacy Directive (implemented as TTDSG in Germany), consent is required for non-essential storage. The localStorage keys (`dealsim_session_count`, `dealsim_scores`, `dealsim_last_challenge`) are functional but arguably not "strictly necessary" for the service the user explicitly requested.

Google Fonts is a known GDPR concern — the Munich Regional Court (Case 3 O 17493/20, Jan 2022) ruled that loading Google Fonts from Google's CDN transmits the user's IP address to Google (a US company), constituting an unauthorized data transfer. Self-hosting the font files eliminates this risk entirely.

**Action required:** Either (a) add a cookie consent banner, or (b) self-host all external resources and justify localStorage as strictly necessary, removing the consent requirement.

### 2.3 No consent mechanism for email collection
**MEDIUM.** The feedback email field has no:
- Checkbox for explicit consent
- Link to privacy policy
- Explanation of what "updates" means
- Opt-in mechanism that satisfies GDPR Art. 7 (conditions for consent)

---

## 3. Analytics Anonymization Assessment

**Status: GOOD with caveats.**

- Analytics events (`events.jsonl`) contain no user identifiers. No session IDs, no IPs, no emails.
- Events cannot be linked to individuals through the analytics data alone.
- The `properties` dict contains scenario types and scores — aggregate, non-identifying data.
- No third-party analytics services (no Google Analytics, no Mixpanel, no tracking pixels).
- No fingerprinting or cross-session tracking in the analytics layer.

**Caveat:** The `feedback.jsonl` file contains `session_id` alongside optional `email`. If a user provides their email, their feedback can be linked to a specific negotiation session. If session transcripts were retained longer (currently 1 hour), this would create a linkable chain: email -> session_id -> full transcript. The 1-hour session cleanup mitigates this, but a brief window of linkability exists.

---

## 4. Feedback Data Security

### 4.1 Storage
- Feedback is stored in `data/feedback.jsonl` — a plain-text JSONL file on the server filesystem.
- No encryption at rest.
- No access controls beyond filesystem permissions (inherited from the process user).
- The `get_all()` method (line 111) returns ALL feedback records including emails — exposed via the admin dashboard with no authentication.

### 4.2 File permissions
- No explicit permission setting in the code. `_ensure_dir()` creates the directory with default permissions.
- On Linux/UpCloud deployment, file permissions depend on the umask of the running process.
- **Action required:** Set explicit restrictive permissions (e.g., `0o600`) on `feedback.jsonl`. Ensure the admin dashboard endpoint is authentication-protected.

### 4.3 Data in transit
- Depends on deployment configuration. If HTTPS is configured at the reverse proxy (expected for UpCloud), data is encrypted in transit.
- The CORS configuration defaults to localhost only if `DEALSIM_CORS_ORIGINS` is not set, which is safe.

---

## 5. Right to Erasure (GDPR Art. 17)

**Status: NOT IMPLEMENTED.**

There is no mechanism for a user to:
- View what data has been collected about them
- Request deletion of their feedback (including email)
- Request deletion of their session data
- Export their data (Art. 20 portability)

The only "delete" operations in the codebase are file rotation (deleting old rotated log files when they exceed 3 copies) and session auto-cleanup (1-hour expiry).

**Action required:**
1. Implement a data deletion endpoint or provide a contact email for erasure requests.
2. Since feedback records contain optional emails, you must be able to find and delete all records associated with a given email address.
3. Document the process in the privacy policy.

---

## 6. Data Minimization Assessment

**Status: MOSTLY GOOD.**

| Data point | Necessary? | Assessment |
|---|---|---|
| Star rating (1-5) | Yes | Core feedback metric |
| Comment text (max 1000 chars) | Yes | Qualitative feedback |
| Email (optional) | Questionable | No mailing list exists; no follow-up mechanism implemented. Collecting email with no use case violates data minimization (Art. 5(1)(c)). Either implement the "updates" feature or remove the field. |
| Session ID in feedback | Yes | Links feedback to context |
| Final score in feedback | Yes | Contextualizes the rating |
| Scenario type in feedback | Yes | Contextualizes the rating |
| IP in rate limiter | Yes | Security necessity |
| localStorage session count | Marginal | Used only to trigger feedback modal after 2nd session. Could be replaced with a session-scoped flag. |
| localStorage scores | Marginal | Score history for the user. Useful feature but persists indefinitely. |
| User-typed negotiation text | Yes | Core service functionality |
| User-pasted email text (audit) | Yes | Core service functionality, not persisted |

**Key concern:** The email field in the feedback form collects data with no corresponding processing purpose. Either build the "updates" feature or remove the field.

---

## 7. Cross-Border Data Transfers

### 7.1 Server location
UpCloud Frankfurt is within the EU. No issue for server-side data.

### 7.2 External resource loads (client-side)
Two external resources loaded in `index.html` trigger cross-border transfers:

| Resource | Provider | Data transferred | Risk |
|---|---|---|---|
| `cdn.tailwindcss.com` | Tailwind Labs (US) | User IP, User-Agent, Referer | MEDIUM — CDN may log requests |
| `fonts.googleapis.com` | Google (US) | User IP, User-Agent, Referer | HIGH — Munich court precedent; Google is a US entity subject to FISA 702 |

**Action required:**
1. **Self-host Google Fonts.** Download the Inter font files and serve them from the application's static directory. This eliminates the most legally risky transfer.
2. **Consider self-hosting Tailwind CSS.** Use the build-time Tailwind CLI instead of the CDN script. This also improves performance.

### 7.3 No other external calls
- No third-party analytics
- No LLM API calls (engine is rule-based)
- No external databases
- No CDN for application data

This is a strong privacy posture. The only transfers are the two CDN loads above.

---

## 8. Session Data Retention

**Status: GOOD.**

- Active sessions auto-expire after 1 hour (`_MAX_AGE_SECONDS = 3600` in `core/store.py`).
- Session data is cleaned on every `load_sessions()` call.
- Session store file (`.dealsim_sessions.json`) is written atomically via `os.replace()`.
- No session data leaks into analytics (analytics events contain no session IDs).

**Minor concern:** Feedback records (`feedback.jsonl`) reference `session_id` and are retained indefinitely (only rotated at 10MB). While the session itself is deleted after 1 hour, the feedback record persists. This is acceptable if the feedback serves a legitimate ongoing purpose, but the retention should be documented in the privacy policy.

**Analytics events** (`events.jsonl`) are also retained indefinitely with 10MB rotation. Since they contain no PII, this is acceptable, but a defined retention period (e.g., 12 months) would strengthen the data minimization posture.

---

## 9. Feedback Form Transparency

**Status: INSUFFICIENT.**

The feedback form (lines 540-568 of `index.html`):
- Labels the email field as "Email for updates (optional)" — implies a purpose but does not explain it.
- No privacy notice or link to privacy policy.
- No indication of how long the data is stored.
- No indication of who processes the data.
- The "Thank you" message says "This helps us improve DealSim" — no mention of what happens with the email specifically.

**Action required:** Add a brief privacy notice near the email field, e.g.: "Your email will only be used to notify you about DealSim updates. We store it on our EU server and you can request deletion at any time. See our Privacy Policy."

---

## 10. Cookie and localStorage Consent

**Status: NO CONSENT MECHANISM EXISTS.**

### localStorage usage (3 keys):
| Key | Purpose | Strictly necessary? |
|---|---|---|
| `dealsim_session_count` | Trigger feedback modal after 2nd session | No — enhancement, not core service |
| `dealsim_scores` | Score history display | No — enhancement, not core service |
| `dealsim_last_challenge` | Daily challenge tracking | Arguable — part of the feature but user could function without it |

Under ePrivacy Directive Art. 5(3) / German TTDSG Section 25: storing information on the user's terminal equipment requires consent unless "strictly necessary for the provision of the service explicitly requested by the user."

These localStorage items enhance the experience but are not strictly necessary for the core negotiation simulation service.

### External scripts that may set cookies:
- Tailwind CDN and Google Fonts CDN may set cookies or access browser storage. This is outside the application's control.

**Action required:** Either:
1. Add a consent banner covering localStorage and external resource loading, OR
2. Self-host all external resources AND argue that localStorage keys are strictly necessary (weak argument for `dealsim_session_count`), OR
3. Move score history and session count to the server side, eliminating client-side storage entirely.

---

## Priority Action Items

| # | Action | Severity | Effort |
|---|---|---|---|
| 1 | Draft and publish a privacy policy | CRITICAL | Medium |
| 2 | Self-host Google Fonts (Inter) | HIGH | Low |
| 3 | Self-host Tailwind CSS (use build step) | HIGH | Low |
| 4 | Add privacy notice near feedback email field | HIGH | Low |
| 5 | Implement data deletion mechanism (Art. 17) | HIGH | Medium |
| 6 | Add cookie/localStorage consent banner OR eliminate non-essential storage | MEDIUM | Medium |
| 7 | Remove email field from feedback OR implement the "updates" feature | MEDIUM | Low |
| 8 | Set explicit file permissions on `feedback.jsonl` | MEDIUM | Low |
| 9 | Protect admin dashboard endpoint with authentication | MEDIUM | Medium |
| 10 | Define retention periods for `feedback.jsonl` and `events.jsonl` | LOW | Low |
| 11 | Ensure `LOG_LEVEL` is not set to `DEBUG` in production (could log pasted email content) | LOW | Low |
| 12 | Add `Referrer-Policy: no-referrer` header to prevent URL leakage to external CDNs | LOW | Low |

---

## Summary

DealSim has a genuinely privacy-respecting architecture at its core: no third-party analytics, no LLM API calls sending user data externally, no persistent IP logging, anonymous analytics events, and automatic session cleanup. The main gaps are procedural rather than architectural:

1. **No privacy policy** — the single most important missing piece for GDPR compliance.
2. **Google Fonts loaded from Google CDN** — a known legal risk in Germany after the Munich ruling.
3. **No data deletion mechanism** — Art. 17 right to erasure is not supported.
4. **Feedback email collected without clear purpose or consent** — data minimization concern.

Fixing items 1-4 from the priority list would bring the application to a reasonable compliance baseline for an EU deployment. The remaining items are hardening measures that reduce risk further.
