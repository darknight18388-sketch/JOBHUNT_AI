"""Connector interface: every job source returns NormalizedJob records.
Only add sources whose terms allow it (official API / feed / permission)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NormalizedJob:
    external_id: str
    title: str
    company: str = ""
    location: str = ""
    is_remote: bool = False
    job_type: str = ""
    salary_text: str = ""
    description: str = ""
    url: str = ""
    tags: list[str] = field(default_factory=list)
    posted_at: datetime | None = None


class JobConnector(ABC):
    key: str
    name: str
    site_url: str
    attribution: str
    min_interval_hours: float = 6  # be polite to the source

    @abstractmethod
    def fetch(self) -> list[NormalizedJob]: ...
