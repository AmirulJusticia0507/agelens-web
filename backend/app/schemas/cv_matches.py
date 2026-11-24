from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CvJobMatchResponse(BaseModel):
    job_posting_id: UUID
    job_title: str
    source_platform: str
    source_url: str | None
    match_percentage: float = Field(ge=0, le=100)
    matched_skills: list[str]
    summary_only: bool


class CvCompanyMatchResponse(BaseModel):
    company_id: UUID
    display_name: str
    match_percentage: float = Field(ge=0, le=100)
    matched_skills: list[str]
    jobs: list[CvJobMatchResponse]


class CvProfileMatchResponse(BaseModel):
    label: Literal["CV 1", "CV 2"]
    skills: list[str]
    jobs_considered: int = Field(ge=0)
    companies: list[CvCompanyMatchResponse]


class CvMatchResponse(BaseModel):
    profiles: list[CvProfileMatchResponse]
