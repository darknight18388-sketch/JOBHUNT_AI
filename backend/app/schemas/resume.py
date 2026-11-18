import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]
Medium = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    original_filename: str
    file_type: str
    size_bytes: int
    created_at: datetime


class ProfileData(BaseModel):
    full_name: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=40)
    skills: list[Short] = Field(default_factory=list, max_length=60)
    education: list[Medium] = Field(default_factory=list, max_length=30)
    experience: list[Medium] = Field(default_factory=list, max_length=30)
    certifications: list[Medium] = Field(default_factory=list, max_length=30)
    languages: list[Short] = Field(default_factory=list, max_length=15)


class ProfileEdit(ProfileData):
    confirmed: bool = False


class AnalysisOut(ProfileData):
    resume_id: uuid.UUID
    confirmed: bool
    uncertain_fields: list[str] = Field(default_factory=list)
