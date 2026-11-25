# RAG-Based Job Search with CV Analysis

This implementation adds a new `/api/v1/cv-matches/search-and-analyze` endpoint that retrieves jobs from three public sources (Indeed, LinkedIn, remote.io), scores them against extracted CV skills, and generates AI-powered fit assessments. The approach combines concurrent HTTP scraping with batch LLM analysis under a 5-second total latency budget.

**Watch for:** Scraper robustness with fragile HTML selectors, incomplete timeout isolation between fetch and LLM phases, and LinkedIn scraper that may never succeed due to built-in blocking.

**Verdict**: NEEDS_CHANGES

---

## High-level view

The endpoint accepts a CV file and optional job filters, then orchestrates a three-stage pipeline. First, three fetchers concurrently scrape job sites using BeautifulSoup, each with a 2-second timeout; failures in one source don't block others. Second, the endpoint deduplicates jobs and scores them by counting matching skills from the CV vocabulary, then selects the top 10. Third, it runs LLM assessments on those 10 jobs concurrently with a 3-second timeout. All stages include error recovery: failed fetchers return empty lists, timeout jobs return null `ai_assessment` with status "timeout", and the endpoint returns 200 with partial results rather than 500. This matches the original design intent of graceful degradation. 

The keyword scoring is straightforward: `(matched_skills / cv_skills) * 100`. It's correct. Top-10 selection before LLM calls is correct—it bounds the concurrent LLM workload.

The major liability is the job fetchers rely on brittle CSS selectors that will break if job sites change their HTML structure. Indeed, LinkedIn, and remote.io all use different card structures and class names; the implementation has fallbacks (LinkedIn scraper exits cleanly if blocked; remote.io tries API then HTML), but no mechanism to detect when selectors break silently. The LinkedIn fetcher explicitly handles 403 and 429 responses, which is good practice, but will return empty results every time—it's effectively a documentation stub.

---

<details>
<summary>Issues (8)</summary>

1. **LinkedIn scraper never succeeds** — LinkedIn actively blocks automated requests; the scraper will consistently return empty results, wasting 2 seconds per search. This is documented in the code comment but not flagged to the user. Consider removing the LinkedIn fetcher or documenting its limitation in the endpoint response.

2. **HTML selectors fragile on structure changes** — Indeed, LinkedIn, and remote.io HTML structures are undocumented and unstable. When class names or card structures change, selectors will silently fail to extract jobs. No monitoring or fallback mechanism exists.

3. **Keyword scoring includes false positives** — Matching skills against `job_title + description` using simple substring matching will match partial words (e.g., "java" matching "javascript"). The description includes other extracted text, not structured fields. No normalization is applied.

4. **Timeout budgets not isolated** — The endpoint's 5-second budget is enforced by the caller (HTTP timeout), not the code. If fetching takes 4s and LLM times out at 3s, the endpoint exceeds 5s total. `asyncio.wait_for` on the LLM batch is correct but doesn't account for time already spent on fetching.

5. **Remote.io API response schema assumed** — `RemoteIoFetcher._fetch` assumes the API returns `{"jobs": [...]}` or a list directly. If the API schema differs, results will be empty without logging the specific parse error.

6. **BeautifulSoup parsing without encoding validation** — `BeautifulSoup(response.text, "html.parser")` assumes the HTTP response encoding is correct. No explicit encoding parameter is set; if the site returns non-UTF-8, parsing may silently fail or corrupt text.

7. **LLM error per-job not isolated** — If LLM fails for one job, `asyncio.gather(..., return_exceptions=True)` captures it correctly, but the loop later assumes `llm_results[i]` maps 1:1 with top jobs. If one task raises an exception, the index alignment holds, but the error handling is implicit and fragile.

