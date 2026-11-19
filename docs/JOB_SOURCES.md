# Job sources: what is allowed and why

Checked November 2026. Terms change, so re-check before relying on them.
Search flow: you pick a country -> only the sources that serve it are used -> new vacancies are stored
(deduplicated) -> the list is filtered by country (plus worldwide-remote jobs and jobs you added).
If you leave the title blank, searches are built from your CV's top skills (generic ones like Teamwork are skipped).

| Source | Countries | Status | Notes |
|---|---|---|---|
| Remotive public API | Worldwide remote | On | Free, no key. Asks for ~4 fetches/day max, 2 requests/min, listings delayed 24 h, attribution + link back, no re-submission to other aggregators; showing its jobs only to gather sign-ups breaches its terms. We fetch at most once per 6 h. If this app is ever made public with sign-up, review their terms first. |
| Official RSS feeds (`backend/app/sources.json`) | Per feed (default: Sri Lanka) | On | ITPro.lk publishes RSS feeds for subscribers at itpro.lk/rss. **IT jobs only.** Fetched at most every 30 min. Add only feeds the publisher offers for this use. |
| Adzuna API | GB, US, AU, CA, DE, FR, IN, IT, NL, NZ, PL, SG, ZA, BR, AT, CH, MX, ES | Needs free key | **Not Sri Lanka.** Set `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`. Check their attribution terms before public use. |
| Jooble API | Many (Sri Lanka unverified) | Needs free key | Set `JOOBLE_API_KEY`, then test Sri Lanka yourself. |
| Arbeitnow API | Germany | Off by default | Personal, non-commercial use only. Enable with `ENABLE_ARBEITNOW=true`. |
| Import from link | Any | On | You paste one vacancy URL. Read only if the page has schema.org JobPosting data and robots.txt allows it; private IP addresses and redirects are blocked. Stored privately and labelled Unverified. |
| Add manually | Any | On | Paste the vacancy and its official link. Private, Unverified. |
| Sri Lankan general job sites (TopJobs, ikman...) | | Not used | No public API found. We do not scrape sites against their terms. If a site offers an official feed/API or permission, add it. |

## Adding a source
RSS: add an entry to `sources.json`. API: subclass `JobConnector` in `backend/app/services/connectors/`,
register it in `registry.py`, add fixture-based tests. Never bypass CAPTCHA, logins or rate limits.
