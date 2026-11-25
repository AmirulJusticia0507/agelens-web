"""Job fetcher service for dynamic job search from multiple sources."""

import asyncio
import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import httpx
from bs4 import BeautifulSoup

from app.schemas.job_search import JobSearchFilters

logger = logging.getLogger(__name__)


def _normalize_text_for_matching(text: str) -> list[str]:
    """Tokenize and normalize text for skill matching with word boundaries."""
    return re.findall(r"\b\w+\b", text.lower())


def compute_query_hash(filters: JobSearchFilters) -> str:
    """Compute hash of job search filters for cache lookup."""
    filter_dict = filters.model_dump(exclude_none=True)
    filter_json = json.dumps(filter_dict, sort_keys=True)
    return hashlib.md5(filter_json.encode()).hexdigest()


@dataclass
class FetchedJob:
    """Represents a job fetched from a source."""
    job_title: str
    company_name: str
    description: str
    url: str
    source_platform: str
    posted_date: date | None = None


class JobFetcher(ABC):
    """Abstract base class for job fetchers from different sources."""

    def __init__(self, timeout_seconds: float = 2.0):
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def fetch(self, filters: JobSearchFilters) -> list[FetchedJob]:
        """Fetch jobs from the source with given filters.
        
        Returns:
            List of FetchedJob objects. Returns empty list on timeout or error.
        """
        pass


class IndeedFetcher(JobFetcher):
    """Fetches jobs from Indeed public search."""

    async def fetch(self, filters: JobSearchFilters) -> list[FetchedJob]:
        """Fetch jobs from Indeed."""
        try:
            query_params = {
                "q": filters.keywords or "software engineer",
                "l": filters.location or "",
                "jt": filters.job_type or "",
            }
            # Build search URL
            query_str = "&".join(f"{k}={v}" for k, v in query_params.items() if v)
            url = f"https://www.indeed.com/jobs?{query_str}&start=0&limit=25"

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )
                response.raise_for_status()

            # Set encoding explicitly to handle character encoding properly
            soup = BeautifulSoup(response.content, "html.parser", from_encoding=response.encoding)
            jobs = []

            # Indeed job cards have specific structure
            job_cards = soup.find_all("div", class_="job_seen_beacon")
            
            # Log if selectors don't match (structural change detection)
            if not job_cards:
                logger.warning(
                    "Indeed: No job cards found with selector 'div.job_seen_beacon'; "
                    "site structure may have changed"
                )
                return []

            for card in job_cards[:15]:  # Take up to 15 jobs
                try:
                    job_link = card.find("a", class_="jcs-JobTitle")
                    if not job_link:
                        continue

                    job_title = job_link.get_text(strip=True)
                    job_url = job_link.get("href", "")
                    if not job_url.startswith("http"):
                        job_url = f"https://www.indeed.com{job_url}"

                    company_elem = card.find("span", class_="companyName")
                    company_name = (
                        company_elem.get_text(strip=True) if company_elem else "Unknown"
                    )

                    snippet_elem = card.find("div", class_="job-snippet")
                    description = (
                        snippet_elem.get_text(strip=True) if snippet_elem else job_title
                    )

                    jobs.append(
                        FetchedJob(
                            job_title=job_title,
                            company_name=company_name,
                            description=description,
                            url=job_url,
                            source_platform="indeed",
                        )
                    )
                except (AttributeError, IndexError):
                    continue

            logger.info(f"Indeed fetcher retrieved {len(jobs)} jobs from {len(job_cards)} cards")
            return jobs

        except asyncio.TimeoutError:
            logger.warning("Indeed fetcher timed out")
            return []
        except httpx.HTTPError as e:
            logger.warning(f"Indeed fetcher HTTP error: {e}")
            return []
        except Exception as e:
            logger.warning(f"Indeed fetcher error: {e}")
            return []





