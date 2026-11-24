from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionFactory
from app.services.analysis_queue import AnalysisRedis


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def get_analysis_redis(request: Request) -> AnalysisRedis:
    return request.app.state.analysis_redis
