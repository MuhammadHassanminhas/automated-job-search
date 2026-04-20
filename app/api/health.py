from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app import __version__
from app import db as app_db

router = APIRouter()


@router.get("/health")
async def health_check():
    try:
        await app_db.check_connection()
        db_status = "ok"
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "db": "error", "version": __version__},
        )
    return {"status": "ok", "db": db_status, "version": __version__}
