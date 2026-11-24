from collections.abc import Callable
from decimal import Decimal
from typing import Any, ClassVar
from uuid import UUID

from arq import Retry
from arq.connections import RedisSettings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models import AgeAnalysis, Company, JobPosting
from app.db.session import SessionFactory
from app.schemas.analysis import AgeAnalysisResult
from app.services.age_analysis import (
    AnalysisConfigurationError,
    AnalysisProviderError,
    OpenAICompatibleAgeAnalyzer,
)

MAX_ANALYSIS_TRIES = 3


class JobPostingNotFoundError(LookupError):
    pass


async def _load_job(session: AsyncSession, job_posting_id: UUID) -> JobPosting | None:
    return await session.scalar(
        select(JobPosting)
        .options(selectinload(JobPosting.analysis))
        .where(JobPosting.id == job_posting_id)
        .with_for_update()
    )


async def _mark_failed(
    session_factory: async_sessionmaker[AsyncSession],
    job_posting_id: UUID,
    error: str,
    *,
    retrying: bool,
) -> None:
    async with session_factory() as session:
        job_posting = await _load_job(session, job_posting_id)
        if job_posting is None:
            raise JobPostingNotFoundError(f"Job posting {job_posting_id} was not found")
        if job_posting.analysis is not None:
            job_posting.analysis_status = "completed"
            job_posting.analysis_error = None
        else:
            job_posting.analysis_status = "pending" if retrying else "failed"
            job_posting.analysis_error = error[:2000]
        await session.commit()


async def _save_analysis(
    session_factory: async_sessionmaker[AsyncSession],
    job_posting_id: UUID,
    result: AgeAnalysisResult,
    model_used: str | None,
) -> None:
    async with session_factory() as session:
        job_posting = await _load_job(session, job_posting_id)
        if job_posting is None:
            raise JobPostingNotFoundError(f"Job posting {job_posting_id} was not found")
        if job_posting.analysis is None:
            job_posting.analysis = AgeAnalysis(
                has_age_restriction=result.has_age_restriction,
                restriction_type=result.restriction_type.value,
                min_age=result.min_age,
                max_age=result.max_age,
                extracted_evidence=result.extracted_evidence,
                ai_reasoning=result.ai_reasoning,
                confidence_score=Decimal(str(result.confidence_score)),
                model_used=model_used,
            )
            await session.flush()

            if job_posting.company_id is not None:
                company = await session.scalar(
                    select(Company)
                    .where(Company.id == job_posting.company_id)
                    .with_for_update()
                )
                if company is not None:
                    total, restricted = (
                        await session.execute(
                            select(
                                func.count(AgeAnalysis.id),
                                func.count(AgeAnalysis.id).filter(
                                    AgeAnalysis.has_age_restriction.is_(True)
                                ),
                            )
                            .select_from(JobPosting)
                            .join(AgeAnalysis, AgeAnalysis.job_posting_id == JobPosting.id)
                            .where(JobPosting.company_id == company.id)
                        )
                    ).one()
                    company.total_jobs_analyzed = total
                    company.age_restricted_jobs_count = restricted
                    company.age_bias_score = (
                        (Decimal(restricted) * Decimal(100) / Decimal(total)).quantize(
                            Decimal("0.01")
                        )
                        if total
                        else Decimal("0.00")
                    )

        job_posting.analysis_status = "completed"
        job_posting.analysis_error = None
        await session.commit()


async def analyze_job_posting(ctx: dict[str, Any], job_posting_id: str) -> None:
    posting_id = UUID(job_posting_id)
    session_factory: async_sessionmaker[AsyncSession] = ctx.get(
        "session_factory", SessionFactory
    )
    async with session_factory() as session:
        job_posting = await _load_job(session, posting_id)
        if job_posting is None:
            raise JobPostingNotFoundError(f"Job posting {posting_id} was not found")
        if job_posting.analysis is not None:
            job_posting.analysis_status = "completed"
            job_posting.analysis_error = None
            await session.commit()
            return

        job_posting.analysis_status = "processing"
        job_posting.analysis_attempts += 1
        job_posting.analysis_error = None
        description = job_posting.raw_description
        await session.commit()

    analyzer = ctx.get("analyzer") or OpenAICompatibleAgeAnalyzer()
    try:
        result = await analyzer.analyze(description)
    except AnalysisConfigurationError as exc:
        await _mark_failed(session_factory, posting_id, str(exc), retrying=False)
        raise
    except AnalysisProviderError as exc:
        retrying = exc.retryable and int(ctx.get("job_try", 1)) < MAX_ANALYSIS_TRIES
        await _mark_failed(session_factory, posting_id, str(exc), retrying=retrying)
        if retrying:
            raise Retry(defer=5) from exc
        raise

    await _save_analysis(
        session_factory,
        posting_id,
        result,
        get_settings().llm_model,
    )


class WorkerSettings:
    functions: ClassVar[list[Callable[..., Any]]] = [analyze_job_posting]
    redis_settings: ClassVar[RedisSettings] = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries: ClassVar[int] = MAX_ANALYSIS_TRIES
    job_timeout: ClassVar[int] = 90
