from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_session
from app.db.models import Company, JobPosting
from app.schemas.companies import CompanyDetailResponse, CompanyPageResponse

router = APIRouter(prefix="/companies", tags=["companies"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=CompanyPageResponse)
async def list_companies(
    session: SessionDependency,
    q: str | None = Query(default=None, max_length=100),
    industry: str | None = Query(default=None, max_length=100),
    city: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CompanyPageResponse:
    filters = []

    if q and q.strip():
        search_term = q.strip()
        pattern = f"%{_escape_like(search_term)}%"
        filters.append(
            or_(
                Company.display_name.ilike(pattern, escape="\\"),
                Company.normalized_name.ilike(pattern, escape="\\"),
                func.to_tsvector("indonesian", Company.display_name).op("@@")(
                    func.plainto_tsquery("indonesian", search_term)
                ),
                func.similarity(Company.normalized_name, search_term) >= 0.3,
            )
        )

    if industry and industry.strip():
        filters.append(
            Company.industry.ilike(f"%{_escape_like(industry.strip())}%", escape="\\")
        )

    if city and city.strip():
        filters.append(Company.city.ilike(f"%{_escape_like(city.strip())}%", escape="\\"))

    total = await session.scalar(select(func.count(Company.id)).where(*filters))
    companies = await session.scalars(
        select(Company)
        .where(*filters)
        .order_by(Company.age_bias_score.desc(), Company.display_name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    total_count = int(total or 0)

    return CompanyPageResponse(
        items=list(companies),
        page=page,
        page_size=page_size,
        total=total_count,
        pages=ceil(total_count / page_size),
    )


@router.get("/{company_id}", response_model=CompanyDetailResponse)
async def get_company(
    company_id: UUID,
    session: SessionDependency,
) -> CompanyDetailResponse:
    result = await session.scalars(
        select(Company)
        .options(selectinload(Company.job_postings).selectinload(JobPosting.analysis))
        .where(Company.id == company_id)
    )
    company = result.one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    return CompanyDetailResponse.model_validate(company)
