# GDPR Privacy Fixes — 2026-03-19

## Changes Made

### 1. Privacy Policy Page (`static/privacy.html`)
Created a full GDPR-compliant privacy policy covering:
- Data controller info (placeholder — fill before launch)
- What data is collected: session content, optional feedback email, analytics events, IP in logs
- Legal basis per data type (Art. 6(1)(a), (b), (f) GDPR)
- Storage method: server-side JSONL files with auto-rotation
- No cookies — only localStorage for score history (never leaves browser)
- No third-party sharing, no tracking pixels, no ad networks
- No cross-border font loading
- Server location: Frankfurt, Germany (UpCloud)
- Full GDPR rights list (access, erasure, portability, etc.)
- Contact email for data requests: privacy@dealsim.app
- Styled consistently with the main app (dark navy theme, Tailwind)

### 2. Google Fonts Removed (`static/index.html`)
- Removed `<link rel="preconnect" href="https://fonts.googleapis.com" />`
- Removed `<link href="https://fonts.googleapis.com/css2?family=Inter:...">` stylesheet
- Replaced Tailwind font config from `['Inter', 'system-ui', 'sans-serif']` to system font stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`
- Updated canvas font reference in JS chart code
- **Why:** Loading Google Fonts transmits the visitor's IP to Google servers in the US, which violates GDPR per German court rulings (LG Munich I, Jan 2022).

### 3. Privacy Link in Footer (`static/index.html`)
- Added a `<footer>` element before `</body>` with copyright and a "Privacy Policy" link pointing to `/privacy`.

### 4. Privacy Route (`src/dealsim_mvp/app.py`)
- Added `GET /privacy` route that serves `static/privacy.html` via `HTMLResponse`.
- Route is registered before the static file mount to ensure it takes priority.
- Returns 404 if the file is missing.

## Before Launch Checklist
- [ ] Replace `[Your Name / Company]` and `[Street Address]` in privacy.html with real data controller info
- [ ] Replace `privacy@dealsim.app` with the actual contact email (or set up that address)
- [ ] Verify log rotation schedule and update retention period in the policy if needed
- [ ] Consider adding a cookie-consent-style banner for localStorage disclosure (not legally required for non-tracking localStorage, but belt-and-suspenders)
