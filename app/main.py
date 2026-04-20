from fastapi import FastAPI

from app.api.health import router as health_router
from app.logging import configure_logging

configure_logging()

app = FastAPI(title="Internship Intel", version="0.1.0")
app.include_router(health_router)
