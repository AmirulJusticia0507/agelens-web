"""Schemas for dynamic job search and AI assessment."""

from pydantic import BaseModel, Field

from app.schemas.cv_matches import CvJobAiAssessment


class JobSearchFilters(BaseModel):
    """Filters for job search queries."""
    
    location: str | None = None
    job_type: str | None = None  # full-time, remote, freelance, etc.
    experience_level: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    keywords: str | None = None


class JobSearchResult(BaseModel):
    """Result for a single job in search results."""
    
    job_title: str
    company_name: str
    source_platform: str
    source_url: str | None = None
    keyword_match_percentage: float = Field(ge=0, le=100)
    matched_skills: list[str]
    ai_assessment: CvJobAiAssessment | None = None
    analysis_status: str = Field(default="success")  # success, timeout, error


class JobSearchResponse(BaseModel):
    """Response from search-and-analyze endpoint."""
    
    cv_skills: list[str]
    results: list[JobSearchResult]
    search_duration_ms: int = Field(ge=0)
    warnings: list[str] | None = None
