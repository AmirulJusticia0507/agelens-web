#!/usr/bin/env python
"""Validate that all imports work correctly."""

import sys

try:
    print("Validating job_search schema...")
    from app.schemas.job_search import JobSearchFilters, JobSearchResponse, JobSearchResult
    print("✓ job_search schema imports OK")

    print("Validating job_fetcher service...")
    from app.services.job_fetcher import (
        FetchedJob,
        IndeedFetcher,
        LinkedInFetcher,
        RemoteIoFetcher,
        compute_query_hash,
        deduplicate_jobs,
    )
    print("✓ job_fetcher service imports OK")

    print("Validating cv_matches API...")
    from app.api.cv_matches import router
    print("✓ cv_matches API imports OK")

    print("Validating config...")
    from app.config import Settings, get_settings
    settings = Settings()
    assert hasattr(settings, 'job_search_timeout_seconds')
    assert hasattr(settings, 'job_search_per_source_timeout_seconds')
    assert hasattr(settings, 'job_search_llm_timeout_seconds')
    assert hasattr(settings, 'job_search_cache_ttl_seconds')
    assert hasattr(settings, 'job_search_max_results')
    print("✓ Config settings OK")
    print(f"  - job_search_timeout_seconds: {settings.job_search_timeout_seconds}")
    print(f"  - job_search_per_source_timeout_seconds: {settings.job_search_per_source_timeout_seconds}")
    print(f"  - job_search_llm_timeout_seconds: {settings.job_search_llm_timeout_seconds}")
    print(f"  - job_search_cache_ttl_seconds: {settings.job_search_cache_ttl_seconds}")
    print(f"  - job_search_max_results: {settings.job_search_max_results}")

    print("\n✅ All validations passed!")
    sys.exit(0)

except Exception as e:
    print(f"\n❌ Validation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
