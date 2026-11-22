"""Careerjet official partner API v4 (free publisher key). It aggregates many job sites.
Docs: https://www.careerjet.com/partners/api . user_ip and user_agent are required by Careerjet and
must be the end-user's. Locale support for a country is decided by Careerjet: an unsupported
locale returns HTTP 400 and is reported as 'source unavailable'."""
import hashlib

import httpx

from app.core.config import settings
from app.services.connectors.base import JobConnector, NormalizedJob
from app.services.connectors.context import client_context
from app.services.connectors.remotive import html_to_text, parse_date

API_URL = "https://search.api.careerjet.net/v4/query"
LOCALES = {
    "LK": "en_LK", "IN": "en_IN", "BD": "en_BD", "PK": "en_PK", "NP": "en_NP", "MY": "en_MY",
    "SG": "en_SG", "AE": "en_AE", "QA": "en_QA", "SA": "en_SA", "KW": "en_KW", "OM": "en_OM",
    "BH": "en_BH", "AU": "en_AU", "NZ": "en_NZ", "GB": "en_GB", "IE": "en_IE", "US": "en_US",
    "CA": "en_CA", "ZA": "en_ZA",
}


class CareerjetConnector(JobConnector):
    key = "careerjet"
    name = "Careerjet"
    site_url = "https://www.careerjet.com"
    attribution = "Jobs via Careerjet (https://www.careerjet.com)"
    min_interval_hours = 10 / 3600
    uses_query = True

    def enabled(self) -> bool:
        return bool(settings.careerjet_api_key)

    def applies(self, country: str) -> bool:
        return country in LOCALES

    def fetch(self, query: str = "", country: str = "ALL", location: str = "") -> list[NormalizedJob]:
        ctx = client_context.get()
        params = {
            "locale_code": LOCALES[country], "keywords": query, "page_size": 30, "sort": "date",
            "user_ip": settings.careerjet_user_ip or ctx.get("ip") or "127.0.0.1",
            "user_agent": ctx.get("ua") or "JOBHUNT-AI/0.1",
        }
        if location:
            params["location"] = location
        r = httpx.get(API_URL, params=params, auth=(settings.careerjet_api_key, ""), timeout=20)
        r.raise_for_status()
        data = r.json()
        if data.get("type") != "JOBS":  # location could not be resolved: nothing to store
            return []
        out = []
        for j in data.get("jobs", []):
            url = str(j.get("url", ""))
            if not j.get("title") or not url.startswith("https://"):
                continue
            out.append(NormalizedJob(
                external_id=hashlib.sha1(url.encode()).hexdigest(), title=html_to_text(j["title"])[:300],
                company=(j.get("company") or "")[:200], location=(j.get("locations") or "")[:200],
                country=country, salary_text=(j.get("salary") or "")[:200],
                description=html_to_text(j.get("description", "")), url=url[:1000],
                posted_at=parse_date(_iso(j.get("date")))))
        return out


def _iso(value):
    """Careerjet dates look like 'Wed,15 Nov 2025 19:13:43 GMT' (RFC 2822), not ISO."""
    if not value or not isinstance(value, str):
        return None
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return None
