from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI

from app.api.analytics import router as analytics_router
from app.api.companies import router as companies_router
from app.api.cv_matches import router as cv_matches_router
from app.api.health import router as health_router
from app.api.location import router as location_router
from app.api.submissions import router as submissions_router
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    app.state.analysis_redis = redis
    try:
        yield
    finally:
        await redis.aclose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(location_router, prefix=settings.api_v1_prefix)
app.include_router(analytics_router, prefix=settings.api_v1_prefix)
app.include_router(companies_router, prefix=settings.api_v1_prefix)
app.include_router(cv_matches_router, prefix=settings.api_v1_prefix)
app.include_router(submissions_router, prefix=settings.api_v1_prefix)
