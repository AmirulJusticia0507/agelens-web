"""Integration tests for the PostgreSQL schema created by Alembic migrations.

These tests need a reachable database configured via ``DATABASE_URL`` with the
``pg_trgm``, ``pgcrypto`` and ``vector`` extensions available (the Docker image
used by ``compose.yaml`` provides them). They are skipped when no database can be
reached, for example in CI jobs that do not start PostgreSQL. Every test runs in a
transaction that is rolled back, so no data is left behind.
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def database_url() -> str:
    return get_settings().database_url


@pytest.fixture(scope="module")
def migrated_database(database_url: str) -> str:
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
async def connection(migrated_database: str) -> AsyncIterator[AsyncConnection]:
    engine = create_async_engine(migrated_database)
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                yield conn
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def execute(connection: AsyncConnection, sql: str, **params: object) -> None:
    """Run ``sql`` inside a savepoint so a constraint error keeps the transaction usable."""
    async with connection.begin_nested():
        await connection.execute(text(sql), params)


async def insert_company(connection: AsyncConnection, name: str) -> object:
    result = await connection.execute(
        text(
            "INSERT INTO companies (normalized_name, display_name) "
            "VALUES (:name, :name) RETURNING id"
        ),
        {"name": name},
    )
    return result.scalar_one()


async def insert_job(
    connection: AsyncConnection, content_hash: str, company_id: object | None = None
) -> object:
    result = await connection.execute(
        text(
            "INSERT INTO job_postings "
            "(company_id, job_title, source_platform, content_hash, raw_description) "
            "VALUES (:company_id, 'Staff Accounting', 'user_report', :content_hash, "
            "'Usia maksimal 25 tahun') RETURNING id"
        ),
        {"company_id": company_id, "content_hash": content_hash},
    )
    return result.scalar_one()


async def test_required_extensions_are_installed(connection: AsyncConnection) -> None:
    result = await connection.execute(
        text("SELECT extname FROM pg_extension WHERE extname = ANY(:names)"),
        {"names": ["pg_trgm", "pgcrypto", "vector"]},
    )

    assert {row[0] for row in result} == {"pg_trgm", "pgcrypto", "vector"}


async def test_company_defaults_are_applied(connection: AsyncConnection) -> None:
    result = await connection.execute(
        text(
            "INSERT INTO companies (normalized_name, display_name) "
            "VALUES ('pt-sumber-alfaria', 'PT Sumber Alfaria') "
            "RETURNING id, total_jobs_analyzed, age_restricted_jobs_count, "
            "age_bias_score, created_at, updated_at"
        )
    )
    row = result.one()

    assert row.id is not None
    assert row.total_jobs_analyzed == 0
    assert row.age_restricted_jobs_count == 0
    assert float(row.age_bias_score) == 0.0
    assert row.created_at is not None
    assert row.updated_at is not None


async def test_company_age_bias_score_range_is_enforced(connection: AsyncConnection) -> None:
    with pytest.raises(IntegrityError, match="ck_companies_age_bias_score_range"):
        await execute(
            connection,
            "INSERT INTO companies (normalized_name, display_name, age_bias_score) "
            "VALUES ('out-of-range', 'Out of Range', 100.01)",
        )


async def test_company_name_search_uses_trigram_and_full_text_indexes(
    connection: AsyncConnection,
) -> None:
    result = await connection.execute(
        text(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'companies' "
            "AND indexname IN "
            "('ix_companies_normalized_name_trgm', 'ix_companies_display_name_fts')"
        )
    )
    indexes = {row.indexname: row.indexdef for row in result}

    assert "gin_trgm_ops" in indexes["ix_companies_normalized_name_trgm"]
    assert "to_tsvector" in indexes["ix_companies_display_name_fts"]


async def test_age_analysis_restriction_type_is_validated(connection: AsyncConnection) -> None:
    job_id = await insert_job(connection, "hash-restriction")

    with pytest.raises(IntegrityError, match="ck_ai_age_analyses_restriction_type"):
        await execute(
            connection,
            "INSERT INTO ai_age_analyses "
            "(job_posting_id, has_age_restriction, restriction_type) "
            "VALUES (:job_id, true, 'SOMETIMES')",
            job_id=job_id,
        )


async def test_age_analysis_confidence_score_range_is_validated(
    connection: AsyncConnection,
) -> None:
    job_id = await insert_job(connection, "hash-confidence")

    with pytest.raises(IntegrityError, match="ck_ai_age_analyses_confidence_score_range"):
        await execute(
            connection,
            "INSERT INTO ai_age_analyses "
            "(job_posting_id, has_age_restriction, restriction_type, confidence_score) "
            "VALUES (:job_id, true, 'EXPLICIT', 1.5)",
            job_id=job_id,
        )


async def test_age_analysis_age_range_is_validated(connection: AsyncConnection) -> None:
    job_id = await insert_job(connection, "hash-age-range")

    with pytest.raises(IntegrityError, match="ck_ai_age_analyses_age_range"):
        await execute(
            connection,
            "INSERT INTO ai_age_analyses "
            "(job_posting_id, has_age_restriction, restriction_type, min_age, max_age) "
            "VALUES (:job_id, true, 'EXPLICIT', 30, 25)",
            job_id=job_id,
        )


async def test_job_posting_content_hash_must_be_unique(connection: AsyncConnection) -> None:
    await insert_job(connection, "duplicate-hash")

    with pytest.raises(IntegrityError, match="job_postings_content_hash_key"):
        await execute(
            connection,
            "INSERT INTO job_postings "
            "(job_title, source_platform, content_hash, raw_description) "
            "VALUES ('Staff', 'user_report', 'duplicate-hash', 'Isi lowongan')",
        )


async def test_analysis_is_removed_with_its_job_posting(connection: AsyncConnection) -> None:
    job_id = await insert_job(connection, "hash-cascade")
    await execute(
        connection,
        "INSERT INTO ai_age_analyses "
        "(job_posting_id, has_age_restriction, restriction_type, max_age, "
        "extracted_evidence, confidence_score) "
        "VALUES (:job_id, true, 'EXPLICIT', 25, 'Usia maksimal 25 tahun', 0.99)",
        job_id=job_id,
    )

    await execute(connection, "DELETE FROM job_postings WHERE id = :job_id", job_id=job_id)

    remaining = await connection.execute(
        text("SELECT count(*) FROM ai_age_analyses WHERE job_posting_id = :job_id"),
        {"job_id": job_id},
    )
    assert remaining.scalar_one() == 0


async def test_deleting_company_keeps_its_job_postings(connection: AsyncConnection) -> None:
    company_id = await insert_company(connection, "orphan-check")
    job_id = await insert_job(connection, "hash-orphan", company_id=company_id)

    await execute(connection, "DELETE FROM companies WHERE id = :company_id", company_id=company_id)

    result = await connection.execute(
        text("SELECT company_id FROM job_postings WHERE id = :job_id"), {"job_id": job_id}
    )
    assert result.scalar_one() is None
