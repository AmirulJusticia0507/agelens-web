import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company, JobPosting

COMPANY_SIMILARITY_THRESHOLD = 0.80
COMPANY_SIMILARITY_GAP = 0.05
LEGAL_DESIGNATORS = {
    "cv",
    "persero",
    "perseroan",
    "tbk",
    "terbuka",
    "terbatas",
    "pt",
}


@dataclass(frozen=True)
class IngestionResult:
    job_posting: JobPosting
    created: bool


def normalize_company_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).casefold()
    tokens = re.findall(r"\w+", normalized)

    while tokens and tokens[0] in LEGAL_DESIGNATORS:
        tokens.pop(0)
    while tokens and tokens[-1] in LEGAL_DESIGNATORS:
        tokens.pop()

    return " ".join(tokens)


def _normalize_content(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def calculate_content_hash(
    company_name: str | None,
    job_title: str,
    raw_description: str,
) -> str:
    normalized_company = normalize_company_name(company_name) if company_name else ""
    canonical_content = "\x1f".join(
        (
            normalized_company,
            _normalize_content(job_title),
            _normalize_content(raw_description),
        )
    )
    return hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()


async def _find_company(session: AsyncSession, normalized_name: str) -> Company | None:
    exact_match = await session.scalar(
        select(Company).where(Company.normalized_name == normalized_name)
    )
    if exact_match is not None:
        return exact_match

    similarity = func.similarity(Company.normalized_name, normalized_name)
    candidates = (
        await session.execute(
            select(Company, similarity.label("similarity"))
            .where(similarity >= COMPANY_SIMILARITY_THRESHOLD)
            .order_by(similarity.desc(), Company.normalized_name.asc())
            .limit(2)
        )
    ).all()
    if not candidates:
        return None

    best_company, best_score = candidates[0]
    if len(candidates) == 1 or best_score - candidates[1].similarity >= COMPANY_SIMILARITY_GAP:
        return best_company
    return None


async def _get_or_create_company(
    session: AsyncSession,
    company_name: str,
    normalized_name: str,
) -> Company:
    existing = await _find_company(session, normalized_name)
    if existing is not None:
        return existing

    inserted_id = await session.scalar(
        insert(Company)
        .values(normalized_name=normalized_name, display_name=company_name.strip())
        .on_conflict_do_nothing(index_elements=[Company.normalized_name])
        .returning(Company.id)
    )
    if inserted_id is not None:
        company = await session.get(Company, inserted_id)
        if company is not None:
            return company

    concurrent_insert = await session.scalar(
        select(Company).where(Company.normalized_name == normalized_name)
    )
    if concurrent_insert is None:
        raise RuntimeError("Company could not be created or retrieved")
    return concurrent_insert


async def ingest_job_posting(
    session: AsyncSession,
    *,
    job_title: str,
    source_platform: str,
    raw_description: str,
    company_name: str | None = None,
    source_url: str | None = None,
    job_level: str | None = None,
    posted_date: date | None = None,
    raw_metadata: dict[str, Any] | None = None,
) -> IngestionResult:
    normalized_title = job_title.strip()
    normalized_description = raw_description.strip()
    if not normalized_title:
        raise ValueError("Job title must not be empty")
    if not normalized_description:
        raise ValueError("Job description must not be empty")

    normalized_company = normalize_company_name(company_name) if company_name else None
    if company_name and not normalized_company:
        raise ValueError("Company name must contain a non-legal name")

    content_hash = calculate_content_hash(
        normalized_company,
        normalized_title,
        normalized_description,
    )
    existing_job = await session.scalar(
        select(JobPosting).where(JobPosting.content_hash == content_hash)
    )
    if existing_job is not None:
        return IngestionResult(job_posting=existing_job, created=False)

    company: Company | None = None
    if company_name and normalized_company:
        company = await _get_or_create_company(session, company_name, normalized_company)

    inserted_id: UUID | None = await session.scalar(
        insert(JobPosting)
        .values(
            company_id=company.id if company is not None else None,
            job_title=normalized_title,
            job_level=job_level,
            source_platform=source_platform,
            source_url=source_url,
            content_hash=content_hash,
            raw_description=normalized_description,
            raw_metadata=raw_metadata,
            posted_date=posted_date,
        )
        .on_conflict_do_nothing(index_elements=[JobPosting.content_hash])
        .returning(JobPosting.id)
    )
    created = inserted_id is not None
    job_id = inserted_id or await session.scalar(
        select(JobPosting.id).where(JobPosting.content_hash == content_hash)
    )
    if job_id is None:
        raise RuntimeError("Job posting could not be created or retrieved")

    job_posting = await session.get(JobPosting, job_id)
    if job_posting is None:
        raise RuntimeError("Job posting was created but could not be loaded")

    return IngestionResult(job_posting=job_posting, created=created)
