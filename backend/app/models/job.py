import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint, Uuid)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def _now():
    return datetime.now(timezone.utc)


class JobSource(Base):
    __tablename__ = "job_sources"

    key: Mapped[str] = mapped_column(String(30), primary_key=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="never")
    last_error: Mapped[str] = mapped_column(String(300), default="")
    last_count: Mapped[int] = mapped_column(Integer, default=0)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source_key", "external_id", name="uq_job_source_ext"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(String(30), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    job_type: Mapped[str] = mapped_column(String(50), default="")
    salary_text: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(1000), default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    dedupe_key: Mapped[str] = mapped_column(String(40), index=True)
