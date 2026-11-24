from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.db.models import AgeAnalysis, Company, JobPosting
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    CategoryAnalytics,
    RestrictionType,
    RestrictionTypeCount,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
RESTRICTION_TYPES: tuple[RestrictionType, ...] = ("EXPLICIT", "IMPLICIT", "NONE")


def _rate_pct(restricted: int, analyzed: int) -> float:
    return round(restricted / analyzed * 100, 2) if analyzed else 0.0


def _category_rows(rows: list[tuple[str | None, int, int]]) -> list[CategoryAnalytics]:
    return [
        CategoryAnalytics(
            category=category,
            analyzed_jobs=analyzed,
            restricted_jobs=restricted,
            age_bias_rate_pct=_rate_pct(restricted, analyzed),
        )
        for category, analyzed, restricted in rows
    ]


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(
    session: SessionDependency,
) -> AnalyticsOverviewResponse:
    total_companies = int((await session.scalar(select(func.count(Company.id)))) or 0)
    total_submissions, analyzed_jobs, restricted_jobs = (
        await session.execute(
            select(
                func.count(JobPosting.id),
                func.count(AgeAnalysis.id),
                func.count(AgeAnalysis.id).filter(AgeAnalysis.has_age_restriction.is_(True)),
            ).outerjoin(AgeAnalysis, AgeAnalysis.job_posting_id == JobPosting.id)
        )
    ).one()
    analyzed_jobs = int(analyzed_jobs)
    restricted_jobs = int(restricted_jobs)

    restriction_counts = dict(
        (
            await session.execute(
                select(AgeAnalysis.restriction_type, func.count(AgeAnalysis.id)).group_by(
                    AgeAnalysis.restriction_type
                )
            )
        ).all()
    )
    industry_rows = (
        await session.execute(
            select(
                Company.industry,
                func.count(AgeAnalysis.id),
                func.count(AgeAnalysis.id).filter(AgeAnalysis.has_age_restriction.is_(True)),
            )
            .select_from(AgeAnalysis)
            .join(JobPosting, JobPosting.id == AgeAnalysis.job_posting_id)
            .outerjoin(Company, Company.id == JobPosting.company_id)
            .group_by(Company.industry)
            .order_by(
                func.count(AgeAnalysis.id)
                .filter(AgeAnalysis.has_age_restriction.is_(True))
                .desc(),
                Company.industry.asc(),
            )
        )
    ).all()
    job_level_rows = (
        await session.execute(
            select(
                JobPosting.job_level,
                func.count(AgeAnalysis.id),
                func.count(AgeAnalysis.id).filter(AgeAnalysis.has_age_restriction.is_(True)),
            )
            .select_from(AgeAnalysis)
            .join(JobPosting, JobPosting.id == AgeAnalysis.job_posting_id)
            .group_by(JobPosting.job_level)
            .order_by(
                func.count(AgeAnalysis.id)
                .filter(AgeAnalysis.has_age_restriction.is_(True))
                .desc(),
                JobPosting.job_level.asc(),
            )
        )
    ).all()

    return AnalyticsOverviewResponse(
        total_companies=total_companies,
        total_submissions=int(total_submissions),
        analyzed_jobs=analyzed_jobs,
        restricted_jobs=restricted_jobs,
        age_bias_rate_pct=_rate_pct(restricted_jobs, analyzed_jobs),
        restriction_breakdown=[
            RestrictionTypeCount(
                restriction_type=restriction_type,
                analyzed_jobs=int(restriction_counts.get(restriction_type, 0)),
            )
            for restriction_type in RESTRICTION_TYPES
        ],
        industry_breakdown=_category_rows(
            [(row[0], int(row[1]), int(row[2])) for row in industry_rows]
        ),
        job_level_breakdown=_category_rows(
            [(row[0], int(row[1]), int(row[2])) for row in job_level_rows]
        ),
    )
