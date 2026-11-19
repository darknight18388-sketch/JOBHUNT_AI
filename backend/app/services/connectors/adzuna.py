"""Adzuna official API (free key). Terms/attribution: check developer.adzuna.com before public use."""
import httpx

from app.core.config import settings
from app.core.countries import ADZUNA
from app.services.connectors.base import JobConnector, NormalizedJob
from app.services.connectors.remotive import html_to_text, parse_date

UA = {"User-Agent": "JOBHUNT-AI/0.1 (personal job-search assistant)"}


class AdzunaConnector(JobConnector):
    key = "adzuna"
    name = "Adzuna"
    site_url = "https://www.adzuna.com"
    attribution = "Jobs by Adzuna (https://www.adzuna.com)"
    min_interval_hours = 10 / 3600
    uses_query = True

    def enabled(self) -> bool:
        return bool(settings.adzuna_app_id and settings.adzuna_app_key)

    def applies(self, country: str) -> bool:
        return country == "ALL" or country in ADZUNA

    def fetch(self, query: str = "", country: str = "ALL", location: str = "") -> list[NormalizedJob]:
        code = ADZUNA.get(country) or settings.adzuna_country
        cc = country if country in ADZUNA else code.upper()
        r = httpx.get(f"https://api.adzuna.com/v1/api/jobs/{code}/search/1", headers=UA, timeout=20,
                      params={"app_id": settings.adzuna_app_id, "app_key": settings.adzuna_app_key,
                              "what": query, "where": location, "results_per_page": 30})
        r.raise_for_status()
        out = []
        for j in r.json().get("results", []):
            if not j.get("id") or not j.get("title") or not str(j.get("redirect_url", "")).startswith("https://"):
                continue
            lo, hi = j.get("salary_min"), j.get("salary_max")
            out.append(NormalizedJob(
                external_id=str(j["id"]), title=html_to_text(j["title"])[:300],
                company=((j.get("company") or {}).get("display_name") or "")[:200],
                location=((j.get("location") or {}).get("display_name") or "")[:200], country=cc,
                salary_text=f"{int(lo)}-{int(hi)}" if lo and hi else "",
                description=html_to_text(j.get("description", "")), url=j["redirect_url"][:1000],
                posted_at=parse_date(j.get("created"))))
        return out
