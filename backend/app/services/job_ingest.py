import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.services.connectors.base import NormalizedJob


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def dedupe_key(title: str, company: str, location: str) -> str:
    raw = f"{_norm(title)}|{_norm(company)}|{_norm(location)}"
    return hashlib.sha1(raw.encode()).hexdigest()


def ingest(db: Session, source_key: str, items: list[NormalizedJob], owner_id=None) -> dict:
    """Insert/update normalized jobs. Same source+external_id -> update; same
    title+company+location already present in this scope -> duplicate (skipped)."""
    stats = {"created": 0, "updated": 0, "duplicates": 0}
    now = datetime.now(timezone.utc)
    scope = Job.owner_user_id.is_(None) if owner_id is None else Job.owner_user_id == owner_id
    for it in items:
        existing = db.scalar(select(Job).where(Job.source_key == source_key,
                                               Job.external_id == it.external_id))
        key = dedupe_key(it.title, it.company, it.location)
        if existing:
            for f in ("title", "company", "location", "country", "is_remote", "job_type", "salary_text",
                      "description", "url", "tags", "posted_at"):
                setattr(existing, f, getattr(it, f))
            existing.dedupe_key, existing.fetched_at = key, now
            stats["updated"] += 1
            continue
        if db.scalar(select(Job.id).where(Job.dedupe_key == key, scope)):
            stats["duplicates"] += 1
            continue
        db.add(Job(source_key=source_key, external_id=it.external_id, owner_user_id=owner_id,
                   title=it.title, company=it.company, location=it.location, country=it.country,
                   is_remote=it.is_remote, job_type=it.job_type, salary_text=it.salary_text,
                   description=it.description, url=it.url, tags=list(it.tags),
                   posted_at=it.posted_at, fetched_at=now, dedupe_key=key))
        db.flush()  # session has autoflush off; make this row visible to later duplicate checks
        stats["created"] += 1
    db.commit()
    return stats
