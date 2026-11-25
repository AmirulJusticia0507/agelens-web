# Implementation Plan: RAG-based Dynamic Job Search with CV Matching

## Overview

Implement a new POST `/api/v1/cv-matches/search-and-analyze` endpoint that fetches live job postings from multiple free sources (Indeed, LinkedIn, remote.io), scores them against an uploaded CV, and returns personalized AI assessments. Total response time must stay under 5 seconds with graceful degradation if sources fail.

The feature reuses:
- `extract_skills()` from `app/services/cv_matching.py` for keyword matching
- `OpenAICompatibleAgeAnalyzer.assess_cv_match()` from `app/services/age_analysis.py` for LLM analysis
- `CvJobAiAssessment` schema from `app/schemas/cv_matches.py` for structured output

## Design Decisions

### 1. Job Fetcher Architecture
Create an abstract `JobFetcher` interface (`app/services/job_fetcher.py`) with concrete implementations for Indeed (HTML scraping + public search), LinkedIn (public job search page scraping), and remote.io (direct API if available, fallback to scraping). All fetchers inherit a common interface with `async fetch(filters: JobSearchFilters) -> list[FetchedJob]`. Fetchers run concurrently via `asyncio.gather()` with individual 2-second timeouts; failures on one source do not block others.

**Rationale**: Loose coupling allows independent updates to each source; timeout per-source (not global) lets faster sources complete while slower ones time out gracefully.

### 2. Keyword Scoring  
Reuse `extract_skills()` from `cv_matching.py` to extract skills from CV and each fetched job description. Score each job as `(matched_skill_count / cv_skill_count * 100)`. Sort descending and take top 10. Return full matched_skills list in response for transparency.

**Rationale**: Aligns with existing keyword extraction logic; avoids reinventing a matching algorithm.

### 3. LLM Batching Under 5s Latency
Run all 10 assess_cv_match calls concurrently via `asyncio.gather()` with individual 3-second timeouts. If timeout occurs on a job, return `ai_assessment: None` and a warning in the response. Total wall time for all 10 LLM calls is capped at 4 seconds (conservative headroom before 5s limit).

**Rationale**: Concurrent LLM calls are I/O-bound; asyncio.gather exploits parallelism. Per-call timeout ensures one slow call doesn't delay others. Setting wall time to 4s leaves 1s buffer for other operations (fetching, scoring, response serialization).

### 4. Caching Strategy
Use PostgreSQL with a lightweight `job_cache` table storing: source_platform, search_query_hash, job posting data, and created_at. Queries within 1 hour of a prior fetch return cached results without re-scraping. Cache lookup is keyed on `(source_platform, md5(search_query))` for fast hits on repeated queries.

**Rationale**: Avoids hammering job sources with repeated queries; PostgreSQL is already in use; 1-hour TTL balances freshness vs. API load.

### 5. Dependency Additions
Promote `httpx` from dev dependencies to main dependencies (already installed as dev, minimal overhead to move). Add `beautifulsoup4` for HTML scraping. No `playwright` or `selenium` (not installed, too heavy for the latency constraint); use lightweight `httpx` with standard HTML parsing instead.

**Rationale**: httpx is already a known quantity in tests; BS4 is the minimal scraping dependency; playwright would add significant latency and memory footprint.

### 6. Response Schema
Return `JobSearchResponse` containing: (1) cv_skills: list of skills extracted from CV, (2) results: list of `JobSearchResult` per job. Each `JobSearchResult` includes: job_title, company_name, source_platform, source_url, keyword_match_percentage, matched_skills, ai_assessment (CvJobAiAssessment or None), warnings (optional field listing non-critical failures).

**Rationale**: Transparency on skills matching and per-job LLM status; warnings on partial failures allow graceful degradation without throwing 500 errors.

### 7. Configuration Additions
Add to `Settings` class (app/config.py):
- `job_search_timeout_seconds: float = 5` — total response SLA
- `job_search_per_source_timeout_seconds: float = 2` — per-source fetcher timeout
- `job_search_llm_timeout_seconds: float = 3` — per-LLM-call timeout
- `job_search_cache_ttl_seconds: int = 3600` — 1-hour cache TTL
- `job_search_max_results: int = 10` — top N jobs by keyword score to analyze

**Rationale**: Makes timeouts and limits tunable without code changes.

## Implementation Steps

### Phase 1: Infrastructure and Configuration

- [ ] 1. Update dependencies in `pyproject.toml`.
      Add `httpx >= 0.27, < 1.0` to main dependencies (promote from dev).
      Add `beautifulsoup4 >= 4.12, < 5.0` to main dependencies.
      Files: `backend/pyproject.toml`
      Verify: `pip install -e backend` succeeds; `pip show httpx beautifulsoup4` lists both packages.

