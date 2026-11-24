import re
import unicodedata
from collections.abc import Sequence
from io import BytesIO
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.db.models import JobPosting
from app.schemas.cv_matches import (
    CvCompanyMatchResponse,
    CvJobMatchResponse,
    CvProfileMatchResponse,
)

MAX_PDF_PAGES = 30

SKILL_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("JavaScript", ("javascript",)),
    ("TypeScript", ("typescript",)),
    ("React", ("react",)),
    ("Next.js", ("next.js", "nextjs")),
    ("Node.js", ("node.js", "nodejs", "node")),
    ("Express.js", ("express.js", "expressjs", "express")),
    ("Python", ("python",)),
    ("Go", ("golang", "go language")),
    ("PostgreSQL", ("postgresql", "postgres")),
    ("MySQL", ("mysql",)),
    ("MongoDB", ("mongodb", "mongo")),
    ("Redis", ("redis",)),
    ("AWS", ("amazon web services", "aws")),
    ("GCP", ("google cloud platform", "gcp")),
    ("Azure", ("microsoft azure", "azure")),
    ("Docker", ("docker",)),
    ("Kubernetes", ("kubernetes", "k8s")),
    ("GraphQL", ("graphql",)),
    ("Vue.js", ("vue.js", "vuejs", "vue")),
    ("PHP", ("php",)),
    ("Laravel", ("laravel",)),
    ("Java", ("java",)),
    ("C#", ("c#",)),
    (".NET", (".net", "dotnet")),
    ("HTML", ("html",)),
    ("CSS", ("css",)),
    ("Tailwind CSS", ("tailwind css", "tailwind")),
    ("FastAPI", ("fastapi",)),
    ("Django", ("django",)),
    ("Flask", ("flask",)),
    ("Git", ("git",)),
)


class CvPdfError(Exception):
    pass


def extract_cv_text(pdf_content: bytes) -> str:
    if not pdf_content.startswith(b"%PDF-"):
        raise CvPdfError("File harus berupa PDF yang valid.")

    try:
        reader = PdfReader(BytesIO(pdf_content), strict=False)
        if reader.is_encrypted:
            raise CvPdfError("PDF terenkripsi tidak dapat dianalisis.")
        pages = reader.pages
        if len(pages) > MAX_PDF_PAGES:
            raise CvPdfError(f"PDF maksimal {MAX_PDF_PAGES} halaman.")
        text = "\n".join(page.extract_text() or "" for page in pages)
    except CvPdfError:
        raise
    except (PdfReadError, OSError, ValueError) as exc:
        raise CvPdfError("PDF tidak dapat dibaca. Coba ekspor ulang sebagai PDF.") from exc

    if not text.strip():
        raise CvPdfError(
            "Teks CV tidak ditemukan. PDF hasil scan belum didukung; gunakan PDF yang teksnya "
            "dapat dipilih."
        )
    return text


def _contains_alias(text: str, alias: str) -> bool:
    left_boundary = r"(?<!\w)" if alias[0].isalnum() else ""
    right_boundary = r"(?!\w)" if alias[-1].isalnum() else ""
    pattern = re.compile(
        f"{left_boundary}{re.escape(alias)}{right_boundary}",
        flags=re.IGNORECASE,
    )
    return pattern.search(text) is not None


def extract_skills(text: str) -> list[str]:
    normalized_text = unicodedata.normalize("NFKC", text)
    skills = []
    for skill, aliases in SKILL_ALIASES:
        found = any(_contains_alias(normalized_text, alias) for alias in aliases)
        if skill == "Go":
            found = found or re.search(r"(?<!\w)Go(?!\w)", normalized_text) is not None
        if found:
            skills.append(skill)
    return skills


def rank_company_matches(
    skills: list[str],
    job_postings: Sequence[JobPosting],
) -> list[CvCompanyMatchResponse]:
    if not skills:
        return []

    candidate_skills = set(skills)
    companies: dict[UUID, CvCompanyMatchResponse] = {}
    seen_postings: set[tuple[UUID, str]] = set()
    for posting in job_postings:
        company = posting.company
        if company is None:
            continue

        source_url = (posting.source_url or "").strip()
        if source_url:
            parsed_url = urlsplit(source_url)
            canonical_url = urlunsplit(
                (parsed_url.scheme.casefold(), parsed_url.netloc.casefold(), parsed_url.path.rstrip("/"), parsed_url.query, "")
            )
            posting_key = (company.id, canonical_url)
        else:
            posting_key = (company.id, f"{posting.job_title.casefold()}:{posting.content_hash}")
        if posting_key in seen_postings:
            continue
        seen_postings.add(posting_key)

        job_skills = set(extract_skills(f"{posting.job_title}\n{posting.raw_description}"))
        matched_skills = [skill for skill in skills if skill in candidate_skills & job_skills]
        if not matched_skills:
            continue

        percentage = round(len(matched_skills) / len(skills) * 100, 1)
        job_match = CvJobMatchResponse(
            job_posting_id=posting.id,
            job_title=posting.job_title,
            source_platform=posting.source_platform,
            source_url=posting.source_url,
            match_percentage=percentage,
            matched_skills=matched_skills,
            summary_only=bool(
                posting.raw_metadata
                and posting.raw_metadata.get("listing_summary_only", False)
            ),
        )
        company_match = companies.get(company.id)
        if company_match is None:
            company_match = CvCompanyMatchResponse(
                company_id=company.id,
                display_name=company.display_name,
                match_percentage=percentage,
                matched_skills=matched_skills,
                jobs=[job_match],
            )
            companies[company.id] = company_match
        else:
            company_match.jobs.append(job_match)
            if percentage > company_match.match_percentage:
                company_match.match_percentage = percentage
                company_match.matched_skills = matched_skills

    matches = list(companies.values())
    visible_companies: dict[str, CvCompanyMatchResponse] = {}
    for company_match in matches:
        company_match.jobs.sort(
            key=lambda job: (-job.match_percentage, job.job_title.casefold())
        )
        normalized_name = " ".join(company_match.display_name.casefold().split())
        existing = visible_companies.get(normalized_name)
        if existing is None:
            visible_companies[normalized_name] = company_match
        else:
            existing.jobs.extend(company_match.jobs)
            existing.jobs.sort(key=lambda job: (-job.match_percentage, job.job_title.casefold()))
            if company_match.match_percentage > existing.match_percentage:
                existing.match_percentage = company_match.match_percentage
                existing.matched_skills = company_match.matched_skills
    return sorted(
        visible_companies.values(),
        key=lambda company: (-company.match_percentage, company.display_name.casefold()),
    )


def build_profile_match(
    label: str,
    cv_text: str,
    job_postings: Sequence[JobPosting],
) -> CvProfileMatchResponse:
    skills = extract_skills(cv_text)
    return CvProfileMatchResponse(
        label=label,
        skills=skills,
        jobs_considered=len(job_postings),
        companies=rank_company_matches(skills, job_postings),
    )
