from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

from app.api.analytics import router as analytics_router
from app.api.applications import router as applications_router
from app.api.auth import router as auth_router
from app.api.auth_gmail import router as gmail_router
from app.api.drafts import router as drafts_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.outreach import router as outreach_router
from app.auth.ratelimit import limiter, rate_limit_exceeded_handler
from app.logging import configure_logging
from app.scheduler import create_scheduler

configure_logging()


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    scheduler = create_scheduler()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(title="Internship Intel", version="0.1.0", lifespan=_lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(gmail_router)
app.include_router(jobs_router)
app.include_router(drafts_router)
app.include_router(applications_router)
app.include_router(outreach_router)
app.include_router(analytics_router)
