import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from arq import Retry
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.db.models import Company, JobPosting
from app.schemas.analysis import AgeAnalysisResult
from app.services.age_analysis import AnalysisProviderError
from app.services.analysis_queue import enqueue_analysis
from app.services.ingestion import ingest_job_posting
from app.worker import MAX_ANALYSIS_TRIES, analyze_job_posting

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def migrated_database_url() -> str:
    database_url = get_settings().database_url

    async def can_connect() -> None:
        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

    try:
        asyncio.run(can_connect())
    except (OperationalError, OSError) as exc:
        pytest.skip(f"PostgreSQL is not reachable: {exc}")

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(config, "head")
    return database_url


@pytest.fixture
async def session_factory(
    migrated_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated_database_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


class FakeRedis:
    def __init__(self, result: object | None) -> None:
        self.result = result
        self.call: tuple[str, tuple[object, ...], dict[str, object]] | None = None

    async def enqueue_job(
        self,
        function_name: str,
        *args: object,
        **kwargs: object,
    ) -> object | None:
        self.call = (function_name, args, kwargs)
        return self.result


class SuccessfulAnalyzer:
    async def analyze(self, _: str) -> AgeAnalysisResult:
        return AgeAnalysisResult(
            has_age_restriction=True,
            restriction_type="EXPLICIT",
            max_age=30,
            extracted_evidence="Usia maksimal 30 tahun",
            ai_reasoning="Batas usia disebut secara eksplisit.",
            confidence_score=0.95,
        )


class RetryableFailureAnalyzer:
    async def analyze(self, _: str) -> AgeAnalysisResult:
        raise AnalysisProviderError("temporary provider error", retryable=True)


async def create_posting(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, UUID | None]:
    async with session_factory() as session:
        result = await ingest_job_posting(
            session,
            company_name=f"Queue Test {uuid4().hex}",
            job_title="Finance Associate",
            source_platform="user_report",
            raw_description="Usia maksimal 30 tahun.",
        )
        await session.commit()
        return result.job_posting.id, result.job_posting.company_id


async def delete_posting(
    session_factory: async_sessionmaker[AsyncSession],
    posting_id: UUID,
    company_id: UUID | None,
) -> None:
    async with session_factory() as session:
        await session.execute(delete(JobPosting).where(JobPosting.id == posting_id))
        if company_id is not None:
            await session.execute(delete(Company).where(Company.id == company_id))
        await session.commit()


@pytest.mark.asyncio
async def test_enqueue_analysis_uses_deterministic_job_id() -> None:
    posting_id = uuid4()
    redis = FakeRedis(result=object())

    enqueued = await enqueue_analysis(redis, posting_id)

    assert enqueued is True
    assert redis.call == (
        "analyze_job_posting",
        (str(posting_id),),
        {"_job_id": f"age-analysis:{posting_id}"},
    )


@pytest.mark.asyncio
async def test_enqueue_analysis_reports_duplicate_job() -> None:
    redis = FakeRedis(result=None)

    enqueued = await enqueue_analysis(redis, uuid4())

    assert enqueued is False


@pytest.mark.asyncio
async def test_worker_persists_analysis_and_company_metrics(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    posting_id, company_id = await create_posting(session_factory)
    try:
        await analyze_job_posting(
            {"analyzer": SuccessfulAnalyzer(), "session_factory": session_factory},
            str(posting_id),
        )

        async with session_factory() as session:
            posting = await session.scalar(
                select(JobPosting)
                .options(selectinload(JobPosting.analysis))
                .where(JobPosting.id == posting_id)
            )
            company = await session.get(Company, company_id)

            assert posting is not None
            assert posting.analysis_status == "completed"
            assert posting.analysis_attempts == 1
            assert posting.analysis is not None
            assert posting.analysis.model_used == get_settings().llm_model
            assert company is not None
            assert company.total_jobs_analyzed == 1
            assert company.age_restricted_jobs_count == 1
            assert float(company.age_bias_score) == 100.0
    finally:
        await delete_posting(session_factory, posting_id, company_id)


@pytest.mark.asyncio
async def test_worker_retries_transient_provider_failures(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    posting_id, company_id = await create_posting(session_factory)
    try:
        with pytest.raises(Retry):
            await analyze_job_posting(
                {
                    "analyzer": RetryableFailureAnalyzer(),
                    "job_try": 1,
                    "session_factory": session_factory,
                },
                str(posting_id),
            )

        async with session_factory() as session:
            posting = await session.get(JobPosting, posting_id)
            assert posting is not None
            assert posting.analysis_status == "pending"
            assert posting.analysis_attempts == 1
            assert posting.analysis_error == "temporary provider error"

        with pytest.raises(AnalysisProviderError):
            await analyze_job_posting(
                {
                    "analyzer": RetryableFailureAnalyzer(),
                    "job_try": MAX_ANALYSIS_TRIES,
                    "session_factory": session_factory,
                },
                str(posting_id),
            )

        async with session_factory() as session:
            posting = await session.get(JobPosting, posting_id)
            assert posting is not None
            assert posting.analysis_status == "failed"
            assert posting.analysis_attempts == 2
    finally:
        await delete_posting(session_factory, posting_id, company_id)
