"""Jooble official API (free key). Sri Lanka coverage is unverified: test with your own key."""
import httpx

from app.core.config import settings
from app.core.countries import COUNTRIES
from app.services.connectors.base import JobConnector, NormalizedJob
from app.services.connectors.remotive import html_to_text, parse_date

UA = {"User-Agent": "JOBHUNT-AI/0.1 (personal job-search assistant)"}


class JoobleConnector(JobConnector):
    key = "jooble"
    name = "Jooble"
    site_url = "https://jooble.org"
    attribution = "Jobs via Jooble (https://jooble.org)"
    min_interval_hours = 10 / 3600
    uses_query = True

    def enabled(self) -> bool:
        return bool(settings.jooble_api_key)

    def fetch(self, query: str = "", country: str = "ALL", location: str = "") -> list[NormalizedJob]:
        where = " ".join(x for x in [location, COUNTRIES.get(country, "")] if x)
        r = httpx.post(f"https://jooble.org/api/{settings.jooble_api_key}",
                       json={"keywords": query, "location": where}, headers=UA, timeout=20)
        r.raise_for_status()
        out = []
        for j in r.json().get("jobs", []):
            link = str(j.get("link", ""))
            if not j.get("title") or not link.startswith(("http://", "https://")):
                continue
            out.append(NormalizedJob(
                external_id=str(j.get("id") or link)[:200], title=html_to_text(j["title"])[:300],
                company=(j.get("company") or "")[:200], location=(j.get("location") or "")[:200],
                country=country if country != "ALL" else "", salary_text=(j.get("salary") or "")[:200],
                description=html_to_text(j.get("snippet", "")), url=link[:1000],
                posted_at=parse_date(j.get("updated"))))
        return out
