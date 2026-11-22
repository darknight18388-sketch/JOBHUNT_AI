"""Company career pages that run on a public ATS. These vendors publish documented, public, read-only job-board
JSON APIs made for embedding a company's vacancies, so we read those instead of scraping the HTML page."""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.services.connectors.base import JobConnector, NormalizedJob
from app.services.connectors.remotive import html_to_text, parse_date as _date

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
UA = {"User-Agent": "JOBHUNT-AI/1.0 (personal job-search assistant)"}


def detect_ats(url: str) -> tuple[str, str] | None:
    """Career-page URL -> (ats, token) for the supported public job-board APIs, else None."""
    u = urlparse(url if "//" in url else "https://" + url)
    host, parts = (u.hostname or "").lower(), [p for p in u.path.split("/") if p]
    tok = None
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io") and parts:
        ats, tok = "greenhouse", parts[0]
    elif host in ("jobs.lever.co", "jobs.eu.lever.co") and parts:
        ats, tok = "lever", parts[0]
    elif host == "jobs.ashbyhq.com" and parts:
        ats, tok = "ashby", parts[0]
    elif host.endswith(".recruitee.com") and host.count(".") == 2:
        ats, tok = "recruitee", host.split(".")[0]
    elif host == "apply.workable.com" and parts:
        ats, tok = "workable", parts[0]
    else:
        return None
    return (ats, tok) if TOKEN_RE.match(tok) else None


def _ms(v) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(v) / 1000, timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _ok(job: NormalizedJob) -> bool:
    return bool(job.title and job.url.startswith("https://") and job.external_id)


def _clean(*parts: str) -> str:
    return "\n\n".join(t for t in (html_to_text(p) for p in parts if p) if t)[:20000]


def _unesc(s: str) -> str:  # Greenhouse returns HTML-escaped HTML
    import html
    return html.unescape(s or "")


def parse_greenhouse(payload, company: str, country: str = "") -> list[NormalizedJob]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("Unexpected Greenhouse response")
    out = []
    for j in payload["jobs"]:
        loc = (j.get("location") or {}).get("name", "") if isinstance(j.get("location"), dict) else ""
        job = NormalizedJob(
            external_id=str(j.get("id", "")), title=(j.get("title") or "").strip()[:300], company=company,
            location=loc[:200], is_remote="remote" in loc.lower(), url=(j.get("absolute_url") or "")[:1000],
            description=_clean(_unesc(j.get("content", ""))),
            tags=[d.get("name", "")[:40] for d in j.get("departments", []) if isinstance(d, dict)][:5],
            posted_at=_date(j.get("first_published") or j.get("updated_at")), country=country)
        if _ok(job):
            out.append(job)
    return out


def parse_lever(payload, company: str, country: str = "") -> list[NormalizedJob]:
    if not isinstance(payload, list):
        raise ValueError("Unexpected Lever response")
    out = []
    for j in payload:
        if not isinstance(j, dict):
            continue
        cat = j.get("categories") or {}
        loc = cat.get("location") or ""
        lists = " ".join(f"{l.get('text', '')}\n{l.get('content', '')}" for l in j.get("lists", []) if isinstance(l, dict))
        job = NormalizedJob(
            external_id=str(j.get("id", "")), title=(j.get("text") or "").strip()[:300], company=company,
            location=loc[:200], is_remote=(j.get("workplaceType") == "remote") or "remote" in loc.lower(),
            job_type=(cat.get("commitment") or "")[:50], url=(j.get("hostedUrl") or "")[:1000],
            description=_clean(j.get("descriptionPlain") or j.get("description", ""), lists),
            tags=[cat["team"][:40]] if cat.get("team") else [], posted_at=_ms(j.get("createdAt")), country=country)
        if _ok(job):
            out.append(job)
    return out


def parse_ashby(payload, company: str, country: str = "") -> list[NormalizedJob]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("Unexpected Ashby response")
    out = []
    for j in payload["jobs"]:
        if not isinstance(j, dict) or j.get("isListed") is False:
            continue
        loc = j.get("location") or ""
        job = NormalizedJob(
            external_id=str(j.get("id", "")), title=(j.get("title") or "").strip()[:300], company=company,
            location=str(loc)[:200], is_remote=bool(j.get("isRemote")) or "remote" in str(loc).lower(),
            job_type=str(j.get("employmentType") or "")[:50], url=(j.get("jobUrl") or "")[:1000],
            description=_clean(j.get("descriptionHtml") or j.get("descriptionPlain", "")),
            tags=[str(j["department"])[:40]] if j.get("department") else [], posted_at=_date(j.get("publishedAt")),
            country=country)
        if _ok(job):
            out.append(job)
    return out


def parse_recruitee(payload, company: str, country: str = "") -> list[NormalizedJob]:
    if not isinstance(payload, dict) or not isinstance(payload.get("offers"), list):
        raise ValueError("Unexpected Recruitee response")
    out = []
    for j in payload["offers"]:
        if not isinstance(j, dict):
            continue
        loc = j.get("location") or ", ".join(x for x in [j.get("city"), j.get("country")] if x)
        job = NormalizedJob(
            external_id=str(j.get("id", "")), title=(j.get("title") or "").strip()[:300], company=company,
            location=str(loc)[:200], is_remote=bool(j.get("remote")), url=(j.get("careers_url") or "")[:1000],
            job_type=str(j.get("employment_type_code") or "")[:50],
            description=_clean(j.get("description", ""), j.get("requirements", "")),
            posted_at=_date(j.get("created_at")), country=country)
        if _ok(job):
            out.append(job)
    return out


def parse_workable(payload, company: str, country: str = "") -> list[NormalizedJob]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("Unexpected Workable response")
    out = []
    for j in payload["jobs"]:
        if not isinstance(j, dict):
            continue
        loc = ", ".join(x for x in [j.get("city"), j.get("state"), j.get("country")] if x)
        job = NormalizedJob(
            external_id=str(j.get("shortcode") or j.get("id") or ""), title=(j.get("title") or "").strip()[:300],
            company=company, location=loc[:200], is_remote=bool(j.get("telecommuting")),
            job_type=str(j.get("employment_type") or "")[:50], url=(j.get("url") or j.get("application_url") or "")[:1000],
            description=_clean(j.get("description", "")), posted_at=_date(j.get("published_on") or j.get("created_at")),
            country=country)
        if _ok(job):
            out.append(job)
    return out


PARSERS = {"greenhouse": parse_greenhouse, "lever": parse_lever, "ashby": parse_ashby,
           "recruitee": parse_recruitee, "workable": parse_workable}


def api_url(ats: str, token: str) -> str:
    if not TOKEN_RE.match(token):
        raise ValueError("Bad board name")
    return {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true",
        "lever": f"https://api.lever.co/v0/postings/{token}?mode=json",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{token}",
        "recruitee": f"https://{token}.recruitee.com/api/offers/",
        "workable": f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true",
    }[ats]


class AtsConnector(JobConnector):
    def __init__(self, key: str, company: str, ats: str, token: str, country: str = "", site_url: str = ""):
        self.key, self.name, self.ats, self.token, self.country = key, company, ats, token, country
        self.site_url = site_url
        self.attribution = f"From {company}'s official career page"

    def fetch(self, query: str = "", country: str = "ALL", location: str = "") -> list[NormalizedJob]:
        r = httpx.get(api_url(self.ats, self.token), headers=UA, timeout=25, follow_redirects=False)
        r.raise_for_status()
        return PARSERS[self.ats](r.json(), self.name, self.country)
