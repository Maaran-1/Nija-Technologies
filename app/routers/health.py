from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis
import structlog

from app.database import get_db
from app.config import settings
from app.core.responses import success_response

router = APIRouter()
logger = structlog.get_logger()


@router.get("/health", response_model=dict, tags=["health"])
def health_check(db: Session = Depends(get_db)):
    """Basic health check: verifies DB and Redis connectivity."""
    checks = {}

    # Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.error("health_db_error", error=str(e))
        checks["database"] = "error"

    # Redis check
    try:
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        logger.warning("health_redis_error", error=str(e))
        checks["redis"] = "error"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"

    return success_response({
        "status": overall,
        "version": settings.APP_VERSION,
        "checks": checks,
    })


@router.get("/health/ready", response_model=dict, tags=["health"])
def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes readiness probe: stricter DB check."""
    try:
        db.execute(text("SELECT 1"))
        return success_response({"ready": True})
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"ready": False, "error": str(e)})


@router.get("/health/live", tags=["health"])
def liveness_check():
    """Kubernetes liveness probe: just returns 200 if app is running."""
    return {"alive": True}