- [ ] 2. Add job search configuration to `app/config.py`.
      Add `job_search_timeout_seconds`, `job_search_per_source_timeout_seconds`, `job_search_llm_timeout_seconds`, `job_search_cache_ttl_seconds`, `job_search_max_results` to Settings class.
      Files: `backend/app/config.py`
      Verify: `Settings()` instantiates with defaults; override in .env works (`job_search_timeout_seconds=5`).

- [ ] 3. Create job cache table migration.
      Alembic migration adds `job_cache` table with columns: id (UUID PK), source_platform (string), search_query_hash (string, indexed), job_data (JSONB), created_at (timestamp). Add unique constraint on `(source_platform, search_query_hash)` and TTL cleanup note in migration.
      Files: `backend/migrations/versions/XXX_add_job_cache_table.py`
      Verify: Run `alembic upgrade head` without errors; `\d job_cache` in psql confirms columns and indexes exist.

### Phase 2: Job Fetcher Service

- [ ] 4. Create `app/services/job_fetcher.py` with abstract JobFetcher interface and common types.
      Define `FetchedJob` dataclass: job_title (str), company_name (str), description (str), url (str), source_platform (str), posted_date (date | None).
      Define `JobSearchFilters` dataclass: location (str | None), job_type (str | None), experience_level (str | None), salary_min (int | None), salary_max (int | None), keywords (str | None).
      Define abstract `JobFetcher` base class with async method `fetch(filters: JobSearchFilters) -> list[FetchedJob]`.
      Files: `backend/app/services/job_fetcher.py`
      Verify: Import class in Python shell; no syntax errors. Dataclasses are JSON-serializable (pydantic check is not needed here).

