"""
Root entry point for the Workforce Optimization Platform backend.
Run with: uvicorn main:app --reload
Or via Docker: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from app.main import app  # noqa: F401 - re-export for uvicorn

if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        reload=settings.DEBUG,
    )
