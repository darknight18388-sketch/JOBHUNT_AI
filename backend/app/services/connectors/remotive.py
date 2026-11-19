"""Remotive public API. Terms (checked Nov 2026): at most ~4 fetches/day, max 2 requests/min,
listings delayed 24h, attribution + link back required, do not resubmit jobs to other
aggregators. Re-check https://github.com/remotive-com/remote-jobs-api before changing usage."""
import html as _html
import re
from datetime import datetime, timezone

import httpx

from app.services.connectors.base import JobConnector, NormalizedJob

API_URL = "https://remotive.com/api/remote-jobs"


def html_to_text(raw: str, limit: int = 20000) -> str:
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", raw or "")
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t).strip()
    return t[:limit]


def parse_date(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def parse_remotive(payload) -> list[NormalizedJob]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("Unexpected response format from Remotive")
    out = []
    for j in payload["jobs"]:
        if not isinstance(j, dict):
            continue
        ext, title, url = j.get("id"), (j.get("title") or "").strip(), (j.get("url") or "").strip()
        if ext is None or not title or not url.startswith("https://"):
            continue  # incomplete record: skip rather than guess
        tags = [str(t)[:40] for t in (j.get("tags") or []) if isinstance(t, str)][:15]
        out.append(NormalizedJob(
            external_id=str(ext)[:200],
            title=title[:300],
            company=(j.get("company_name") or "")[:200],
            location=(j.get("candidate_required_location") or "Worldwide")[:200],
            country="ANY",
            is_remote=True,
            job_type=(j.get("job_type") or "")[:50],
            salary_text=(j.get("salary") or "")[:200],
            description=html_to_text(j.get("description") or ""),
            url=url[:1000],
            tags=tags,
            posted_at=parse_date(j.get("publication_date")),
        ))
    return out


class RemotiveConnector(JobConnector):
    key = "remotive"
    name = "Remotive"
    site_url = "https://remotive.com"
    attribution = "Job via Remotive (https://remotive.com)"

    def fetch(self, query: str = "", country: str = "ALL", location: str = "") -> list[NormalizedJob]:
        r = httpx.get(API_URL, timeout=20, follow_redirects=True,
                      headers={"User-Agent": "JOBHUNT-AI/0.1 (personal job-search assistant)"})
        r.raise_for_status()
        return parse_remotive(r.json())
