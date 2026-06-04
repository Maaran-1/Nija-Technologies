from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import time

from app.config import settings
from app.core.exceptions import WOPException
from app.core.logging_config import configure_logging

configure_logging()
logger = structlog.get_logger()


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )
        return response

    # Exception handlers
    @app.exception_handler(WOPException)
    async def wop_exception_handler(request: Request, exc: WOPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"data": None, "meta": {}, "errors": [{"message": exc.message, "code": exc.error_code}]},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_exception", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"data": None, "meta": {}, "errors": [{"message": "Internal server error", "code": "INTERNAL_ERROR"}]},
        )

    # Routers
    from app.routers import health, auth, users, projects, tasks, utilization, recommendations, analytics, sync
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
    app.include_router(utilization.router, prefix="/api/v1/utilization", tags=["utilization"])
    app.include_router(recommendations.router, prefix="/api/v1/recommendations", tags=["recommendations"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
    app.include_router(sync.router, prefix="/api/v1/sync", tags=["sync"])

    @app.on_event("startup")
    async def startup_event():
        logger.info("application_starting", version=settings.APP_VERSION)

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("application_shutting_down")

    return app


app = create_application()
