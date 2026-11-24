from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "age_bias_score >= 0 AND age_bias_score <= 100",
            name="ck_companies_age_bias_score_range",
        ),
        Index(
            "ix_companies_normalized_name_trgm",
            "normalized_name",
            postgresql_using="gin",
            postgresql_ops={"normalized_name": "gin_trgm_ops"},
        ),
        Index(
            "ix_companies_display_name_fts",
            text("to_tsvector('indonesian', display_name)"),
            postgresql_using="gin",
        ),
        Index("ix_companies_age_bias_score", text("age_bias_score DESC")),
        Index(
            "ix_companies_display_name_fts",
            text("to_tsvector('indonesian', display_name)"),
            postgresql_using="gin",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    total_jobs_analyzed: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    age_restricted_jobs_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    age_bias_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default=text("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job_postings: Mapped[list[JobPosting]] = relationship(back_populates="company")


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL")
    )
    job_title: Mapped[str] = mapped_column(String(255))
    job_level: Mapped[str | None] = mapped_column(String(50))
    source_platform: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    raw_description: Mapped[str] = mapped_column(Text)
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    posted_date: Mapped[date | None] = mapped_column(Date)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company | None] = relationship(back_populates="job_postings")
    analysis: Mapped[AgeAnalysis | None] = relationship(
        back_populates="job_posting", cascade="all, delete-orphan", uselist=False
    )


class AgeAnalysis(Base):
    __tablename__ = "ai_age_analyses"
    __table_args__ = (
        CheckConstraint(
            "restriction_type IN ('EXPLICIT', 'IMPLICIT', 'NONE')",
            name="ck_ai_age_analyses_restriction_type",
        ),
        CheckConstraint(
            "min_age IS NULL OR max_age IS NULL OR min_age <= max_age",
            name="ck_ai_age_analyses_age_range",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_ai_age_analyses_confidence_score_range",
        ),
        Index(
            "ix_ai_age_analyses_max_age",
            "max_age",
            postgresql_where=text("max_age IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_posting_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        unique=True,
    )
    has_age_restriction: Mapped[bool] = mapped_column(Boolean)
    restriction_type: Mapped[str] = mapped_column(String(30))
    min_age: Mapped[int | None] = mapped_column(Integer)
    max_age: Mapped[int | None] = mapped_column(Integer)
    extracted_evidence: Mapped[str | None] = mapped_column(Text)
    ai_reasoning: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    model_used: Mapped[str | None] = mapped_column(String(100))
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job_posting: Mapped[JobPosting] = relationship(back_populates="analysis")
