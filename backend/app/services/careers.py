"""User-added company career pages: detect the ATS, fetch politely, store privately for that user."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.job import CareerSource
from app.services.connectors.ats import AtsConnector, detect_ats
from app.services.connectors.base import JobConnector
from app.services.connectors.jsonld import CareerPageConnector
from app.services.job_ingest import ingest

log = logging.getLogger("jobhunt.careers")
MIN_INTERVAL = timedelta(hours=6)
MIN_RETRY = timedelta(minutes=5)
MAX_PER_USER = 25


def classify(url: str) -> tuple[str, str]:
    found = detect_ats(url)
    return found if found else ("jsonld", "")


def connector_for(src: CareerSource) -> JobConnector:
    key = f"career-{src.id.hex[:8]}"
    if src.ats == "jsonld":
        return CareerPageConnector(key, src.company, src.url, src.country)
    return AtsConnector(key, src.company, src.ats, src.token, src.country, src.url)


def _aware(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def next_allowed(src: CareerSource) -> datetime | None:
    nxt = _aware(src.last_fetched_at) + MIN_INTERVAL if src.last_fetched_at else None
    if src.last_status == "error" and src.last_attempt_at:
        retry = _aware(src.last_attempt_at) + MIN_RETRY
        nxt = max(nxt, retry) if nxt else retry
    return nxt


def refresh_career(db: Session, src: CareerSource) -> dict:
    now = datetime.now(timezone.utc)
    nxt = next_allowed(src)
    if nxt and now < nxt:
        return {"source": src.company, "status": "skipped",
                "message": f"Fetched recently. Next refresh allowed after {nxt.isoformat(timespec='minutes')}"}
    src.last_attempt_at = now
    try:
        items = connector_for(src).fetch()
    except Exception as e:  # blocked by robots.txt, no structured data, outage...
        log.warning("career source %s failed: %s", src.id, type(e).__name__)
        src.last_status, src.last_error = "error", f"{type(e).__name__}: {e}"[:300]
        db.commit()
        return {"source": src.company, "status": "error", "message": str(e)[:200] or "Source unavailable."}
    prefix = src.id.hex[:12]
    for it in items:
        it.external_id = f"{prefix}:{it.external_id}"[:200]
        it.company = it.company or src.company
        it.country = it.country or src.country
    stats = ingest(db, "career", items, owner_id=src.owner_user_id)
    src.last_status, src.last_error, src.last_fetched_at, src.last_count = "ok", "", now, len(items)
    db.commit()
    return {"source": src.company, "status": "ok", **stats}
