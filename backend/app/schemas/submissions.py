from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class JobPostingReportRequest(BaseModel):
    company_name: str | None = Field(default=None, max_length=255)
    job_title: str = Field(min_length=1, max_length=255)
    job_level: str | None = Field(default=None, max_length=50)
    source_platform: str = Field(default="user_report", min_length=1, max_length=50)
    source_url: str | None = Field(default=None, max_length=2048)
    posted_date: date | None = None
    raw_description: str = Field(min_length=1, max_length=20000)
    vacancy_status: Literal["open", "unverified"] = "unverified"
    listing_summary_only: bool = True

    @field_validator("job_title", "source_platform", "raw_description")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field must not be empty")
        return normalized

    @field_validator("company_name", "job_level", "source_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class JobPostingReportResponse(BaseModel):
    job_posting_id: UUID
    analysis_status: Literal["pending", "processing", "completed", "failed"]
    created: bool


class JobPostingImportRequest(BaseModel):
    postings: list[JobPostingReportRequest] = Field(min_length=1, max_length=100)


class JobPostingImportResponse(BaseModel):
    total: int
    inserted: int
    duplicates: int
    queued: int
