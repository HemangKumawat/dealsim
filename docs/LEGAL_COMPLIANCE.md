# DealSim Legal and Compliance Report
### AI-Powered Negotiation Practice App — Developer Based in Munster, Germany
### Research Date: March 2026

---

## Executive Summary

DealSim faces a tractable compliance stack for a solo German developer. None of the requirements are exotic or prohibitively expensive. The highest-risk items before launch are GDPR fundamentals, the Impressum, and CDN localization (already in progress). The EU AI Act adds obligations but the hard deadline is August 2026 — after typical MVP timelines. Payment compliance is largely delegated to Stripe. Business registration is the only item that must happen before the first euro is invoiced.

---

## 1. GDPR Compliance

### What Data DealSim Collects

- Chat transcripts (may contain names, negotiation positions, personal context)
- Behavioral metadata (session duration, scores, timestamps)
- Account credentials (email address, hashed password)
- Technical data (IP addresses, browser fingerprint via session cookies)

IP addresses are definitively personal data under German law (LG Munchen, January 2022).

The Tailwind CDN replacement already identified is the right call. The same principle applies to any third-party resource loaded from a non-EU server at page render time.

### Legal Basis for Processing (Article 6)

| Processing Activity | Legal Basis |
|---|---|
| Account & session data for service delivery | Art. 6(1)(b) — contract performance |
| Analytics beyond strictly necessary | Art. 6(1)(a) — consent (opt-in required) |
| Marketing emails | Art. 6(1)(a) — explicit consent |
| AI model inference (LLM API calls) | Third-party processor — requires DPA |

### Privacy Policy Requirements

Must be in German, reachable from every page in one click, covering:

1. Identity and contact details of data controller (full name and address)
2. DPO contact (not required for one-person operation at MVP)
3. Per processing activity: what data, legal basis, retention period, EU transfer mechanisms
4. Third-party processors list: LLM API provider, hosting provider, Stripe, analytics
5. User rights: access (Art. 15), rectification (Art. 16), erasure (Art. 17), restriction (Art. 18), portability (Art. 20), objection (Art. 21)
6. Right to lodge complaint with LfDI NRW (supervisory authority for Munster)

### Data Retention Defaults

| Data Type | Retention Period |
|---|---|
| Chat transcripts | 90 days after session, or upon account deletion |
| Account data | While active, delete within 30 days of deletion request |
| Payment records | 10 years (§257 HGB) — Stripe retains on your behalf |
| Server logs with IPs | 7 days (defensible industry standard) |

### Right to Deletion (Art. 17)

- Account deletion button in user settings (must actually delete data)
- Anonymization acceptable for aggregate analytics
- Respond within 30 days
- Request deletion from sub-processors (LLM provider) as needed
- Log all deletion requests

### Cookie Consent

- Strictly necessary cookies (session auth, CSRF): no consent required
- Analytics, A/B testing, marketing: consent required before setting
- "Reject All" must be as prominent as "Accept All"
- If MVP uses only session cookies: can launch without a consent banner

---

## 2. Impressum Requirements (DDG §5)

Moved from TMG to DDG (Digitale-Dienste-Gesetz) on May 14, 2024.

### Required Fields (Natural Person / Freelancer)

1. Full legal name (first and last)
2. Full street address (PO box not sufficient)
3. Direct email address (contact form alone insufficient)
4. Telephone number (recommended, not strictly mandatory under DDG)
5. USt-IdNr. if VAT-registered
6. If Kleinunternehmer: no VAT ID needed

### Not Needed at Solo Scale

- Supervisory authority (only for regulated professions)
- Commercial register number (only for GmbH, UG, AG)
- W-IdNr. (mandatory from December 2026)

### Placement

Link labeled "Impressum" accessible from every page within two clicks. Footer placement is standard.

### Risk

Fines up to EUR 50,000. Professional Abmahnung firms actively scan for missing Impressums.

---

## 3. Terms of Service

Not legally mandatory, but strongly advisable. Without ToS, default BGB applies (more user-favorable).

### Key Clauses for DealSim

**AI Disclaimer (most important):** DealSim is an educational simulation tool. It does not provide professional negotiation, legal, or business advice. AI responses are simulated counterparts for practice only.

**Liability Limitation:** Cannot exclude liability for gross negligence, willful misconduct, or personal injury under German law. Can limit for simple negligence to foreseeable typical damage.

**User Content License:** Users retain ownership of inputs. Grant DealSim non-exclusive license to process for service delivery. State explicitly if chat data is NOT used for training.

**AI Content Clause:** AI responses are auto-generated, may contain inaccuracies, do not represent DealSim's views.

**Acceptable Use:** No training data extraction, system prompt probing, harassment, resale.

**Governing Law:** German law, courts of Munster.

**EU ODR Platform:** Platform shuts down July 20, 2025 — remove any such link after that date.

**Language:** German version must be legally authoritative.

