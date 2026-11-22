import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class JobOut(BaseModel):
    id: uuid.UUID
    source_key: str
    source_name: str
    attribution: str
    title: str
    company: str
    location: str
    country: str
    is_remote: bool
    job_type: str
    salary_text: str
    description: str
    url: str
    tags: list[str]
    posted_at: datetime | None
    fetched_at: datetime
    is_stale: bool
    is_manual: bool  # added/imported by the user: private and unverified


class JobList(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    limit: int


class SourceOut(BaseModel):
    key: str
    name: str
    site_url: str
    attribution: str
    enabled: bool
    last_status: str
    last_error: str
    last_count: int
    last_attempt_at: datetime | None
    last_fetched_at: datetime | None
    next_refresh_allowed_at: datetime | None


class RefreshResult(BaseModel):
    source: str
    status: str  # ok | skipped | error
    created: int = 0
    updated: int = 0
    duplicates: int = 0
    message: str = ""


class SearchIn(BaseModel):
    query: str = Field(default="", max_length=100)  # blank = build searches from your CV
    country: str = Field(default="ALL", max_length=8)
    location: str = Field(default="", max_length=100)
    include_remote: bool = True


class SearchOut(BaseModel):
    queries: list[str]
    country: str
    sources: list[RefreshResult]
    note: str = ""
    jobs: list[JobOut]
    total: int


class ImportIn(BaseModel):
    url: str = Field(min_length=8, max_length=1000)
    country: str = Field(default="", max_length=8)


class ManualJobIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    company: str = Field(min_length=1, max_length=200)
    location: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=8)
    is_remote: bool = False
    job_type: str = Field(default="", max_length=50)
    salary_text: str = Field(default="", max_length=200)
    url: str = Field(default="", max_length=1000)
    description: str = Field(min_length=10, max_length=20000)

    @field_validator("title", "company", "location", "job_type", "salary_text", "description")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str) -> str:
        v = v.strip()
        if v and not v.lower().startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class CareerIn(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=8, max_length=1000)
    country: str = Field(default="", max_length=8)


class CareerOut(BaseModel):
    id: uuid.UUID
    company: str
    url: str
    ats: str
    country: str
    last_status: str
    last_error: str
    last_count: int
    last_fetched_at: datetime | None
    next_refresh_allowed_at: datetime | None
