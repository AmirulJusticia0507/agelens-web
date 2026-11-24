import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from redis.exceptions import RedisError
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from app.api import cv_matches as cv_matches_api
from app.api.dependencies import get_analysis_redis, get_session
from app.config import get_settings
from app.db.models import AgeAnalysis, Company, JobPosting
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parents[1]


class FakeAnalysisRedis:
    def __init__(self) -> None:
        self.fail = False
        self.jobs: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    async def enqueue_job(
        self,
        function_name: str,
        *args: object,
        **kwargs: object,
    ) -> object | None:
        self.jobs.append((function_name, args, kwargs))
        if self.fail:
            raise RedisError("Redis unavailable")
        return object()


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
async def api(
    migrated_database_url: str,
) -> AsyncIterator[tuple[AsyncClient, AsyncSession]]:
    engine = create_async_engine(migrated_database_url)
    connection: AsyncConnection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_session, None)
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest.fixture
async def submission_api(
    api: tuple[AsyncClient, AsyncSession],
) -> AsyncIterator[tuple[AsyncClient, AsyncSession, FakeAnalysisRedis]]:
    client, session = api
    redis = FakeAnalysisRedis()
    app.dependency_overrides[get_analysis_redis] = lambda: redis
    try:
        yield client, session, redis
    finally:
        app.dependency_overrides.pop(get_analysis_redis, None)


def unique_name(name: str) -> str:
    return f"{name}-{uuid4().hex}"


