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
| Careerjet API | Sri Lanka (`en_LK`, unverified), India, UAE, Singapore, GB, US and more | Needs free publisher key | Aggregates many job sites. Set `CAREERJET_API_KEY` (publisher account at careerjet.com/partners). Careerjet decides which locales it supports; unsupported ones show as 'unavailable'. It requires the end user's IP and user-agent, which the app passes on. |
| Arbeitnow API | Germany | Off by default | Personal, non-commercial use only. Enable with `ENABLE_ARBEITNOW=true`. |
| Company career pages (your own list) | Any | On | Add a company's career page under Find Jobs. Greenhouse, Lever and Ashby boards are read through their documented public job-board APIs; Recruitee and Workable use public board JSON (response shapes not tested against a live board, so a failure is shown on that row). Any other page is read only through its schema.org JobPosting data, if robots.txt allows it, max 15 detail pages per refresh, 1 request/second, same host only. At most 25 pages per user, refreshed at most every 6 h. Jobs from these pages are visible only to you. |
| Import from link | Any | On | You paste one vacancy URL. Read only if the page has schema.org JobPosting data and robots.txt allows it; private IP addresses and redirects are blocked. Stored privately and labelled Unverified. |
| Add manually | Any | On | Paste the vacancy and its official link. Private, Unverified. |
| LinkedIn | | Link-out only | No public job-search API (partner programme only) and its terms forbid automated collection (scraping can get your account restricted). The app only builds a prefilled search link that opens in your browser. |
| TopJobs.lk, ikman.lk, Xpress.jobs, Indeed | | Link-out only | No official API/feed found, so nothing is collected. The app builds prefilled search links; you can import any job you find with 'Import from link' or 'Add manually'. |
| Sri Lankan general job sites (others) | | Not used | No public API found. We do not scrape sites against their terms. If a site offers an official feed/API or permission, add it. |

## Adding a source
RSS: add an entry to `sources.json`. API: subclass `JobConnector` in `backend/app/services/connectors/`,
register it in `registry.py`, add fixture-based tests. Never bypass CAPTCHA, logins or rate limits.