- [ ] 5. Implement Indeed fetcher in `app/services/job_fetcher.py`.
      Class `IndeedFetcher(JobFetcher)`: fetch by constructing Indeed public search URL (e.g., `indeed.com/jobs?q=...&l=...`), scrape results using httpx + BeautifulSoup. Extract job title, company, description snippet, URL. Handle pagination if top 10 needed. Set 2-second timeout via httpx. Return up to 15 jobs (we'll filter to top 10 by score later).
      **Note**: Indeed's public search does not have a free official API; scraping is the documented workaround for free tier.
      Files: `backend/app/services/job_fetcher.py` (append to file)
      Verify: Unit test with mocked httpx response; test succeeds, returns at least 1 job with all fields populated.

- [ ] 6. Implement LinkedIn fetcher in `app/services/job_fetcher.py`.
      Class `LinkedInFetcher(JobFetcher)`: fetch from LinkedIn public job search page (linkedin.com/jobs/search, no login required for public snippets). Note: LinkedIn restricts scraping; this fetcher attempts to retrieve public search page data. If blocked, return empty list (graceful degradation). Set 2-second timeout. Return up to 15 jobs.
      **Note**: LinkedIn actively blocks scrapers. This implementation should attempt a single request and gracefully degrade (return empty list) if 429 (rate limit) or 403 (forbidden) is encountered.
      Files: `backend/app/services/job_fetcher.py` (append to file)
      Verify: Unit test with mocked httpx 403 response; fetcher returns empty list without raising exception. Second test with mocked 200 response and HTML snippet; test extracts job title and company.

- [ ] 7. Implement remote.io fetcher in `app/services/job_fetcher.py`.
      Class `RemoteIoFetcher(JobFetcher)`: fetch from remote.io public API (https://www.remote.io/api/jobs) if available; fallback to scraping public search page if API fails. Set 2-second timeout. Return up to 15 jobs.
      **Note**: Check if remote.io offers a public free API; if not, scrapers use the public HTML. Either way, graceful degradation on timeout.
      Files: `backend/app/services/job_fetcher.py` (append to file)
      Verify: Unit test with mocked httpx response (simulate either API or HTML); test extracts job title, company, description, URL.

### Phase 3: Job Search Schema and Endpoint

- [ ] 8. Create `app/schemas/job_search.py` with JobSearchResult and JobSearchResponse schemas.
      `JobSearchResult`: job_title (str), company_name (str), source_platform (str), source_url (str | None), keyword_match_percentage (float, 0-100), matched_skills (list[str]), ai_assessment (CvJobAiAssessment | None), warnings (list[str] | None).
      `JobSearchResponse`: cv_skills (list[str]), results (list[JobSearchResult]), search_duration_ms (int).
      Files: `backend/app/schemas/job_search.py`
      Verify: Import classes; `JobSearchResult.model_validate({...})` succeeds with valid data; Pydantic validation works.

- [ ] 9. Add search-and-analyze endpoint to `app/api/cv_matches.py`.
      Endpoint: `POST /api/v1/cv-matches/search-and-analyze`
      Form fields: cv_file (UploadFile, required), location (str, optional), job_type (str, optional), experience_level (str, optional), salary_min (int, optional), salary_max (int, optional), keywords (str, optional).
      Implementation:
      a. Validate and extract CV text using existing `_read_cv_text()` helper.
      b. Extract CV skills using `extract_skills(cv_text)`.
      c. Build `JobSearchFilters` from form fields.
      d. Run fetchers concurrently: `asyncio.gather(*[Indeed(...).fetch(filters), LinkedIn(...).fetch(filters), RemoteIo(...).fetch(filters)], return_exceptions=True)`. Catch exceptions and treat as empty lists (graceful degradation).
      e. Merge fetched jobs, deduplicate by (company_name, job_title) hash, then score by keyword match.
      f. Take top 10 by keyword score. If fewer than 10, return all.
      g. Run LLM batch assess via `asyncio.gather(*[analyzer.assess_cv_match(cv_text, job.description) for job in top_10], return_exceptions=True)`. Treat timeout/exception on any call as `ai_assessment = None`.
      h. Build response: map each job + LLM result to `JobSearchResult`.
      i. Enforce total 5-second timeout: wrap entire flow in `asyncio.wait_for(..., timeout=5.0)`. If timeout occurs, return partial results with warning.
      Files: `backend/app/api/cv_matches.py`
      Verify: Run the endpoint in test with mocked fetchers and mocked LLM; verify response schema. Test timeout: mock a slow fetcher, confirm endpoint returns before 5s and includes warning.

### Phase 4: Database Integration and Caching

- [ ] 10. Add cache lookup and write logic to `app/services/job_fetcher.py`.
      Create helper function `cache_lookup(session: AsyncSession, source_platform: str, query_hash: str, ttl_seconds: int) -> list[FetchedJob] | None`.
      Create helper function `cache_write(session: AsyncSession, source_platform: str, query_hash: str, jobs: list[FetchedJob])`.
      Modify each fetcher to check cache first, write miss to cache.
      Files: `backend/app/services/job_fetcher.py` (add functions at module level after fetcher classes)
      Verify: Unit tests for cache_lookup (hit, miss, TTL expiry); cache_write creates row in DB.

- [ ] 11. Integrate caching into endpoint.
      In `search-and-analyze` endpoint, before calling fetchers, compute `query_hash = md5(json.dumps(filters))`. Pass query_hash to each fetcher; they check cache before HTTP call. After fetch, write to cache regardless of source.
      Files: `backend/app/api/cv_matches.py` (modify endpoint)
      Verify: Call endpoint twice with identical filters; second call uses cached results (verify via logging or response timing).

### Phase 5: Error Handling and Resilience

- [ ] 12. Add error handling and logging.
      Wrap each HTTP operation in try-except; log failures at WARNING level. Fetcher timeout or HTTP error → return empty list (not exception). LLM timeout → ai_assessment = None. Add field to JobSearchResult: `analysis_status: Literal["success", "timeout", "error"]` to track per-job LLM result.
      Files: `backend/app/api/cv_matches.py`, `backend/app/services/job_fetcher.py`
      Verify: Integration test: mock one fetcher to fail (raise exception), one to timeout, one to succeed. Verify endpoint returns results from successful source only and includes warnings.

- [ ] 13. Add logging imports and configure for job_fetcher module.
      Import `logging` in `job_fetcher.py`. Use `logger = logging.getLogger(__name__)`. Log at INFO when fetch starts, WARNING on timeout/error, INFO on cache hit.
      Files: `backend/app/services/job_fetcher.py`
      Verify: Run endpoint, check logs include job fetcher messages.

### Phase 6: Testing

- [ ] 14. Write unit tests for job fetchers in `tests/test_job_fetcher.py`.
      Test each fetcher with mocked httpx responses. Verify:
      - `IndeedFetcher`: scrapes HTML and extracts job title, company, description, URL correctly.
      - `LinkedInFetcher`: handles 403 gracefully by returning empty list.
      - `RemoteIoFetcher`: attempts API endpoint and falls back to scrape on 404.
      - Timeout: mock httpx.AsyncClient with 1ms timeout; fetcher returns empty list, not exception.
      - Deduplication: same job from two sources is merged.
      Files: `tests/test_job_fetcher.py`
      Verify: `pytest tests/test_job_fetcher.py` passes all tests.

- [ ] 15. Write integration tests for search-and-analyze endpoint in `tests/test_cv_matches_search_api.py`.
      Test:
      - Endpoint accepts valid CV PDF + filters; returns JobSearchResponse with cv_skills and results.
      - Keyword matching: top 10 jobs are sorted by match_percentage descending.
      - LLM integration: ai_assessment is populated from OpenAICompatibleAgeAnalyzer.
      - Partial failure: mock one fetcher to fail; endpoint returns results from other sources with warning.
      - Timeout: mock slow fetchers; endpoint returns before 5s with partial results.
      - Invalid CV file (non-PDF): returns 415.
      - Cache hit: second call with same filters is faster and returns same results.
      Files: `tests/test_cv_matches_search_api.py`
      Verify: `pytest tests/test_cv_matches_search_api.py` passes; total test execution < 30s.

### Phase 7: Integration and Verification

- [ ] 16. Run full test suite to ensure no regressions.
      `pytest tests/` from backend directory. Verify all existing tests pass.
      Files: (no files modified)
      Verify: `pytest tests/ -v` passes; no failures.

- [ ] 17. Test endpoint manually against live backend.
      Start backend: `python -m uvicorn app.main:app --reload --port 8000`.
      Upload a sample CV PDF via POST to `/api/v1/cv-matches/search-and-analyze` with filters.
      Verify: Response includes cv_skills, results with top 10 jobs, ai_assessment populated or None with explanation.
      Response time: check X-Response-Time header or measure client-side; ensure < 5s.
      Files: (no files modified)
      Verify: Endpoint callable from curl or client; returns valid JSON within latency SLA.

### Phase 8: Documentation

- [ ] 18. Update README.md with new endpoint documentation.
      Add new section under "Endpoint API": document `/api/v1/cv-matches/search-and-analyze` with request/response schema, filters, example curl, and latency expectations.
      Note that results are ranked by keyword match first, then AI assessment fit_level (if populated).
      Note graceful degradation: if sources fail, partial results are returned with warnings.
      Files: `readme.md`
      Verify: Documentation is clear and matches actual endpoint behavior.

## Verification Checklist

- [ ] All new files created with correct Python syntax and imports.
- [ ] `pyproject.toml` has httpx and beautifulsoup4 in main dependencies.
- [ ] Database migration runs successfully; `job_cache` table exists in PostgreSQL.
- [ ] Configuration reads new settings from Settings class; defaults are reasonable.
- [ ] Job fetchers return valid `FetchedJob` objects; no unhandled exceptions.
- [ ] Keyword scoring algorithm correctly identifies top 10 jobs.
- [ ] Endpoint processes 5-job scenario in < 5s (measured end-to-end).
- [ ] Cache write and hit paths work (verified in tests).
- [ ] All 15 tests pass without timeout.
- [ ] Partial failures (one fetcher fails, others succeed) return partial results with warnings.
- [ ] LLM timeout is handled gracefully (ai_assessment = None, not 500 error).
- [ ] Response schema is JSON-serializable and matches CvJobAiAssessment for valid results.
- [ ] README updated with endpoint documentation and latency notes.

## Notes on Latency Budget

Total 5-second SLA breakdown (conservative estimates):
- Fetcher HTTP calls (3 sources × 2s timeout, concurrent): ~2s max
- Job deduplication and scoring: ~0.1s
- LLM batch calls (10 jobs × 3s timeout, concurrent): ~4s max (but gated by 5s total SLA)
- Response serialization and network: ~0.3s
- **Total headroom**: ~1s for other operations and jitter

If total clock exceeds 5s, endpoint raises `asyncio.TimeoutError` and returns 408 Request Timeout with partial results collected so far.

## Graceful Degradation Scenarios

1. **One fetcher times out**: Other fetchers continue; results from active sources returned.
2. **All fetchers fail**: Return empty results list with warning message.
3. **LLM times out for N jobs**: Those jobs have `ai_assessment = None`; others have assessments.
4. **Cache hit on query**: Skip HTTP calls, return in < 100ms (unless results are stale and need refresh).
5. **CV file invalid**: Return 415 Unsupported Media Type (reuse existing `_read_cv_text` behavior).

## Dependency on Existing Code

- `extract_skills(text: str) -> list[str]` from `app/services/cv_matching.py` ✓
- `extract_cv_text(pdf_content: bytes) -> str` from `app/services/cv_matching.py` ✓
- `OpenAICompatibleAgeAnalyzer.assess_cv_match(cv_text, job_description)` from `app/services/age_analysis.py` ✓
- `CvJobAiAssessment` schema from `app/schemas/cv_matches.py` ✓
- `SessionDependency` pattern from `app/api/cv_matches.py` ✓
- Database models and session factory already in place ✓
