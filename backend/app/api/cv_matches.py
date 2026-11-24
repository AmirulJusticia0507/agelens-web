from http import HTTPStatus
from pathlib import PurePath
from time import monotonic
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_session
from app.db.models import JobPosting
from app.schemas.cv_matches import CvJobAiAssessment, CvMatchResponse
from app.services.age_analysis import (
    AnalysisConfigurationError,
    AnalysisProviderError,
    OpenAICompatibleAgeAnalyzer,
)
from app.services.cv_matching import CvPdfError, build_profile_match, extract_cv_text

MAX_CV_FILE_BYTES = 8 * 1024 * 1024

router = APIRouter(prefix="/cv-matches", tags=["cv-matches"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CV_SESSION_TTL_SECONDS = 15 * 60
MAX_CV_SESSIONS = 100
_cv_sessions: dict[str, tuple[float, str, str | None]] = {}


class CvJobAssessmentRequest(BaseModel):
    cv_session_id: str = Field(min_length=36, max_length=36)
    profile: str = Field(pattern=r"^CV [12]$")
    job_posting_id: str = Field(min_length=1, max_length=36)

def _prune_cv_sessions() -> None:
    now = monotonic()
    for session_id, (expires_at, _, _) in list(_cv_sessions.items()):
        if expires_at <= now:
            _cv_sessions.pop(session_id, None)


def _store_cv_session(cv_a: str, cv_b: str | None) -> str:
    _prune_cv_sessions()
    while len(_cv_sessions) >= MAX_CV_SESSIONS:
        oldest_id = min(_cv_sessions, key=lambda key: _cv_sessions[key][0])
        _cv_sessions.pop(oldest_id, None)
    session_id = str(uuid4())
    _cv_sessions[session_id] = (monotonic() + CV_SESSION_TTL_SECONDS, cv_a, cv_b)
    return session_id


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
    cv_session_id = _store_cv_session(cv_a_text, cv_b_text)
    job_postings = list(
        await session.scalars(
            select(JobPosting)
            .options(selectinload(JobPosting.company))
            .where(
                JobPosting.company_id.is_not(None),
                JobPosting.raw_metadata["record_type"].astext == "job_posting",
            )
            .order_by(JobPosting.job_title.asc())
        )
    )
    profiles = [build_profile_match("CV 1", cv_a_text, job_postings, cv_session_id)]
    if cv_b_text is not None:
        profiles.append(build_profile_match("CV 2", cv_b_text, job_postings, cv_session_id))

    return CvMatchResponse(profiles=profiles)


@router.post("/assess-job", response_model=CvJobAiAssessment)
async def assess_cv_job_fit(
    payload: CvJobAssessmentRequest,
    session: SessionDependency,
) -> CvJobAiAssessment:
    _prune_cv_sessions()
    cached_cv = _cv_sessions.get(payload.cv_session_id)
    if cached_cv is None:
        raise HTTPException(status_code=410, detail="Sesi CV berakhir. Unggah ulang CV untuk melanjutkan.")
    _, cv_a_text, cv_b_text = cached_cv
    cv_text = cv_a_text if payload.profile == "CV 1" else cv_b_text
    if cv_text is None:
        raise HTTPException(status_code=404, detail="CV untuk profil ini tidak ditemukan.")
    try:
        job = await session.get(JobPosting, payload.job_posting_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="ID lowongan tidak valid.") from exc
    if job is None or not job.raw_metadata or job.raw_metadata.get("record_type") != "job_posting":
        raise HTTPException(status_code=404, detail="Lowongan tidak ditemukan.")
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
