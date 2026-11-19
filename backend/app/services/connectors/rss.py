"""Official RSS feeds listed in app/sources.json (e.g. ITPro.lk publishes feeds for subscribers).
Only add feeds the publisher offers for this use. All enabled feeds are fetched together (they are
small), each job keeps its feed's country, and the search filters by country afterwards."""
import json
import logging
import re
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx
from defusedxml import ElementTree as ET

from app.core.countries import COUNTRIES
from app.services.connectors.base import JobConnector, NormalizedJob
from app.services.connectors.remotive import html_to_text

log = logging.getLogger("jobhunt.rss")
SOURCES_FILE = Path(__file__).resolve().parents[2] / "sources.json"
NS = {"content": "http://purl.org/rss/1.0/modules/content/", "dc": "http://purl.org/dc/elements/1.1/"}
UA = {"User-Agent": "JOBHUNT-AI/0.1 (personal job-search assistant)"}


def load_feeds(path: Path = SOURCES_FILE) -> list[dict]:
    try:
        feeds = json.loads(Path(path).read_text()).get("rss", [])
    except (OSError, ValueError):
        return []
    return [f for f in feeds
            if isinstance(f, dict) and f.get("enabled") and f.get("country") in COUNTRIES
            and isinstance(f.get("url"), str) and f["url"].startswith("https://")
            and isinstance(f.get("name"), str)]


def parse_rss(xml: bytes, country: str) -> list[NormalizedJob]:
    root = ET.fromstring(xml)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        short = html_to_text(item.findtext("description") or "")
        full = html_to_text(item.findtext("content:encoded", namespaces=NS) or "") or short
        full = re.sub(r"\s*Apply for this job\s*$", "", full).strip()
        m = re.match(r"Location:\s*(.+)", short)
        loc = m.group(1).strip() if m else COUNTRIES.get(country, "")
        posted = None
        if item.findtext("pubDate"):
            try:
                posted = parsedate_to_datetime(item.findtext("pubDate"))
            except (TypeError, ValueError):
                posted = None
        out.append(NormalizedJob(
            external_id=(item.findtext("guid") or link)[:200], title=title[:300],
            company=(item.findtext("dc:creator", namespaces=NS) or "").strip()[:200],
            location=loc[:200], country=country, is_remote="remote" in loc.lower(),
            description=full, url=link[:1000], posted_at=posted))
    return out


class RssConnector(JobConnector):
    key = "rss"
    name = "Official RSS feeds"
    site_url = ""
    attribution = "Job via official RSS feed"
    min_interval_hours = 0.5  # feeds advertise a ~30 min TTL

    def feeds(self) -> list[dict]:
        return load_feeds()

    def enabled(self) -> bool:
        return bool(self.feeds())

    def applies(self, country: str) -> bool:
        return any(country == "ALL" or f["country"] == country for f in self.feeds())

    def fetch(self, query: str = "", country: str = "ALL", location: str = "") -> list[NormalizedJob]:
        jobs, failures, feeds = [], 0, self.feeds()
        for f in feeds:
            try:
                r = httpx.get(f["url"], headers=UA, timeout=20, follow_redirects=True)
                r.raise_for_status()
                jobs.extend(parse_rss(r.content, f["country"]))
            except Exception as e:  # one broken feed must not hide the others
                failures += 1
                log.warning("feed %s failed: %s", f["name"], type(e).__name__)
        if feeds and failures == len(feeds):
            raise RuntimeError("all RSS feeds failed")
        return jobs
