import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.countries import ANY, COUNTRIES, valid_country
from app.database.session import get_db
from app.models.job import Job, JobSource
from app.models.resume import Resume, ResumeAnalysis
from app.models.user import User
from app.schemas.job import (ImportIn, JobList, JobOut, ManualJobIn, RefreshResult, SearchIn,
                             SearchOut, SourceOut)
from app.services.connectors import import_url as importer
from app.services.connectors.base import JobConnector, NormalizedJob
from app.services.connectors.registry import CONNECTORS
from app.services.job_ingest import ingest

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
log = logging.getLogger("jobhunt.jobs")

STALE_DAYS = 45
MIN_RETRY_AFTER_ERROR = timedelta(minutes=5)
RESULT_LIMIT = 30
PRIVATE_SOURCES = ("manual", "import")
SOFT_SKILLS = {"communication", "teamwork", "leadership", "problem solving", "customer service",
               "microsoft office", "excel", "powerpoint", "time management"}
SOURCE_INFO = {
    "manual": ("Added by you", "Added by you (unverified, check the official posting)"),
    "import": ("Imported link", "Imported from a link you gave (unverified, check the official posting)"),
}
for _c in CONNECTORS.values():
    SOURCE_INFO[_c.key] = (_c.name, _c.attribution)


def _aware(d: datetime | None) -> datetime | None:
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_error(e: Exception) -> str:
    """Never store URLs/messages from exceptions: they can contain API keys."""
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTPStatusError (HTTP {e.response.status_code})"
    return type(e).__name__


def _visible(user: User):
    return or_(Job.owner_user_id.is_(None), Job.owner_user_id == user.id)


def _country_cond(country: str, include_remote: bool, user: User):
    if not country or country == "ALL":
        return None
    conds = [Job.country == country, Job.owner_user_id == user.id]  # your own jobs always show
    if include_remote:
        conds.append(Job.country == ANY)
    return or_(*conds)


def _out(job: Job, full: bool) -> JobOut:
    name, attribution = SOURCE_INFO.get(job.source_key, (job.source_key, job.source_key))
    if job.source_key == "rss":
        host = urlparse(job.url).netloc or "RSS feed"
        name, attribution = host, f"Job via {host} (official RSS feed)"
    desc = job.description or ""
    if not full and len(desc) > 600:
        desc = desc[:600].rstrip() + "…"
    posted = _aware(job.posted_at)
    return JobOut(
        id=job.id, source_key=job.source_key, source_name=name, attribution=attribution,
        title=job.title, company=job.company, location=job.location, country=job.country or "",
        is_remote=job.is_remote, job_type=job.job_type, salary_text=job.salary_text,
        description=desc, url=job.url, tags=job.tags or [], posted_at=posted,
        fetched_at=_aware(job.fetched_at),
        is_stale=bool(posted and _now() - posted > timedelta(days=STALE_DAYS)),
        is_manual=job.source_key in PRIVATE_SOURCES)


def _source_row(db: Session, key: str) -> JobSource:
    row = db.get(JobSource, key)
    if row is None:
        row = JobSource(key=key)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _next_allowed(row: JobSource, conn: JobConnector) -> datetime | None:
    nxt = None
    if row.last_fetched_at:
        nxt = _aware(row.last_fetched_at) + timedelta(hours=conn.min_interval_hours)
    if row.last_attempt_at and row.last_status == "error":
        retry = _aware(row.last_attempt_at) + MIN_RETRY_AFTER_ERROR
        nxt = max(nxt, retry) if nxt else retry
    return nxt


def derive_queries(db: Session, user: User) -> list[str]:
    """No typing needed: use the top (non-generic) skills of your confirmed, else latest, CV."""
    a = db.scalar(select(ResumeAnalysis).join(Resume, Resume.id == ResumeAnalysis.resume_id)
                  .where(Resume.user_id == user.id)
                  .order_by(ResumeAnalysis.confirmed.desc(), Resume.created_at.desc()).limit(1))
    skills = [s for s in ((a.data or {}).get("skills", []) if a else []) if s.lower() not in SOFT_SKILLS]
    return skills[:3]


def _collect(conn: JobConnector, queries: list[str], country: str, location: str) -> list[NormalizedJob]:
    if conn.uses_query:
        items = [i for q in queries for i in conn.fetch(q, country, location)]
    else:
        items = conn.fetch(queries[0], country, location)
    seen, out = set(), []
    for it in items:
        if it.external_id not in seen:
            seen.add(it.external_id)
            out.append(it)
    return out


