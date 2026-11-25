from http import HTTPStatus
from pathlib import PurePath
from time import time
from typing import Annotated
import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_session
from app.config import get_settings
from app.db.models import JobPosting
from app.schemas.cv_matches import CvJobAiAssessment, CvMatchResponse
from app.schemas.job_search import JobSearchFilters, JobSearchResponse, JobSearchResult
from app.services.age_analysis import (
    AnalysisConfigurationError,
    AnalysisProviderError,
    OpenAICompatibleAgeAnalyzer,
)
from app.services.cv_matching import CvPdfError, build_profile_match, extract_cv_text, extract_skills
from app.services.job_fetcher import (
    GlassdoorFetcher,
    GoogleJobsFetcher,
    IndeedFetcher,
    JobStreetFetcher,
    LinkedInFetcher,
    LokerJakartaFetcher,
    LokerJogjaFetcher,
    RemoteIoFetcher,
    compute_query_hash,
    deduplicate_jobs,
    _normalize_text_for_matching,
)

logger = logging.getLogger(__name__)

MAX_CV_FILE_BYTES = 8 * 1024 * 1024

router = APIRouter(prefix="/cv-matches", tags=["cv-matches"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
async def _read_cv_text(file: UploadFile) -> str:
    extension = PurePath(file.filename or "").suffix.casefold()
    if extension != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unggah CV dalam format PDF.",
        )
    if file.size is not None and file.size > MAX_CV_FILE_BYTES:
        raise HTTPException(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            detail="Ukuran setiap file CV maksimal 8 MB.",
        )

    try:
        content = await file.read(MAX_CV_FILE_BYTES + 1)
    finally:
        await file.close()

    if len(content) > MAX_CV_FILE_BYTES:
        raise HTTPException(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            detail="Ukuran setiap file CV maksimal 8 MB.",
        )

    try:
        return extract_cv_text(content)
    except CvPdfError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/analyze", response_model=CvMatchResponse)
async def analyze_cv_matches(
    session: SessionDependency,
    cv_a: Annotated[UploadFile, File()],
    cv_b: Annotated[UploadFile | None, File()] = None,
) -> CvMatchResponse:
    cv_a_text = await _read_cv_text(cv_a)
    cv_b_text = await _read_cv_text(cv_b) if cv_b is not None else None
    job_postings = list(
        await session.scalars(
            select(JobPosting)
            .options(selectinload(JobPosting.company))
            .where(
                JobPosting.company_id.is_not(None),
                JobPosting.raw_metadata["record_type"].astext == "job_posting",
                JobPosting.source_platform != "target_company",
            )
            .order_by(JobPosting.job_title.asc())
        )
    )
    profiles = [build_profile_match("CV 1", cv_a_text, job_postings)]
    if cv_b_text is not None:
        profiles.append(build_profile_match("CV 2", cv_b_text, job_postings))

    return CvMatchResponse(profiles=profiles)


@router.post("/assess-job", response_model=CvJobAiAssessment)
async def assess_cv_job_fit(
    job_posting_id: Annotated[str, Form(min_length=1, max_length=36)],
    cv_file: Annotated[UploadFile, File()],
    session: SessionDependency,
) -> CvJobAiAssessment:
    try:
        job = await session.get(JobPosting, job_posting_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="ID lowongan tidak valid.") from exc
    if job is None or job.company_id is None or job.source_platform == "target_company":
        raise HTTPException(status_code=404, detail="Lowongan tidak ditemukan.")
    cv_text = await _read_cv_text(cv_file)
    try:
        result = await OpenAICompatibleAgeAnalyzer().assess_cv_match(
            cv_text,
            job.raw_description,
        )
    except AnalysisConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AnalysisProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CvJobAiAssessment.model_validate(result.model_dump())


@router.post("/search-and-analyze", response_model=JobSearchResponse)
async def search_and_analyze_cv_jobs(
    cv_file: Annotated[UploadFile, File()],
    location: Annotated[str | None, Form()] = None,
    job_type: Annotated[str | None, Form()] = None,
    experience_level: Annotated[str | None, Form()] = None,
    salary_min: Annotated[int | None, Form()] = None,
    salary_max: Annotated[int | None, Form()] = None,
    keywords: Annotated[str | None, Form()] = None,
) -> JobSearchResponse:
    """
    Search for jobs and analyze CV fit.
    
    - Fetches jobs from Google, Indeed, JobStreet, LinkedIn, Glassdoor,
      remote.io, and local Jogja/Jakarta job listings
    - Scores jobs based on keyword matching with CV skills
    - Returns top 10 jobs with AI assessments
    
    Total response time is capped at 5 seconds.
    """
    settings = get_settings()
    start_time = time()
    warnings = []

    try:
        # Validate and extract CV text
        cv_text = await _read_cv_text(cv_file)
        
        # Extract CV skills
        cv_skills = extract_skills(cv_text)
        if not cv_skills:
            raise HTTPException(
                status_code=422,
                detail="CV tidak memiliki keterampilan teknis yang dapat dikenali.",
            )

        # Build search filters
        filters = JobSearchFilters(
            location=location,
            job_type=job_type,
            experience_level=experience_level,
            salary_min=salary_min,
            salary_max=salary_max,
            keywords=keywords,
        )

        # Fetch jobs from all sources concurrently
        try:
            timeout = settings.job_search_per_source_timeout_seconds
            fetchers = [
                GoogleJobsFetcher(timeout), IndeedFetcher(timeout), JobStreetFetcher(timeout),
                LinkedInFetcher(timeout), GlassdoorFetcher(timeout), RemoteIoFetcher(timeout),
                LokerJogjaFetcher(timeout), LokerJakartaFetcher(timeout),
            ]
            results = await asyncio.gather(
                *(fetcher.fetch(filters) for fetcher in fetchers),
                return_exceptions=True,
            )

            all_jobs = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    source_name = getattr(fetchers[i], "platform", fetchers[i].__class__.__name__)
                    logger.warning(f"Fetcher {source_name} failed: {result}")
                    warnings.append(f"Failed to fetch jobs from {source_name}")
                else:
                    all_jobs.extend(result)

            if not all_jobs:
                raise HTTPException(
                    status_code=404,
                    detail="Tidak ada lowongan yang ditemukan dari sumber yang tersedia.",
                )

        except asyncio.TimeoutError:
            warnings.append("Job search timed out; partial results may be incomplete")
            logger.warning("Job fetch timeout")
            all_jobs = []

        # Deduplicate jobs
        all_jobs = deduplicate_jobs(all_jobs)

        # Score jobs by keyword matching with word boundary normalization
        scored_jobs = []
        cv_skills_normalized = {skill: _normalize_text_for_matching(skill) for skill in cv_skills}
        
        for job in all_jobs:
            # Normalize job description for matching (preserve original for LLM)
            job_description_normalized = _normalize_text_for_matching(
                f"{job.job_title} {job.description}"
            )
            
            matched_skills = []
            for skill in cv_skills:
                # Use tokenized word boundary matching to avoid "java" matching "javascript"
                skill_tokens = cv_skills_normalized[skill]
                # Check if all tokens of the skill appear in the description
                if all(token in job_description_normalized for token in skill_tokens):
                    matched_skills.append(skill)

            if matched_skills:  # Only include jobs with at least one matched skill
                match_percentage = round(len(matched_skills) / len(cv_skills) * 100, 1)
                scored_jobs.append((job, matched_skills, match_percentage))

        # Sort by match percentage descending and take top N
        scored_jobs.sort(key=lambda x: x[2], reverse=True)
        top_jobs = scored_jobs[:settings.job_search_max_results]

        if not top_jobs:
            # If no jobs matched skills, return all deduplicated jobs with 0% match
            top_jobs = [(job, [], 0.0) for job in all_jobs[:settings.job_search_max_results]]

        # Track elapsed time for timeout isolation
        fetch_duration = time() - start_time
        llm_timeout = max(0.5, settings.job_search_llm_timeout_seconds - fetch_duration)
        
        logger.debug(f"Fetch phase took {fetch_duration:.2f}s; LLM timeout reduced to {llm_timeout:.2f}s")

        # Run LLM analysis on top jobs concurrently with timeout
        analyzer = OpenAICompatibleAgeAnalyzer()
        llm_tasks = []
        for job, _, _ in top_jobs:
            llm_tasks.append(analyzer.assess_cv_match(cv_text, job.description))

        try:
            llm_results = await asyncio.wait_for(
                asyncio.gather(*llm_tasks, return_exceptions=True),
                timeout=llm_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("LLM analysis timed out")
            warnings.append("AI analysis timed out; fit assessments unavailable")
            llm_results = [None] * len(top_jobs)

        # Build response
        response_results = []
        # Assertion to maintain index alignment invariant
        assert len(llm_results) == len(top_jobs), (
            f"LLM results count ({len(llm_results)}) must match top_jobs count ({len(top_jobs)}); "
            "asyncio.gather maintains order and return_exceptions=True ensures consistent length"
        )
        for i, (job, matched_skills, match_percentage) in enumerate(top_jobs):
            llm_result = llm_results[i]
            analysis_status = "success"

            if llm_result is None:
                analysis_status = "timeout"
                ai_assessment = None
            elif isinstance(llm_result, Exception):
                analysis_status = "error"
                logger.warning(f"LLM analysis failed for job {job.job_title}: {llm_result}")
                ai_assessment = None
            else:
                try:
                    ai_assessment = CvJobAiAssessment.model_validate(llm_result.model_dump())
                except Exception as e:
                    logger.warning(f"Failed to convert LLM result to schema: {e}")
                    analysis_status = "error"
                    ai_assessment = None

            response_results.append(
                JobSearchResult(
                    job_title=job.job_title,
                    company_name=job.company_name,
                    source_platform=job.source_platform,
                    source_url=job.url if job.url else None,
                    keyword_match_percentage=match_percentage,
                    matched_skills=matched_skills,
                    ai_assessment=ai_assessment,
                    analysis_status=analysis_status,
                )
            )

        end_time = time()
        search_duration_ms = int((end_time - start_time) * 1000)

        return JobSearchResponse(
            cv_skills=cv_skills,
            results=response_results,
            search_duration_ms=search_duration_ms,
            warnings=warnings,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in search_and_analyze: {exc}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan pada server.") from exc
