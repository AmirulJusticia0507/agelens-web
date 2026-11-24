import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from app.api.dependencies import get_session
from app.config import get_settings
from app.db.models import AgeAnalysis, Company, JobPosting
from app.main import app

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


@pytest.mark.asyncio
async def test_get_company_returns_not_found_for_unknown_id(
    api: tuple[AsyncClient, AsyncSession],
) -> None:
    client, _ = api

    response = await client.get(f"/api/v1/companies/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Company not found"}
