import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.job import Job, JobSource
from app.models.user import User
from app.schemas.job import JobList, JobOut, ManualJobIn, RefreshResult, SourceOut
from app.services.connectors.base import JobConnector, NormalizedJob
from app.services.connectors.remotive import RemotiveConnector
from app.services.job_ingest import ingest

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
log = logging.getLogger("jobhunt.jobs")

CONNECTORS: dict[str, JobConnector] = {"remotive": RemotiveConnector()}
STALE_DAYS = 45
MIN_RETRY_AFTER_ERROR = timedelta(minutes=5)
SOURCE_INFO = {"manual": ("Added by you", "", "Added by you (unverified, check the official posting)")}
for _c in CONNECTORS.values():
    SOURCE_INFO[_c.key] = (_c.name, _c.site_url, _c.attribution)


def _aware(d: datetime | None) -> datetime | None:
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _visible(user: User):
    return or_(Job.owner_user_id.is_(None), Job.owner_user_id == user.id)


def _out(job: Job, full: bool) -> JobOut:
    name, _, attribution = SOURCE_INFO.get(job.source_key, (job.source_key, "", job.source_key))
    desc = job.description or ""
    if not full and len(desc) > 600:
        desc = desc[:600].rstrip() + "…"
    posted = _aware(job.posted_at)
    return JobOut(
        id=job.id, source_key=job.source_key, source_name=name, attribution=attribution,
        title=job.title, company=job.company, location=job.location, is_remote=job.is_remote,
        job_type=job.job_type, salary_text=job.salary_text, description=desc, url=job.url,
        tags=job.tags or [], posted_at=posted, fetched_at=_aware(job.fetched_at),
        is_stale=bool(posted and _now() - posted > timedelta(days=STALE_DAYS)),
        is_manual=job.source_key == "manual")


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


@router.get("/sources", response_model=list[SourceOut])
def sources(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for key, conn in CONNECTORS.items():
        row = _source_row(db, key)
        out.append(SourceOut(
            key=key, name=conn.name, site_url=conn.site_url, attribution=conn.attribution,
            last_status=row.last_status, last_error=row.last_error, last_count=row.last_count,
            last_attempt_at=_aware(row.last_attempt_at), last_fetched_at=_aware(row.last_fetched_at),
            next_refresh_allowed_at=_next_allowed(row, conn)))
    return out


@router.post("/refresh", response_model=list[RefreshResult])
def refresh(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch new vacancies from permitted sources. Rate-limited per source terms."""
    results = []
    for key, conn in CONNECTORS.items():
        row = _source_row(db, key)
        nxt = _next_allowed(row, conn)
        if nxt and _now() < nxt:
            results.append(RefreshResult(
                source=key, status="skipped",
                message=f"Fetched recently. Next refresh allowed after {nxt.isoformat(timespec='minutes')}"))
            continue
        row.last_attempt_at = _now()
        try:
            items = conn.fetch()
        except Exception as e:  # outage, bad response, network error: record and continue
            log.warning("connector %s failed: %s", key, type(e).__name__)
            row.last_status, row.last_error = "error", f"{type(e).__name__}: {e}"[:300]
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
    return results


@router.get("", response_model=JobList)
def list_jobs(
    q: str = Query("", max_length=100), location: str = Query("", max_length=100),
    remote: bool | None = None, source: str = Query("", max_length=30),
    page: int = Query(1, ge=1, le=1000), limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    conds = [_visible(user)]
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
    ext = uuid.uuid4().hex
    item = NormalizedJob(external_id=ext, title=body.title, company=body.company,
                         location=body.location, is_remote=body.is_remote,
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
def delete_manual(job_id: uuid.UUID, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    job = db.scalar(select(Job).where(Job.id == job_id, Job.owner_user_id == user.id,
                                      Job.source_key == "manual"))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    db.delete(job)
    db.commit()
