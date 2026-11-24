from fastapi import FastAPI

from app.api.companies import router as companies_router
from app.api.health import router as health_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(companies_router, prefix=settings.api_v1_prefix)
