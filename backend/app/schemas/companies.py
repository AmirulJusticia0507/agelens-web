from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgeAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    has_age_restriction: bool
    restriction_type: str
    min_age: int | None
    max_age: int | None
    extracted_evidence: str | None
    ai_reasoning: str | None
    confidence_score: float | None
    model_used: str | None
    analyzed_at: datetime


class JobPostingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_title: str
    job_level: str | None
    source_platform: str
    source_url: str | None
    raw_description: str
    posted_date: date | None
    scraped_at: datetime
    analysis_status: Literal["pending", "processing", "completed", "failed"]
    analysis: AgeAnalysisResponse | None


class CompanySummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    normalized_name: str
    display_name: str
    industry: str | None
    city: str | None
    total_jobs_analyzed: int
    age_restricted_jobs_count: int
    age_bias_score: float
    created_at: datetime
    updated_at: datetime


class CompanyDetailResponse(CompanySummaryResponse):
    job_postings: list[JobPostingResponse]


class CompanyPageResponse(BaseModel):
    items: list[CompanySummaryResponse]
    page: int
    page_size: int
    total: int
    pages: int
