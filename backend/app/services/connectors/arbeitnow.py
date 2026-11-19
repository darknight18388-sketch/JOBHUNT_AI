"""Arbeitnow (Germany). Its terms allow personal, non-commercial use only, so it is OFF by default.
Enable with ENABLE_ARBEITNOW=true for personal use."""
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.services.connectors.base import JobConnector, NormalizedJob
from app.services.connectors.remotive import html_to_text

UA = {"User-Agent": "JOBHUNT-AI/0.1 (personal job-search assistant)"}


class ArbeitnowConnector(JobConnector):
    key = "arbeitnow"
    name = "Arbeitnow"
    site_url = "https://www.arbeitnow.com"
    attribution = "Job via Arbeitnow (https://www.arbeitnow.com)"
    min_interval_hours = 1

    def enabled(self) -> bool:
        return settings.enable_arbeitnow

    def applies(self, country: str) -> bool:
        return country in ("ALL", "DE")

    def fetch(self, query: str = "", country: str = "ALL", location: str = "") -> list[NormalizedJob]:
        r = httpx.get("https://www.arbeitnow.com/api/job-board-api", headers=UA, timeout=20)
        r.raise_for_status()
        words = query.lower().split()
        out = []
        for j in r.json().get("data", []):
            if not j.get("slug") or not j.get("title") or not str(j.get("url", "")).startswith("https://"):
                continue
            blob = f"{j['title']} {j.get('description', '')} {' '.join(j.get('tags') or [])}".lower()
            if words and not all(w in blob for w in words):
                continue
            ts = j.get("created_at")
            out.append(NormalizedJob(
                external_id=j["slug"][:200], title=j["title"][:300], company=(j.get("company_name") or "")[:200],
                location=(j.get("location") or "")[:200], country="DE", is_remote=bool(j.get("remote")),
                description=html_to_text(j.get("description", "")), url=j["url"][:1000],
                tags=[str(t)[:40] for t in (j.get("tags") or [])][:15],
                posted_at=datetime.fromtimestamp(ts, timezone.utc) if isinstance(ts, (int, float)) else None))
        return out[:40]
