from fastapi import FastAPI

from app.api.applications import router as applications_router
from app.api.auth import router as auth_router
from app.api.drafts import router as drafts_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.logging import configure_logging

configure_logging()

app = FastAPI(title="Internship Intel", version="0.1.0")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(drafts_router)
app.include_router(applications_router)
