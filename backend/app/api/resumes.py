import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.database.session import get_db
from app.models.resume import Resume, ResumeAnalysis
from app.models.user import User
from app.parsers.cv_parser import parse_cv
from app.parsers.text_extract import CVParseError, extract_text
from app.schemas.resume import AnalysisOut, ProfileEdit, ResumeOut

router = APIRouter(prefix="/api/resumes", tags=["resumes"])
log = logging.getLogger("jobhunt.resumes")  # never log CV contents

ALLOWED = {".pdf": b"%PDF-", ".docx": b"PK\x03\x04"}
PROFILE_KEYS = ["full_name", "email", "phone", "skills", "education", "experience",
                "certifications", "languages"]


def _upload_dir() -> Path:
    d = Path(settings.upload_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _own(db: Session, user: User, rid: uuid.UUID) -> Resume:
    r = db.scalar(select(Resume).where(Resume.id == rid, Resume.user_id == user.id))
    if r is None:  # 404 (not 403) so other users' IDs are not revealed
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    return r


def _analysis_out(a: ResumeAnalysis) -> AnalysisOut:
    d = a.data or {}
    return AnalysisOut(resume_id=a.resume_id, confirmed=a.confirmed,
                       uncertain_fields=d.get("uncertain_fields", []),
                       **{k: d.get(k, "" if k in ("full_name", "email", "phone") else [])
                          for k in PROFILE_KEYS})


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload(file: UploadFile = File(...), user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    name = Path(file.filename or "").name[:200]
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PDF or DOCX files are allowed")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(413,
                                f"File too large (max {settings.max_upload_mb} MB)")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    if not bytes(data).startswith(ALLOWED[ext]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "File content does not match its extension")

    stored = f"{uuid.uuid4().hex}{ext}"
    path = _upload_dir() / stored
    path.write_bytes(bytes(data))
    path.chmod(0o600)
    try:
        text = extract_text(path, ext)
    except CVParseError as e:
        path.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    resume = Resume(user_id=user.id, original_filename=name, stored_name=stored,
                    file_type=ext.lstrip("."), size_bytes=len(data), extracted_text=text)
    db.add(resume)
    db.commit()
    db.refresh(resume)
    log.info("resume uploaded user=%s resume=%s bytes=%d", user.id, resume.id, len(data))
    return resume


@router.get("", response_model=list[ResumeOut])
def list_resumes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Resume).where(Resume.user_id == user.id)
                      .order_by(Resume.created_at.desc())).all()


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: uuid.UUID, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    return _own(db, user, resume_id)


@router.post("/{resume_id}/analyze", response_model=AnalysisOut)
def analyze(resume_id: uuid.UUID, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    resume = _own(db, user, resume_id)
    data = parse_cv(resume.extracted_text)
    a = db.scalar(select(ResumeAnalysis).where(ResumeAnalysis.resume_id == resume.id))
    if a is None:
        a = ResumeAnalysis(resume_id=resume.id, data=data, confirmed=False)
        db.add(a)
    else:
        a.data, a.confirmed = data, False
    db.commit()
    db.refresh(a)
    return _analysis_out(a)


@router.get("/{resume_id}/analysis", response_model=AnalysisOut)
def get_analysis(resume_id: uuid.UUID, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    resume = _own(db, user, resume_id)
    a = db.scalar(select(ResumeAnalysis).where(ResumeAnalysis.resume_id == resume.id))
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not analysed yet")
    return _analysis_out(a)


@router.put("/{resume_id}/analysis", response_model=AnalysisOut)
def save_analysis(resume_id: uuid.UUID, body: ProfileEdit,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = _own(db, user, resume_id)
    a = db.scalar(select(ResumeAnalysis).where(ResumeAnalysis.resume_id == resume.id))
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not analysed yet")
    new = body.model_dump(exclude={"confirmed"})
    new["uncertain_fields"] = [] if body.confirmed else (a.data or {}).get("uncertain_fields", [])
    a.data, a.confirmed = new, body.confirmed
    db.commit()
    db.refresh(a)
    return _analysis_out(a)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: uuid.UUID, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    resume = _own(db, user, resume_id)
    (_upload_dir() / resume.stored_name).unlink(missing_ok=True)
    a = db.scalar(select(ResumeAnalysis).where(ResumeAnalysis.resume_id == resume.id))
    if a:
        db.delete(a)
    db.delete(resume)
    db.commit()
