"""Tests for job search and CV matching integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.schemas.job_search import JobSearchFilters, JobSearchResult
from app.services.job_fetcher import (
    FetchedJob,
    IndeedFetcher,
    RemoteIoFetcher,
    compute_query_hash,
    deduplicate_jobs,
)


class TestJobFetcherBase:
    """Test basic job fetcher functionality."""

    @pytest.mark.asyncio
    async def test_indeed_fetcher_timeout(self):
        """Test that Indeed fetcher handles timeout gracefully."""
        fetcher = IndeedFetcher(timeout_seconds=0.001)
        filters = JobSearchFilters(keywords="python")
        result = await fetcher.fetch(filters)
        # Should return empty list on timeout
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_remote_io_fetcher_exists(self):
        """Test that RemoteIoFetcher class exists."""
        fetcher = RemoteIoFetcher(timeout_seconds=2.0)
        assert fetcher is not None
        assert hasattr(fetcher, "fetch")


class TestJobSearchUtilities:
    """Test utility functions for job search."""

    def test_compute_query_hash(self):
        """Test that query hash is consistent and unique."""
        filters1 = JobSearchFilters(keywords="python", location="remote")
        filters2 = JobSearchFilters(keywords="python", location="remote")
        filters3 = JobSearchFilters(keywords="javascript", location="remote")

        hash1 = compute_query_hash(filters1)
        hash2 = compute_query_hash(filters2)
        hash3 = compute_query_hash(filters3)

        assert hash1 == hash2  # Same filters should produce same hash
        assert hash1 != hash3  # Different filters should produce different hash
        assert len(hash1) == 32  # MD5 hash is 32 characters

    def test_deduplicate_jobs(self):
        """Test that duplicate jobs are removed."""
        job1 = FetchedJob(
            job_title="Python Developer",
            company_name="Tech Corp",
            description="Build APIs",
            url="https://example.com/job1",
            source_platform="Indeed",
        )
        job2 = FetchedJob(
            job_title="Python Developer",
            company_name="Tech Corp",
            description="Build APIs (from remote.io)",
            url="https://example.com/job2",
            source_platform="remote.io",
        )
        job3 = FetchedJob(
            job_title="Senior Python Developer",
            company_name="Tech Corp",
            description="Lead team",
            url="https://example.com/job3",
            source_platform="Indeed",
        )

        jobs = [job1, job2, job3]
        deduplicated = deduplicate_jobs(jobs)

        # Should have 2 jobs (job1 and job2 are duplicates)
        assert len(deduplicated) == 2


class TestJobSearchFilters:
    """Test job search filter schema."""

    def test_filters_validation(self):
        """Test that filters validate correctly."""
        filters = JobSearchFilters(
            location="Jakarta",
            job_type="remote",
            experience_level="senior",
            salary_min=50000,
            salary_max=100000,
            keywords="python django",
        )

        assert filters.location == "Jakarta"
        assert filters.job_type == "remote"
        assert filters.salary_min == 50000

    def test_filters_optional(self):
        """Test that filters are optional."""
        filters = JobSearchFilters()
        assert filters.location is None
        assert filters.job_type is None
        assert filters.keywords is None


class TestJobSearchResult:
    """Test job search result schema."""

    def test_job_search_result_validation(self):
        """Test that JobSearchResult validates correctly."""
        result = JobSearchResult(
            job_title="Python Developer",
            company_name="Tech Corp",
            source_platform="Indeed",
            source_url="https://indeed.com/job/123",
            keyword_match_percentage=85.5,
            matched_skills=["Python", "Django"],
            ai_assessment=None,
        )

        assert result.job_title == "Python Developer"
        assert result.keyword_match_percentage == 85.5
        assert result.matched_skills == ["Python", "Django"]
        assert result.analysis_status == "success"

    def test_job_search_result_match_percentage_bounds(self):
        """Test that match percentage is bounded 0-100."""
        # Valid
        result = JobSearchResult(
            job_title="Python Developer",
            company_name="Tech Corp",
            source_platform="Indeed",
            source_url=None,
            keyword_match_percentage=0.0,
            matched_skills=[],
            ai_assessment=None,
        )
        assert result.keyword_match_percentage == 0.0

        result = JobSearchResult(
            job_title="Python Developer",
            company_name="Tech Corp",
            source_platform="Indeed",
            source_url=None,
            keyword_match_percentage=100.0,
            matched_skills=["Python"],
            ai_assessment=None,
        )
        assert result.keyword_match_percentage == 100.0


class TestFetchedJob:
    """Test FetchedJob dataclass."""

    def test_fetched_job_creation(self):
        """Test that FetchedJob can be created."""
        job = FetchedJob(
            job_title="Python Developer",
            company_name="Tech Corp",
            description="Build web APIs",
            url="https://example.com/job",
            source_platform="Indeed",
        )

        assert job.job_title == "Python Developer"
        assert job.company_name == "Tech Corp"
        assert job.source_platform == "Indeed"
        assert job.posted_date is None
