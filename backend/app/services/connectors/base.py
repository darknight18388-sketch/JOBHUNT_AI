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
    country: str = ""  # ISO code, "ANY" for worldwide remote, "" unknown
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
    uses_query: bool = False       # True: fetch() is called once per search query

    def enabled(self) -> bool:     # e.g. API key configured
        return True

    def applies(self, country: str) -> bool:  # does this source serve the selected country?
        return True

    @abstractmethod
    def fetch(self, query: str = "", country: str = "ALL", location: str = "") -> list[NormalizedJob]: ...