class RemoteIoFetcher(JobFetcher):
    """Fetches jobs from remote.io."""

    async def fetch(self, filters: JobSearchFilters) -> list[FetchedJob]:
        """Fetch jobs from remote.io."""
        try:
            # Try remote.io public search/API first
            url = "https://www.remote.io/api/jobs"
            params = {"limit": 25}
            if filters.keywords:
                params["q"] = filters.keywords
            if filters.location:
                params["location"] = filters.location

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                try:
                    # Try API endpoint
                    response = await client.get(url, params=params)
                    response.raise_for_status()

                    try:
                        data = response.json()
                    except json.JSONDecodeError as e:
                        logger.warning(f"remote.io API returned invalid JSON: {e}")
                        return await self._scrape_remote_io(filters)

                    jobs = []

                    # API response structure may vary; validate schema
                    if isinstance(data, dict):
                        job_list = data.get("jobs", [])
                        if not isinstance(job_list, list):
                            logger.warning(
                                f"remote.io API schema mismatch: 'jobs' field is {type(job_list)}, expected list"
                            )
                            return await self._scrape_remote_io(filters)
                    elif isinstance(data, list):
                        job_list = data
                    else:
                        logger.warning(
                            f"remote.io API response type unexpected: {type(data)}, expected dict or list"
                        )
                        return await self._scrape_remote_io(filters)

                    for job_data in job_list[:15]:
                        if isinstance(job_data, dict):
                            jobs.append(
                                FetchedJob(
                                    job_title=job_data.get("title", "Unknown"),
                                    company_name=job_data.get("company", "Unknown"),
                                    description=job_data.get("description", "")
                                    or job_data.get("title", ""),
                                    url=job_data.get("url", ""),
                                    source_platform="remote.io",
                                )
                            )

                    logger.info(f"remote.io API fetcher retrieved {len(jobs)} jobs")
                    return jobs

                except httpx.HTTPError as e:
                    # Fallback to HTML scraping if API fails
                    logger.debug(f"remote.io API failed ({e}); falling back to scraping")
                    return await self._scrape_remote_io(filters)

        except asyncio.TimeoutError:
            logger.warning("remote.io fetcher timed out")
            return []
        except Exception as e:
            logger.warning(f"remote.io fetcher error: {e}")
            return []

    async def _scrape_remote_io(self, filters: JobSearchFilters) -> list[FetchedJob]:
        """Scrape remote.io web page as fallback."""
        try:
            query = filters.keywords or "software engineer"
            url = f"https://www.remote.io/remote-jobs?search={query}"

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )
                response.raise_for_status()

            # Set encoding explicitly
            soup = BeautifulSoup(response.content, "html.parser", from_encoding=response.encoding)
            jobs = []

            # remote.io job cards
            job_cards = soup.find_all("div", class_="job-card")
            
            # Log if selectors don't match (structural change detection)
            if not job_cards:
                logger.warning(
                    "remote.io scraper: No job cards found with selector 'div.job-card'; "
                    "site structure may have changed"
                )
                return []

            for card in job_cards[:15]:
                try:
                    job_link = card.find("a", class_="job-title")
                    if not job_link:
                        continue

                    job_title = job_link.get_text(strip=True)
                    job_url = job_link.get("href", "")
                    if not job_url.startswith("http"):
                        job_url = f"https://www.remote.io{job_url}"

                    company_elem = card.find("span", class_="company-name")
                    company_name = (
                        company_elem.get_text(strip=True) if company_elem else "Unknown"
                    )

                    description_elem = card.find("p", class_="job-description")
                    description = (
                        description_elem.get_text(strip=True) if description_elem else job_title
                    )

                    jobs.append(
                        FetchedJob(
                            job_title=job_title,
                            company_name=company_name,
                            description=description,
                            url=job_url,
                            source_platform="remote.io",
                        )
                    )
                except (AttributeError, IndexError):
                    continue

            logger.info(f"remote.io scraper retrieved {len(jobs)} jobs from {len(job_cards)} cards")
            return jobs

        except asyncio.TimeoutError:
            logger.warning("remote.io scraper timed out")
            return []
        except httpx.HTTPError as e:
            logger.warning(f"remote.io scraper HTTP error: {e}")
            return []
        except Exception as e:
            logger.warning(f"remote.io scraper error: {e}")
            return []


def deduplicate_jobs(jobs: list[FetchedJob]) -> list[FetchedJob]:
    """Deduplicate jobs by (company_name, job_title) hash."""
    seen = set()
    unique_jobs = []

    for job in jobs:
        # Create a canonical key for deduplication
        key = f"{job.company_name.lower()}:{job.job_title.lower()}".strip()
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)

    return unique_jobs