@router.get("/sources", response_model=list[SourceOut])
def sources(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for key, conn in CONNECTORS.items():
        row = _source_row(db, key)
        out.append(SourceOut(
            key=key, name=conn.name, site_url=conn.site_url, attribution=conn.attribution,
            enabled=conn.enabled(), last_status=row.last_status, last_error=row.last_error,
            last_count=row.last_count, last_attempt_at=_aware(row.last_attempt_at),
            last_fetched_at=_aware(row.last_fetched_at),
            next_refresh_allowed_at=_next_allowed(row, conn)))
    return out


@router.post("/search", response_model=SearchOut)
def search(body: SearchIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Country -> the sources that serve it -> store new vacancies -> list them."""
    if not valid_country(body.country):
        raise HTTPException(400, "Unknown country.")
    typed = body.query.strip()
    queries = [typed] if typed else derive_queries(db, user)
    if not queries:
        raise HTTPException(400, "Upload and analyse your CV, or type a job title to search.")
    location = body.location.strip()

    results, applied = [], []
    for key, conn in CONNECTORS.items():
        if not conn.enabled() or not conn.applies(body.country):
            continue
        applied.append(key)
        row = _source_row(db, key)
        nxt = _next_allowed(row, conn)
        if nxt and _now() < nxt:
            results.append(RefreshResult(
                source=key, status="skipped",
                message=f"Fetched recently. Next refresh allowed after {nxt.isoformat(timespec='minutes')}"))
            continue
        row.last_attempt_at = _now()
        try:
            items = _collect(conn, queries, body.country, location)
        except Exception as e:  # outage, bad response, network error: record and continue
            log.warning("connector %s failed: %s", key, _safe_error(e))
            row.last_status, row.last_error = "error", _safe_error(e)
            db.commit()
            results.append(RefreshResult(source=key, status="error",
                                         message="Source unavailable. Try again later."))
            continue
        stats = ingest(db, key, items)
        row.last_status, row.last_error = "ok", ""
        row.last_fetched_at, row.last_count = _now(), len(items)
        db.commit()
        log.info("connector %s ok: fetched=%d %s", key, len(items), stats)
        results.append(RefreshResult(source=key, status="ok", **stats))

    conds = [_visible(user)]
    cc = _country_cond(body.country, body.include_remote, user)
    if cc is not None:
        conds.append(cc)
    if typed:
        conds.append(or_(Job.title.icontains(typed, autoescape=True),
                         Job.company.icontains(typed, autoescape=True),
                         Job.description.icontains(typed, autoescape=True)))
    if location:
        conds.append(Job.location.icontains(location, autoescape=True))
    total = db.scalar(select(func.count()).select_from(Job).where(*conds)) or 0
    rows = db.scalars(select(Job).where(*conds)
                      .order_by(Job.posted_at.desc().nullslast(), Job.fetched_at.desc())
                      .limit(RESULT_LIMIT)).all()

    note = ""
    if body.country != "ALL" and not set(applied) - {"remotive"}:
        note = (f"No source for {COUNTRIES[body.country]} is enabled yet, so you only see worldwide remote "
                "jobs and vacancies you added. Add a free Jooble/Adzuna key in .env, an official RSS feed "
                "in app/sources.json, or use 'Import from link'.")
    return SearchOut(queries=queries, country=body.country, sources=results, note=note,
                     jobs=[_out(j, False) for j in rows], total=total)


@router.post("/import-url", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def import_url(body: ImportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Paste ONE vacancy link. Read only if the page allows it (robots.txt). Stored privately."""
    if body.country and not valid_country(body.country):
        raise HTTPException(400, "Unknown country.")
    try:
        item = importer.import_job_from_url(body.url.strip(), body.country)
    except importer.RobotsDisallowed as e:
        raise HTTPException(403, str(e))
    except importer.NoJobData as e:
        raise HTTPException(422, str(e))
    except importer.BadUrl as e:
        raise HTTPException(400, str(e))
    except httpx.HTTPError:
        raise HTTPException(400, "Could not open that link.")
    stats = ingest(db, "import", [item], owner_id=user.id)
    if stats["created"] != 1:
        raise HTTPException(409, "You already added this job")
    job = db.scalar(select(Job).where(Job.source_key == "import", Job.external_id == item.external_id))
    return _out(job, True)


@router.get("", response_model=JobList)
def list_jobs(
    q: str = Query("", max_length=100), location: str = Query("", max_length=100),
    country: str = Query("ALL", max_length=8), include_remote: bool = True,
    remote: bool | None = None, source: str = Query("", max_length=30),
    page: int = Query(1, ge=1, le=1000), limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    conds = [_visible(user)]
    cc = _country_cond(country, include_remote, user)
    if cc is not None:
        conds.append(cc)
    if q.strip():
        conds.append(or_(Job.title.icontains(q.strip(), autoescape=True),
                         Job.company.icontains(q.strip(), autoescape=True),
                         Job.description.icontains(q.strip(), autoescape=True)))
    if location.strip():
        conds.append(Job.location.icontains(location.strip(), autoescape=True))
    if remote is not None:
        conds.append(Job.is_remote == remote)
    if source:
        conds.append(Job.source_key == source)
    total = db.scalar(select(func.count()).select_from(Job).where(*conds)) or 0
    rows = db.scalars(select(Job).where(*conds)
                      .order_by(Job.posted_at.desc().nullslast(), Job.fetched_at.desc())
                      .offset((page - 1) * limit).limit(limit)).all()
    return JobList(items=[_out(j, False) for j in rows], total=total, page=page, limit=limit)


@router.post("/manual", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def add_manual(body: ManualJobIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if body.country and not valid_country(body.country):
        raise HTTPException(400, "Unknown country.")
    ext = uuid.uuid4().hex
    item = NormalizedJob(external_id=ext, title=body.title, company=body.company,
                         location=body.location, country=body.country, is_remote=body.is_remote,
                         job_type=body.job_type, salary_text=body.salary_text,
                         description=body.description, url=body.url)
    stats = ingest(db, "manual", [item], owner_id=user.id)
    if stats["created"] != 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already added this job")
    job = db.scalar(select(Job).where(Job.source_key == "manual", Job.external_id == ext))
    return _out(job, True)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    job = db.scalar(select(Job).where(Job.id == job_id, _visible(user)))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return _out(job, True)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_private_job(job_id: uuid.UUID, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    job = db.scalar(select(Job).where(Job.id == job_id, Job.owner_user_id == user.id,
                                      Job.source_key.in_(PRIVATE_SOURCES)))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    db.delete(job)
    db.commit()