@pytest.mark.asyncio
async def test_list_companies_filters_and_paginates(
    api: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api
    normalized_name = unique_name("sinar-terang")
    company = Company(
        normalized_name=normalized_name,
        display_name="PT Sinar Terang",
        industry="Teknologi",
        city="Bandung",
        total_jobs_analyzed=2,
        age_restricted_jobs_count=1,
        age_bias_score=Decimal("50.00"),
    )
    session.add(company)
    session.add(
        Company(
            normalized_name=unique_name("sinar-terang-2"),
            display_name="Sinar Terang Kedua",
            industry="Teknologi",
            city="Bandung",
            age_bias_score=Decimal("25.00"),
        )
    )
    await session.flush()

    response = await client.get(
        "/api/v1/companies",
        params={"q": "sinar", "industry": "teknologi", "city": "bandung", "page_size": 1},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["pages"] == 2
    assert response.json()["items"][0]["id"] == str(company.id)
    assert response.json()["items"][0]["age_bias_score"] == 50.0

    next_page = await client.get(
        "/api/v1/companies",
        params={
            "q": "sinar",
            "industry": "teknologi",
            "city": "bandung",
            "page": 2,
            "page_size": 1,
        },
    )

    assert next_page.status_code == 200
    assert next_page.json()["items"][0]["display_name"] == "Sinar Terang Kedua"


@pytest.mark.asyncio
async def test_list_companies_treats_search_wildcards_as_literals(
    api: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api
    session.add(
        Company(
            normalized_name=unique_name("all-companies"),
            display_name="All Companies",
        )
    )
    await session.flush()

    response = await client.get("/api/v1/companies", params={"q": "%"})

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_get_company_includes_jobs_and_analysis(
    api: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api
    company = Company(
        normalized_name=unique_name("detail-company"),
        display_name="Detail Company",
    )
    job = JobPosting(
        job_title="Staff Accountant",
        source_platform="user_report",
        source_url="https://example.test/jobs/123",
        content_hash=uuid4().hex,
        raw_description="Usia maksimal 28 tahun",
    )
    job.analysis = AgeAnalysis(
        has_age_restriction=True,
        restriction_type="EXPLICIT",
        max_age=28,
        extracted_evidence="Usia maksimal 28 tahun",
        confidence_score=Decimal("0.980"),
    )
    company.job_postings.append(job)
    session.add(company)
    await session.flush()

    response = await client.get(f"/api/v1/companies/{company.id}")

    assert response.status_code == 200
    assert response.json()["job_postings"][0]["analysis"]["max_age"] == 28
    assert response.json()["job_postings"][0]["analysis"]["extracted_evidence"] == (
        "Usia maksimal 28 tahun"
    )
    assert response.json()["job_postings"][0]["source_url"] == (
        "https://example.test/jobs/123"
    )
    assert response.json()["job_postings"][0]["analysis_status"] == "pending"


@pytest.mark.asyncio
async def test_get_company_returns_not_found_for_unknown_id(
    api: tuple[AsyncClient, AsyncSession],
) -> None:
    client, _ = api

    response = await client.get(f"/api/v1/companies/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Company not found"}


@pytest.mark.asyncio
async def test_compare_cv_uploads_returns_separate_company_matches(
    api: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api
    react_company = Company(
        normalized_name=unique_name("cv-match-react"),
        display_name="React Company",
    )
    cloud_company = Company(
        normalized_name=unique_name("cv-match-cloud"),
        display_name="Cloud Company",
    )
    react_job = JobPosting(
        job_title="React Engineer",
        source_platform="test",
        content_hash=uuid4().hex,
        raw_description="React and Python.",
        raw_metadata={"record_type": "job_posting"},
    )
    cloud_job = JobPosting(
        job_title="Cloud Engineer",
        source_platform="test",
        content_hash=uuid4().hex,
        raw_description="AWS and Docker.",
        raw_metadata={"record_type": "job_posting"},
    )
    react_company.job_postings.append(react_job)
    cloud_company.job_postings.append(cloud_job)
    session.add_all([react_company, cloud_company])
    await session.flush()

    def fake_extract_cv_text(content: bytes) -> str:
        if content == b"%PDF-cv-one":
            return "React Python; contact private@example.test"
        return "AWS Docker; contact private@example.test"

    monkeypatch.setattr(cv_matches_api, "extract_cv_text", fake_extract_cv_text)
    response = await client.post(
        "/api/v1/cv-matches/analyze",
        files=[
            ("cv_a", ("cv-one.pdf", b"%PDF-cv-one", "application/pdf")),
            ("cv_b", ("cv-two.pdf", b"%PDF-cv-two", "application/pdf")),
        ],
    )

    assert response.status_code == 200
    profiles = response.json()["profiles"]
    assert profiles[0]["label"] == "CV 1"
    assert profiles[0]["skills"] == ["React", "Python"]
    cv_one_companies = {company["display_name"] for company in profiles[0]["companies"]}
    assert "React Company" in cv_one_companies
    assert "Cloud Company" not in cv_one_companies
    assert profiles[1]["label"] == "CV 2"
    assert profiles[1]["skills"] == ["AWS", "Docker"]
    cv_two_companies = {company["display_name"] for company in profiles[1]["companies"]}
    assert "Cloud Company" in cv_two_companies
    assert "React Company" not in cv_two_companies
    assert "private@example.test" not in response.text


@pytest.mark.asyncio
async def test_compare_cv_upload_accepts_only_required_first_cv(
    api: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = api
    monkeypatch.setattr(cv_matches_api, "extract_cv_text", lambda _: "React Python")

    response = await client.post(
        "/api/v1/cv-matches/analyze",
        files=[("cv_a", ("cv-one.pdf", b"%PDF-cv-one", "application/pdf"))],
    )

    assert response.status_code == 200
    profiles = response.json()["profiles"]
    assert len(profiles) == 1
    assert profiles[0]["label"] == "CV 1"
    assert profiles[0]["skills"] == ["React", "Python"]


@pytest.mark.asyncio
async def test_compare_cv_upload_rejects_oversized_file(
    api: tuple[AsyncClient, AsyncSession],
) -> None:
    client, _ = api
    oversized = b"%PDF-" + b"x" * cv_matches_api.MAX_CV_FILE_BYTES

    response = await client.post(
        "/api/v1/cv-matches/analyze",
        files=[
            ("cv_a", ("cv-one.pdf", oversized, "application/pdf")),
            ("cv_b", ("cv-two.pdf", b"%PDF-cv-two", "application/pdf")),
        ],
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Ukuran setiap file CV maksimal 8 MB."


@pytest.mark.asyncio
async def test_submit_report_stores_posting_and_enqueues_analysis(
    submission_api: tuple[AsyncClient, AsyncSession, FakeAnalysisRedis],
) -> None:
    client, session, redis = submission_api

    response = await client.post(
        "/api/v1/submissions/report",
        json={
            "company_name": "PT Contoh Kerja",
            "job_title": "Finance Associate",
            "source_platform": "company_site",
            "source_url": "https://example.test/jobs/finance",
            "posted_date": "2025-01-15",
            "raw_description": "Usia maksimal 30 tahun.",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["analysis_status"] == "pending"
    assert body["created"] is True
    posting = await session.get(JobPosting, body["job_posting_id"])
    assert posting is not None
    assert posting.source_platform == "company_site"
    assert posting.source_url == "https://example.test/jobs/finance"
    assert posting.posted_date.isoformat() == "2025-01-15"
    assert redis.jobs == [
        (
            "analyze_job_posting",
            (body["job_posting_id"],),
            {"_job_id": f"age-analysis:{body['job_posting_id']}"},
        )
    ]


@pytest.mark.asyncio
async def test_submit_report_queue_failure_can_be_retried(
    submission_api: tuple[AsyncClient, AsyncSession, FakeAnalysisRedis],
) -> None:
    client, session, redis = submission_api
    redis.fail = True
    report = {
        "job_title": "Accountant",
        "raw_description": "Pengalaman akuntansi minimal dua tahun.",
    }

    failed_response = await client.post("/api/v1/submissions/report", json=report)

    assert failed_response.status_code == 503
    assert "Report was saved" in failed_response.json()["detail"]
    redis.fail = False

    retry_response = await client.post("/api/v1/submissions/report", json=report)

    assert retry_response.status_code == 202
    assert retry_response.json()["created"] is False
    posting = await session.get(JobPosting, retry_response.json()["job_posting_id"])
    assert posting is not None
    assert posting.analysis_status == "pending"
    assert len(redis.jobs) == 2


@pytest.mark.asyncio
async def test_submit_report_rejects_empty_job_text(
    submission_api: tuple[AsyncClient, AsyncSession, FakeAnalysisRedis],
) -> None:
    client, _, redis = submission_api

    response = await client.post(
        "/api/v1/submissions/report",
        json={"job_title": "  ", "raw_description": "Deskripsi."},
    )

    assert response.status_code == 422
    assert redis.jobs == []


@pytest.mark.asyncio
async def test_analytics_overview_aggregates_analyzed_jobs(
    api: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api
    before_total = await session.scalar(select(func.count(JobPosting.id)))
    before_analyzed = await session.scalar(select(func.count(AgeAnalysis.id)))
    before_restricted = await session.scalar(
        select(func.count(AgeAnalysis.id)).where(AgeAnalysis.has_age_restriction.is_(True))
    )
    company = Company(
        normalized_name=unique_name("analytics"),
        display_name="Analytics Test Company",
        industry=f"Analytics {uuid4().hex}",
    )
    restricted_job = JobPosting(
        job_title="Analytics Restricted",
        job_level=f"Analytics Level {uuid4().hex}",
        source_platform="user_report",
        content_hash=uuid4().hex,
        raw_description="Usia maksimal 30 tahun.",
    )
    restricted_job.analysis = AgeAnalysis(
        has_age_restriction=True,
        restriction_type="EXPLICIT",
        max_age=30,
        confidence_score=Decimal("0.950"),
    )
    unrestricted_job = JobPosting(
        job_title="Analytics Unrestricted",
        job_level=restricted_job.job_level,
        source_platform="user_report",
        content_hash=uuid4().hex,
        raw_description="Fokus pada kompetensi.",
    )
    unrestricted_job.analysis = AgeAnalysis(
        has_age_restriction=False,
        restriction_type="NONE",
        confidence_score=Decimal("0.900"),
    )
    company.job_postings.extend([restricted_job, unrestricted_job])
    session.add(company)
    session.add(
        JobPosting(
            job_title="Analytics Pending",
            job_level=restricted_job.job_level,
            source_platform="user_report",
            content_hash=uuid4().hex,
            raw_description="Belum dianalisis.",
        )
    )
    await session.flush()

    response = await client.get("/api/v1/analytics/overview")

    assert response.status_code == 200
    overview = response.json()
    assert overview["total_submissions"] == int(before_total or 0) + 3
    assert overview["analyzed_jobs"] == int(before_analyzed or 0) + 2
    assert overview["restricted_jobs"] == int(before_restricted or 0) + 1
    assert overview["age_bias_rate_pct"] == round(
        (int(before_restricted or 0) + 1) / (int(before_analyzed or 0) + 2) * 100,
        2,
    )
    assert {
        row["restriction_type"]: row["analyzed_jobs"]
        for row in overview["restriction_breakdown"]
    }["EXPLICIT"] >= 1
    industry = next(
        row for row in overview["industry_breakdown"] if row["category"] == company.industry
    )
    assert industry["analyzed_jobs"] == 2
    assert industry["restricted_jobs"] == 1
    job_level = next(
        row
        for row in overview["job_level_breakdown"]
        if row["category"] == restricted_job.job_level
    )
    assert job_level["analyzed_jobs"] == 2
    assert job_level["age_bias_rate_pct"] == 50.0
