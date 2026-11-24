from http import HTTPStatus
from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_session
from app.db.models import JobPosting
from app.schemas.cv_matches import CvMatchResponse
from app.services.cv_matching import CvPdfError, build_profile_match, extract_cv_text

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
    cv_b: Annotated[UploadFile, File()],
) -> CvMatchResponse:
    cv_a_text = await _read_cv_text(cv_a)
    cv_b_text = await _read_cv_text(cv_b)
    job_postings = list(
        await session.scalars(
            select(JobPosting)
            .options(selectinload(JobPosting.company))
            .where(JobPosting.company_id.is_not(None))
            .order_by(JobPosting.job_title.asc())
        )
    )

    return CvMatchResponse(
        profiles=[
            build_profile_match("CV 1", cv_a_text, job_postings),
            build_profile_match("CV 2", cv_b_text, job_postings),
        ]
    )
