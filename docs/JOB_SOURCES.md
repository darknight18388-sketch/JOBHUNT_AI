# Job sources: what is allowed and why

Checked November 2026. Terms change, so re-check before relying on them.

| Source | Status | Notes |
|---|---|---|
| Remotive public API | Used | Free, no key. Asks for at most ~4 fetches/day and max 2 requests/min; listings are delayed 24 h; attribution and a link back are required; jobs must not be re-submitted to other aggregators; displaying their jobs just to collect sign-ups breaches their terms. Our connector fetches at most once per 6 h and always shows "Job via Remotive" with the original link. If this app is ever made public with sign-up, review their terms first. |
| Manual entry | Used | You paste a vacancy's link and description. Stored privately for you only, labelled "Unverified". This is the Sri Lanka path. |
| Adzuna API | Not used yet | Free key, but its supported countries do not include Sri Lanka (India and Singapore are covered). |
| Arbeitnow API | Not used | Terms allow personal, non-commercial use only. |
| Sri Lankan job sites | Not used | No public API found. We do not scrape sites against their terms. If a site publishes an official RSS/API or gives permission, add a connector in `backend/app/services/connectors/`. |

## Adding a connector
Subclass `JobConnector`, return `NormalizedJob` records, register it in `CONNECTORS` in
`backend/app/api/jobs.py`, and add fixture-based tests. Never bypass CAPTCHA, logins or rate limits.
