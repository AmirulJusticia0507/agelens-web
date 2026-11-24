from collections.abc import Awaitable
from typing import Any, Protocol
from uuid import UUID


class AnalysisRedis(Protocol):
    def enqueue_job(
        self,
        function_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Awaitable[object | None]: ...


async def enqueue_analysis(redis: AnalysisRedis, job_posting_id: UUID) -> bool:
    job = await redis.enqueue_job(
        "analyze_job_posting",
        str(job_posting_id),
        _job_id=f"age-analysis:{job_posting_id}",
    )
    return job is not None
