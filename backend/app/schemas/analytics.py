from typing import Literal

from pydantic import BaseModel

RestrictionType = Literal["EXPLICIT", "IMPLICIT", "NONE"]


class RestrictionTypeCount(BaseModel):
    restriction_type: RestrictionType
    analyzed_jobs: int


class CategoryAnalytics(BaseModel):
    category: str | None
    analyzed_jobs: int
    restricted_jobs: int
    age_bias_rate_pct: float


class AnalyticsOverviewResponse(BaseModel):
    total_companies: int
    total_submissions: int
    analyzed_jobs: int
    restricted_jobs: int
    age_bias_rate_pct: float
    restriction_breakdown: list[RestrictionTypeCount]
    industry_breakdown: list[CategoryAnalytics]
    job_level_breakdown: list[CategoryAnalytics]
