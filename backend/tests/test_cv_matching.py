from io import BytesIO
from uuid import uuid4

import pytest
from pypdf import PdfWriter

from app.db.models import Company, JobPosting
from app.services.cv_matching import (
    CvPdfError,
    extract_cv_text,
    extract_skills,
    rank_company_matches,
)


def pdf_with_text(text: str) -> bytes:
    encoded_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 50 700 Td ({encoded_text}) Tj ET".encode("ascii")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        ),
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length "
        + str(len(stream)).encode()
        + b" >> stream\n"
        + stream
        + b"\nendstream\nendobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for pdf_object in objects:
        offsets.append(len(pdf))
        pdf.extend(pdf_object)
    xref_offset = len(pdf)
    pdf.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n")
    pdf.extend(f"{xref_offset}\n%%EOF\n".encode())
    return bytes(pdf)


def test_extract_skills_matches_technology_names_without_matching_go_as_a_verb() -> None:
    skills = extract_skills(
        "Experience with React, Next.js, Python, Go, and PostgreSQL. "
        "Ready to go wherever the role is."
    )

    assert skills == ["React", "Next.js", "Python", "Go", "PostgreSQL"]


def test_extract_cv_text_rejects_invalid_and_scanned_pdfs() -> None:
    assert extract_cv_text(pdf_with_text("React Python")) == "React Python"

    with pytest.raises(CvPdfError, match="PDF yang valid"):
        extract_cv_text(b"not a pdf")

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    content = BytesIO()
    writer.write(content)

    with pytest.raises(CvPdfError, match="Teks CV tidak ditemukan"):
        extract_cv_text(content.getvalue())


def test_rank_company_matches_returns_best_job_per_company() -> None:
    company = Company(
        id=uuid4(),
        normalized_name="contoh-teknologi",
        display_name="Contoh Teknologi",
    )
    best_job = JobPosting(
        id=uuid4(),
        job_title="Full Stack Engineer",
        source_platform="test",
        content_hash=uuid4().hex,
        raw_description="Menggunakan React, Python, dan PostgreSQL.",
        raw_metadata={"listing_summary_only": True},
    )
    other_job = JobPosting(
        id=uuid4(),
        job_title="Frontend Developer",
        source_platform="test",
        content_hash=uuid4().hex,
        raw_description="Menggunakan React.",
    )
    company.job_postings.extend([best_job, other_job])

    matches = rank_company_matches(
        ["React", "Python", "AWS"],
        [best_job, other_job],
    )

    assert len(matches) == 1
    assert matches[0].display_name == "Contoh Teknologi"
    assert matches[0].match_percentage == 66.7
    assert matches[0].matched_skills == ["React", "Python"]
    assert len(matches[0].jobs) == 2
    assert matches[0].jobs[0].summary_only is True
