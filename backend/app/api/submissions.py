from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_analysis_redis, get_session
from app.schemas.submissions import JobPostingReportRequest, JobPostingReportResponse
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