---

## 4. AI-Specific Regulations

### EU AI Act Classification: Limited Risk

DealSim is NOT high-risk. High-risk education AI targets automated exam proctoring or admissions scoring — not practice simulators.

DealSim falls under Article 50 (limited-risk chatbot systems): users must be informed they are interacting with AI.

### Article 50 Transparency (effective August 2, 2026)

Notice at session start: "You are about to practice against an AI opponent." Costs nothing to implement now.

### Prohibited Practices (Art. 5, in force Feb 2, 2025)

Subliminal manipulation, exploitation of vulnerabilities, social scoring — DealSim does none.

### GPAI Obligations

Apply to the LLM provider (OpenAI, Anthropic), not to DealSim as deployer.

### German DPA AI Guidance (2024-2025)

- Pre-processing filters to detect PII before sending to LLM API
- Human oversight mechanism (user flagging of problematic outputs)
- Documentable decision-making basis for AI responses

---

## 5. Freelance and Business Structure

### Freiberufler vs. Gewerbetreibender

Operating a SaaS with subscription revenue is often classified as Gewerbebetrieb (§15 EStG). Gray zone for solo developer running own SaaS.

**Safe path:** Register Gewerbe at Gewerbeamt Munster (EUR 20-30, 30 minutes). Does not prevent also registering as Freiberufler for consulting.

### Kleinunternehmerregelung (§19 UStG) — as of Jan 1, 2025

- Prior year revenue: must not exceed EUR 25,000
- Current year revenue: must not exceed EUR 100,000
- No VAT charged, no input VAT reclaimable
- B2B customers may prefer proper VAT invoices — consider opting out if significant B2B revenue

### Invoice Requirements (§14 UStG)

- Full name and address of seller and buyer
- Date of issue, unique sequential invoice number
- Description of service, net amount
- Kleinunternehmer: include "Gemaess §19 UStG wird keine Umsatzsteuer berechnet"
- Steuernummer or USt-IdNr.

---

## 6. Payment Processing (Stripe)

### PSD2 / SCA

Stripe handles SCA automatically via 3D Secure 2.0. Use Stripe's SCA-ready products (Payment Intents API).

### Stripe Handles

- PCI DSS compliance
- SCA / 3D Secure
- SEPA Direct Debit mandates
- VAT calculation (Stripe Tax)

### Your Obligations

- Complete Stripe identity verification
- Sign Stripe DPA (Settings > Legal in dashboard)
- Configure correct business type
- Display required payment info in checkout

### Widerrufsrecht (14-day withdrawal)

For digital services with immediate delivery: user must explicitly consent to immediate delivery AND acknowledge forfeiting withdrawal right. Clear checkbox at checkout required.

---

## Prioritized Launch Checklist

### Must-Have Before Launch (Blocking)

| # | Item | Effort |
|---|---|---|
| 1 | Impressum page (name, address, email) | 1 hour |
| 2 | CDN localization (zero non-EU resources before consent) | 30 min |
| 3 | Privacy Policy (Datenschutzerklarung) in German | 2-4 hours |
| 4 | Cookie implementation (if non-essential cookies exist) | 1-2 hours |
| 5 | DPA with LLM provider | 15 min |
| 6 | Account deletion functionality (Art. 17) | 2-4 hours |
| 7 | Business registration (Gewerbeamt or Finanzamt) | 30 min + wait |

### Must-Have Within 30 Days

| # | Item | Effort |
|---|---|---|
| 8 | Terms of Service in German | 2-4 hours |
| 9 | Widerrufsbelehrung (cancellation policy) | 1 hour |
| 10 | Record of Processing Activities (RoPA) | 2 hours |

### Pre-Launch Recommended

| # | Item | Effort |
|---|---|---|
| 11 | AI transparency notice at session start | 15 min |
| 12 | Stripe DPA (dashboard) | 15 min |
| 13 | Data retention automation (cron cleanup) | 2 hours |
| 14 | Steuerberater consultation | EUR 150-300 |

### Can Wait Until Scale

| # | Item |
|---|---|
| 15 | EU AI Act Art. 50 formal compliance (Aug 2026) |
| 16 | Formal DPO appointment |
| 17 | Cookie consent audit update |
| 18 | VAT registration opt-out |
| 19 | W-IdNr. in Impressum (Dec 2026) |
| 20 | Remove EU ODR link (after Jul 2025) |

---

## Confidence Notes

- All legal claims: confidence 0.75-0.90
- Freiberufler vs. Gewerbe for solo SaaS: confidence 0.65 (genuine gray zone — Steuerberater consultation recommended)
- EU AI Act Limited Risk classification: confidence 0.85
- GDPR retention periods: based on German DPA guidance and industry practice

---

*Research conducted March 2026. Sources include EDPB guidance, German DPA publications, DDG text, EU AI Act, Stripe documentation, and German tax law references.*
