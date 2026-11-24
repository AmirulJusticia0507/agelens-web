from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_analysis_redis, get_session
from app.schemas.submissions import (
    JobPostingImportRequest,
    JobPostingImportResponse,
    JobPostingReportRequest,
    JobPostingReportResponse,
)
from app.services.analysis_queue import AnalysisRedis, enqueue_analysis
from app.services.ingestion import ingest_job_posting

router = APIRouter(prefix="/submissions", tags=["submissions"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
AnalysisRedisDependency = Annotated[AnalysisRedis, Depends(get_analysis_redis)]


@router.post(
    "/report",
    response_model=JobPostingReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_report(
    payload: JobPostingReportRequest,
    session: SessionDependency,
    redis: AnalysisRedisDependency,
) -> JobPostingReportResponse:
    try:
        result = await ingest_job_posting(
            session,
            company_name=payload.company_name,
            job_title=payload.job_title,
            job_level=payload.job_level,
            source_platform=payload.source_platform,
            source_url=payload.source_url,
            posted_date=payload.posted_date,
            raw_description=payload.raw_description,
            raw_metadata={
                "record_type": "job_posting",
                "vacancy_status": payload.vacancy_status,
                "listing_summary_only": payload.listing_summary_only,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    await session.commit()

    if result.job_posting.analysis_status == "pending":
        try:
            await enqueue_analysis(redis, result.job_posting.id)
        except RedisError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Report was saved but could not be queued. "
                    "Retry the request to enqueue its analysis."
                ),
            ) from exc

    return JobPostingReportResponse(
        job_posting_id=result.job_posting.id,
        analysis_status=result.job_posting.analysis_status,
        created=result.created,
    )


@router.post("/import", response_model=JobPostingImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_postings(
    payload: JobPostingImportRequest,
    session: SessionDependency,
    redis: AnalysisRedisDependency,
) -> JobPostingImportResponse:
    inserted = duplicates = queued = 0
    pending_ids = []
    for item in payload.postings:
        result = await ingest_job_posting(
            session,
            company_name=item.company_name,
            job_title=item.job_title,
            job_level=item.job_level,
            source_platform=item.source_platform,
            source_url=item.source_url,
            posted_date=item.posted_date,
            raw_description=item.raw_description,
            raw_metadata={
                "record_type": "job_posting",
                "vacancy_status": item.vacancy_status,
                "listing_summary_only": item.listing_summary_only,
            },
        )
        if result.created:
            inserted += 1
            pending_ids.append(result.job_posting.id)
        else:
            duplicates += 1
    await session.commit()
    for posting_id in pending_ids:
        try:
            await enqueue_analysis(redis, posting_id)
            queued += 1
        except RedisError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sebagian lowongan tersimpan, tetapi analisis gagal masuk antrean.",
            ) from exc
    return JobPostingImportResponse(
        total=len(payload.postings), inserted=inserted, duplicates=duplicates, queued=queued
    )
