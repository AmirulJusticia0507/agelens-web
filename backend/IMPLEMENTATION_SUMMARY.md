# RAG-Based Job Search with LLM Analysis - Implementation Summary

## Files Created/Modified

### 1. **Configuration Updates**
- **File**: `app/config.py`
  - Added job search settings:
    - `job_search_timeout_seconds: float = 5.0` (total SLA)
    - `job_search_per_source_timeout_seconds: float = 2.0` (per-fetcher timeout)
    - `job_search_llm_timeout_seconds: float = 3.0` (per-LLM-call timeout)
    - `job_search_cache_ttl_seconds: int = 3600` (1-hour TTL)
    - `job_search_max_results: int = 10` (top N jobs to return)

### 2. **Schemas**
- **File**: `app/schemas/job_search.py` (NEW)
  - `JobSearchFilters`: Query filters (location, job_type, experience_level, salary_min/max, keywords)
  - `JobSearchResult`: Single job result with keyword matching and AI assessment
  - `JobSearchResponse`: Response containing CV skills, results list, duration, and warnings

### 3. **Job Fetcher Service**
- **File**: `app/services/job_fetcher.py` (NEW)
  - `FetchedJob`: Dataclass for raw job data from sources
  - `JobFetcher`: Abstract base class for fetchers
  - `IndeedFetcher`: Scrapes Indeed public search (HTML parsing)
  - `LinkedInFetcher`: Scrapes LinkedIn public search (graceful degradation on 403/429)
  - `RemoteIoFetcher`: Attempts API first, falls back to scraping
  - `compute_query_hash()`: MD5 hash for cache keys
  - `deduplicate_jobs()`: Removes duplicate jobs by company+title

### 4. **API Endpoint**
- **File**: `app/api/cv_matches.py` (MODIFIED)
  - Added `POST /api/v1/cv-matches/search-and-analyze` endpoint
  - Accepts: CV file (PDF), optional filters (location, job_type, experience_level, salary_min/max, keywords)
  - Workflow:
    1. Extract and validate CV text
    2. Extract skills from CV using `extract_skills()`
    3. Fetch jobs concurrently from 3 sources via `asyncio.gather()`
    4. Deduplicate jobs
    5. Score jobs by keyword matching (matched_skills / cv_skills * 100)
    6. Take top 10 by score
    7. Run LLM `assess_cv_match()` concurrently on top 10 jobs
    8. Build response with results, durations, and warnings
    9. Total timeout: 5 seconds with graceful degradation

### 5. **Dependencies**
- **File**: `backend/pyproject.toml` (MODIFIED)
  - Promoted `httpx>=0.27,<1.0` from dev to main dependencies
  - Added `beautifulsoup4>=4.12,<5.0` to main dependencies

### 6. **Tests**
- **File**: `tests/test_job_search.py` (NEW)
  - Unit tests for job fetchers with mocked HTTP responses
  - Tests for utility functions (compute_query_hash, deduplicate_jobs)
  - Tests for schema validation
  - Tests for graceful degradation and timeout handling

## Implementation Details

### Latency Budget (5 seconds total)
- Job fetching (3 sources concurrent): ~2s max
- Job scoring and deduplication: ~0.1s
- LLM analysis (10 jobs concurrent): ~4s max (gated by overall 5s limit)
- Serialization and network: ~0.3s
- **Buffer**: ~1s for jitter/overhead

### Graceful Degradation
1. **Source Failure**: Other sources continue; partial results returned with warnings
2. **All Sources Fail**: Return 404 with "No jobs found" message
3. **LLM Timeout**: Set `ai_assessment = None`, `analysis_status = "timeout"`
4. **LLM Error**: Set `ai_assessment = None`, `analysis_status = "error"`
5. **Job Fetch Timeout**: Log warning, return empty list from affected source

### Error Handling
- CV file validation: Returns 415 if not PDF, 422 if no extractable text
- Invalid filters: Pydantic automatically validates optional fields
- HTTP errors: Logged and handled gracefully per source
- Timeout errors: Per-source timeout doesn't block others

## Testing Strategy

1. **Unit Tests** (`test_job_search.py`):
   - Fetcher timeout handling
   - LinkedIn graceful degradation (403)
   - Query hash consistency
   - Job deduplication
   - Schema validation

2. **Integration Tests** (to be added if needed):
   - End-to-end endpoint test with mocked fetchers/LLM
   - Timeout scenarios
   - Partial failure scenarios

3. **Manual Testing**:
   - Upload sample CV to `/api/v1/cv-matches/search-and-analyze`
   - Verify response includes cv_skills, top 10 jobs, AI assessments
   - Confirm response time < 5 seconds

## Key Design Decisions

1. **HTTP Scraping vs. Official APIs**:
   - Indeed: No free official API; HTML scraping is documented workaround
   - LinkedIn: Scraping restricted but public search pages accessible; graceful 403 handling
   - remote.io: Attempted API first with HTML fallback

2. **Concurrency Model**:
   - `asyncio.gather()` for all fetchers (I/O-bound parallelism)
   - Per-source 2s timeout prevents slow sources from blocking others
   - Per-job LLM timeout ensures completion within overall 5s SLA

3. **Keyword Matching**:
   - Reuses existing `extract_skills()` from cv_matching.py
   - Case-insensitive matching within job description + title
   - Score = (matched_skills / cv_skills) * 100

4. **Response Schema**:
   - Reuses existing `CvJobAiAssessment` schema
   - Added `analysis_status` field to track per-job LLM success/failure
   - Warnings list for non-fatal errors
   - Includes cv_skills for transparency on matching criteria

## Known Limitations

1. **Job Source Restrictions**:
   - LinkedIn actively blocks scrapers; may return empty results
   - Indeed's HTML structure may change without notice
   - remote.io API endpoint may change or be deprecated

2. **Search Quality**:
   - Keyword matching is simple substring-based (not semantic)
   - No location filtering or salary range filtering on results
   - Results depend on what sources return for given query

3. **Performance**:
   - 5-second timeout is strict; may cut off results on slow networks
   - LLM analysis on 10 jobs takes ~3-4 seconds (depends on model)
   - No caching of job listings across requests (as specified)

## Next Steps

1. Run test suite: `pytest tests/test_job_search.py -v`
2. Test endpoint manually with sample CV
3. Monitor logs for fetcher failures and timeouts
4. Tune timeouts based on actual network conditions
5. Consider pagination if more than 10 results needed
