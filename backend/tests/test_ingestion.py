import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import get_settings
from app.db.models import Company
from app.services.ingestion import (
    calculate_content_hash,
    ingest_job_posting,
    normalize_company_name,
)

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
async def session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(migrated_database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db_session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield db_session
        finally:
            await db_session.close()
            await transaction.rollback()
    await engine.dispose()


def test_normalize_company_name_removes_legal_designators() -> None:
    assert normalize_company_name("PT. Sumber Alfaria Trijaya, Tbk.") == (
        "sumber alfaria trijaya"
    )
    assert normalize_company_name("CV Bumi Segar") == "bumi segar"
    assert normalize_company_name("PT Tbk") == ""


def test_content_hash_ignores_case_and_extra_whitespace() -> None:
    first = calculate_content_hash(
        "PT. Sumber Alfaria Trijaya, Tbk",
        "Staff Accountant",
        "Usia maksimal 28 tahun",
    )
    second = calculate_content_hash(
        "Sumber Alfaria Trijaya",
        "  STAFF   ACCOUNTANT ",
        " usia   maksimal 28 TAHUN ",
    )

    assert first == second


@pytest.mark.asyncio
async def test_ingestion_deduplicates_equivalent_submissions(
    session: AsyncSession,
) -> None:
    first = await ingest_job_posting(
        session,
        company_name="PT. Sumber Alfaria Trijaya, Tbk",
        job_title="Staff Accountant",
        source_platform="user_report",
        source_url="https://example.test/jobs/first",
        raw_description="Usia maksimal 28 tahun",
    )
    duplicate = await ingest_job_posting(
        session,
        company_name="Sumber Alfaria Trijaya",
        job_title=" STAFF   ACCOUNTANT ",
        source_platform="user_report",
        source_url="https://example.test/jobs/duplicate",
        raw_description="usia maksimal 28 TAHUN",
    )

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.job_posting.id == first.job_posting.id
    assert duplicate.job_posting.source_url == "https://example.test/jobs/first"


@pytest.mark.asyncio
async def test_ingestion_uses_trigram_match_for_company_typo(
    session: AsyncSession,
) -> None:
    first = await ingest_job_posting(
        session,
        company_name="Sumber Alfaria Trijaya",
        job_title="Staff Accountant",
        source_platform="user_report",
        raw_description="Kualifikasi dan tanggung jawab posisi.",
    )
    second = await ingest_job_posting(
        session,
        company_name="Sumber Alfaria Trijya",
        job_title="Finance Associate",
        source_platform="user_report",
        raw_description="Pengalaman akuntansi minimal dua tahun.",
    )

    assert first.job_posting.company_id == second.job_posting.company_id
    company_count = await session.scalar(
        select(func.count(Company.id)).where(
            Company.normalized_name.in_(
                ["sumber alfaria trijaya", "sumber alfaria trijya"]
            )
        )
    )
    assert company_count == 1


@pytest.mark.asyncio
async def test_ingestion_rejects_company_names_without_name_tokens(
    session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="non-legal name"):
        await ingest_job_posting(
            session,
            company_name="PT Tbk",
            job_title="Accountant",
            source_platform="user_report",
            raw_description="Kualifikasi posisi.",
        )


@pytest.mark.asyncio
async def test_ingestion_accepts_jobs_without_a_company(
    session: AsyncSession,
) -> None:
    result = await ingest_job_posting(
        session,
        job_title="Finance Associate",
        source_platform="user_report",
        raw_description="Pengalaman akuntansi minimal dua tahun.",
    )

    assert result.job_posting.company_id is None
    assert result.created is True
