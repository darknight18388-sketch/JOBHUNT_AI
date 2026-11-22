"""Any company career page (or a single vacancy link) that publishes schema.org JobPosting data (JSON-LD).
Google Jobs requires this markup, so many company sites include it. We read only pages robots.txt allows."""
import html as _html
import json
import re
import time
from urllib.parse import urldefrag, urljoin, urlparse

from app.services.connectors import web
from app.services.connectors.base import JobConnector, NormalizedJob
from app.services.connectors.remotive import html_to_text, parse_date as _date

SCRIPT_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
HREF_RE = re.compile(r'href=["\']([^"\'#][^"\']*)["\']', re.I)
JOBLINK_RE = re.compile(r"(job|career|vacanc|position|opening|opportunit|recruit)", re.I)
MAX_DETAIL_PAGES = 15
DELAY_S = 1.0  # one request per second at most


def _walk(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk(n)
    elif isinstance(node, dict):
        t = node.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            yield node
        for k in ("@graph", "itemListElement", "item"):
            if k in node:
                yield from _walk(node[k])


def extract_postings(html: str) -> list[dict]:
    posts = []
    for block in SCRIPT_RE.findall(html):
        for candidate in (block, _html.unescape(block)):  # some sites HTML-escape the JSON
            try:
                posts.extend(_walk(json.loads(candidate)))
                break
            except ValueError:
                continue
    return posts


def posting_to_job(post: dict, page_url: str, country: str = "", company_fallback: str = "") -> NormalizedJob | None:
    org = post.get("hiringOrganization") or {}
    company = (org.get("name") if isinstance(org, dict) else str(org)) or company_fallback
    loc = post.get("jobLocation") or {}
    loc = loc[0] if isinstance(loc, list) and loc else loc
    addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
    if not isinstance(addr, dict):
        addr = {}
    place = ", ".join(str(x) for x in [addr.get("addressLocality"), addr.get("addressRegion")] if isinstance(x, str))
    ac = addr.get("addressCountry")
    ac = ac.get("name") if isinstance(ac, dict) else ac
    if isinstance(ac, str) and len(ac) == 2 and not country:
        country = ac.upper()
    url = post.get("url") if isinstance(post.get("url"), str) else page_url
    if not url.startswith("https://"):
        url = page_url
    title = html_to_text(str(post.get("title") or ""))
    if not title or not url.startswith("https://"):
        return None
    base = post.get("baseSalary") or {}
    val = (base.get("value") or {}) if isinstance(base, dict) else {}
    salary = ""
    if isinstance(val, dict) and (val.get("minValue") or val.get("value")):
        salary = f"{val.get('minValue', val.get('value'))}-{val.get('maxValue', '')} {base.get('currency', '')}".replace("- ", " ").strip()
    jt = post.get("employmentType")
    jt = ", ".join(jt) if isinstance(jt, list) else (jt or "")
    return NormalizedJob(
        external_id=url[:200], title=title[:300], company=str(company)[:200], location=place[:200],
        is_remote=post.get("jobLocationType") == "TELECOMMUTE", job_type=str(jt)[:50], salary_text=salary[:200],
        description=html_to_text(str(post.get("description") or "")), url=url[:1000],
        posted_at=_date(post.get("datePosted")) if isinstance(post.get("datePosted"), str) else None, country=country)


def import_single(url: str, country: str = "") -> NormalizedJob:
    html = web.safe_get(url)
    for post in extract_postings(html):
        job = posting_to_job(post, url, country)
        if job:
            return job
    raise LookupError("No structured job data found on that page. Use 'Add a job manually' instead.")


def detail_links(html: str, page_url: str) -> list[str]:
    host, seen, out = urlparse(page_url).netloc, set(), []
    for href in HREF_RE.findall(html):
        full = urldefrag(urljoin(page_url, href))[0]
        p = urlparse(full)
        if p.netloc != host or p.scheme not in ("http", "https") or full in seen or full.rstrip("/") == page_url.rstrip("/"):
            continue
        if re.search(r"\.(pdf|jpg|png|zip|css|js)$", p.path, re.I) or not JOBLINK_RE.search(p.path):
            continue
        seen.add(full)
        out.append(full)
    return out[:MAX_DETAIL_PAGES]


class CareerPageConnector(JobConnector):
    """Generic fallback for a company's own career page (no known ATS)."""

    def __init__(self, key: str, company: str, url: str, country: str = ""):
        self.key, self.name, self.page_url, self.country, self.company = key, company, url, country, company
        self.site_url = url
        self.attribution = f"From {company}'s official career page"

    def fetch(self, query: str = "", country: str = "ALL", location: str = "") -> list[NormalizedJob]:
        html = web.safe_get(self.page_url)
        jobs = [j for p in extract_postings(html) if (j := posting_to_job(p, self.page_url, self.country, self.company))]
        if jobs:
            return jobs
        for link in detail_links(html, self.page_url):
            time.sleep(DELAY_S)
            try:
                page = web.safe_get(link)
            except Exception:
                continue
            jobs += [j for p in extract_postings(page) if (j := posting_to_job(p, link, self.country, self.company))]
        if not jobs:
            raise LookupError("No JobPosting data found. This page may not publish structured vacancies.")
        return jobs