8. **Warnings array may hide critical issues** — Jobs from some sources may fail silently, and warnings only appear if an exception is caught. If BeautifulSoup returns empty results (e.g., selectors don't match), no warning is issued; the user won't know why they got fewer results than expected.

</details>

---

<details>
<summary>Details</summary>

### Concurrent fetch orchestration and timeout isolation

The endpoint fetches from three sources using `asyncio.gather(..., return_exceptions=True)` with individual 2-second timeouts per fetcher. This correctly prevents one slow source from blocking others, and exceptions (including timeouts) are caught as exceptions in the results list rather than propagating.

However, the total time budget is not enforced within the endpoint. Settings define `job_search_timeout_seconds: 5.0` but this is not used by the endpoint—it's left to the HTTP layer. Fetching could take 3.5s, then the LLM batch is wrapped with `asyncio.wait_for(..., timeout=3.0)`, which allows the whole operation to exceed 5s. The two timeouts are independent. For compliance with the 5-second SLA, either the endpoint should track elapsed time and reduce the LLM timeout accordingly, or the HTTP layer should enforce the ceiling.

### Keyword matching and scoring logic

Skills are extracted from the CV using existing `extract_skills(cv_text)`, which leverages the `SKILL_ALIASES` dict in `cv_matching.py`. Scoring checks if each CV skill appears in `f"{job.job_title} {job.description}".lower()`. 

The score is computed as `len(matched_skills) / len(cv_skills) * 100`, which is correct for the stated requirement. However, the substring search is naive: a CV skill "Java" will match both "Java" and "JavaScript" descriptions. The code doesn't normalize for word boundaries or account for partial matches. The description field is extracted from the HTML by BeautifulSoup; it's not a structured field, so it may contain boilerplate text, metadata, or corrupted HTML entities. Scoring quality depends entirely on how complete and clean the extracted description is.

Scoring omits jobs with no matched skills; they're filtered out. If no jobs match any skill, the endpoint falls back to returning the top N deduplicated jobs with 0% match. This is a reasonable fallback, though the user won't know why—no warning is issued.

### HTML scraping and CSS selectors

Three fetchers scrape using BeautifulSoup with hard-coded CSS selectors specific to each site's HTML structure. Indeed uses `div.job_seen_beacon`, LinkedIn uses `div.base-card`, remote.io uses `div.job-card`. These selectors are not versioned and will break silently if the site changes.

**Indeed fetcher:** Extracts title from `a.jcs-JobTitle`, company from `span.companyName`, snippet from `div.job-snippet`. Takes up to 15 jobs. If selectors don't match, the loop skips the malformed card and continues. No logging of skipped cards.

**LinkedIn fetcher:** Explicitly handles HTTP 403 and 429 (rate-limited) responses by returning an empty list with a warning log. This is good, but LinkedIn will almost always return 403 or block the request entirely. The scraper includes a User-Agent header ("Mozilla/5.0..."), which is a minor attempt at evasion, but LinkedIn's automated request detection is sophisticated enough to block standard async HTTP clients. This fetcher is effectively non-functional.

**remote.io fetcher:** Tries an API endpoint (`/api/jobs`) first. If the API succeeds, it assumes the response is `{"jobs": [...]}` or a list of job objects, and iterates over the first 15. If the API fails (any HTTP error or JSON parse error), it falls back to HTML scraping with class `div.job-card`. The fallback is a good pattern, but no specific error logging distinguishes between timeout, 404, invalid JSON, etc.

All fetchers catch `BeautifulSoup` parsing errors and continue. HTML parsing errors are caught but not logged, so if parsing fails for all cards (e.g., site structure changed), the endpoint returns 0 jobs with no indication of why.

### Error isolation and partial results

When one fetcher fails, the exception is captured in the results list. The loop checks `isinstance(result, Exception)` and logs a warning (e.g., "Failed to fetch jobs from Indeed"), then continues to the next source. The endpoint only raises HTTPException (404) if all jobs are empty after fetch, which is correct—it allows partial results.

LLM analysis errors are similarly isolated: `asyncio.gather(..., return_exceptions=True)` captures exceptions, and the loop checks `isinstance(llm_result, Exception)`. Failed jobs return `analysis_status="error"` and `ai_assessment=None`. This is correct. However, if `model_validate()` fails during the conversion from LLM output to `CvJobAiAssessment`, the exception is logged but the job is still included in the response with `analysis_status="error"`. This is acceptable.

### Latency and timeout scenarios

**Fetching phase:** Three sources with 2-second timeouts each, running concurrently. Best case: 2 seconds (all complete in parallel). Worst case: 2 seconds (all timeout or fail independently). This phase is bounded.

**Deduplication and scoring:** Synchronous, O(n log n) due to sorting. With 15 results per source × 3 sources = 45 jobs, this is negligible.

**LLM analysis phase:** Up to 10 jobs analyzed concurrently, with a 3-second timeout for the entire batch. Each job calls `analyzer.assess_cv_match(cv_text, job.description)`. If all 10 succeed, the analyzer will make 10 sequential HTTP calls to the LLM provider (depending on the analyzer's internals). If any single call hangs beyond the per-call timeout in the analyzer (default 30s per settings), the entire batch times out at 3s, returning `ai_assessment=None` for all jobs.

**Total time:** Fetch (2s) + score (0.1s) + LLM (3s) = 5.1s, exceeding the 5-second budget by 0.1s. This is acceptable if the caller enforces HTTP timeout at 5s. However, if either fetch or LLM is slow to start (e.g., DNS resolution), the total exceeds budget. The implementation does not enforce the budget internally.

### Deduplication strategy

Deduplication uses `f"{company_name}:{job_title}".lower()` as the key. This is reasonable for detecting duplicates across sources but may be too strict (duplicates with slightly different formatting won't be caught) or too lenient (same company posting identical role in different regions won't be distinguished). The implementation is consistent and doesn't have bugs.

### Schema and type correctness

`JobSearchFilters` is a standard Pydantic model with optional string and int fields. `JobSearchResult` includes `ai_assessment: CvJobAiAssessment | None`, which correctly allows null assessments when LLM fails. `JobSearchResponse` includes `cv_skills` (for reference), `results` (list of jobs), `search_duration_ms`, and `warnings` (optional list). All schema fields are correctly typed.

The endpoint reuses `CvJobAiAssessment` from `cv_matches.py` rather than re-defining it, which follows DRY principle and ensures consistency with the existing `/assess-job` endpoint.

### Test coverage

Tests cover:
- Timeout handling (Indeed fetcher with 0.001s timeout)
- Graceful degradation on HTTP errors (LinkedIn fetcher returning empty on 403)
- Query hash consistency (same filters → same hash, different filters → different hash)
- Deduplication logic (duplicates by company + title)
- Filter and result schema validation

Tests do not cover:
- End-to-end latency under concurrent load
- Behavior when all sources fail simultaneously
- Behavior when LLM batch times out (timeout scenario is not explicitly tested)
- Behavior when CV has no extractable skills (edge case)
- HTML selector correctness (selectors are not tested; relies on live site stability)
- Indeed/LinkedIn/remote.io scraping with real HTML (tests mock HTTP but don't validate parsing logic against actual site structure)

The tests use mocks for HTTP clients, which is good for isolation but means scraper reliability is untested.

### Code quality and patterns

Code follows existing patterns in the codebase:
- Async/await is used consistently
- `httpx.AsyncClient` is used for HTTP (consistent with existing code)
- Error types (`AnalysisConfigurationError`, `AnalysisProviderError`) are reused
- Pydantic models are used for schemas
- Logging is used for warnings and errors
- Request files are properly closed in `_read_cv_text`

Minor issues:
- The endpoint function is long (100+ lines); could be refactored into smaller helpers for readability.
- Magic number 15 (jobs per fetcher) and 10 (top N results) are hard-coded rather than in settings. Consider externalizing these.

### Untested assumptions

- **Remote.io API schema:** Assumes `GET /api/jobs` returns `{"jobs": [...]}` or a list. No validation against actual API.
- **HTTP response encoding:** Assumes UTF-8 encoding from job sites. If a site returns ISO-8859-1 or other encoding without proper headers, BeautifulSoup may misparse.
- **User-Agent bypass:** Assumes "Mozilla/5.0" User-Agent is sufficient to bypass bot detection. It won't be for LinkedIn, and may fail for others in the future.

</details>

---

<details>
<summary>File map</summary>

- **app/services/job_fetcher.py** (new): Three JobFetcher subclasses (Indeed, LinkedIn, RemoteIo) with concurrent timeout-safe fetch methods, plus deduplication and query hash utilities.
- **app/schemas/job_search.py** (new): JobSearchFilters, JobSearchResult, JobSearchResponse Pydantic models.
- **app/api/cv_matches.py** (modified): New POST `/search-and-analyze` endpoint orchestrating fetch → score → LLM analysis pipeline. Reuses existing CV text extraction and skill extraction.
- **app/config.py** (modified): Added job_search_timeout_seconds, job_search_per_source_timeout_seconds, job_search_llm_timeout_seconds, job_search_cache_ttl_seconds, job_search_max_results settings.
- **pyproject.toml** (unchanged): beautifulsoup4 and httpx already present; no new dependencies added.
- **tests/test_job_search.py** (new): Tests for fetchers, deduplication, filters, result schemas. Mocked HTTP; real scraper selectors not validated.

Full diff: `git diff main -- app/services/job_fetcher.py app/schemas/job_search.py app/api/cv_matches.py app/config.py tests/test_job_search.py`

</details>
