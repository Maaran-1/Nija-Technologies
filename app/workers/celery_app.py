from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "wop",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Persist the beat schedule so it survives container restarts.
    # Without this, beat resets on every restart and may trigger tasks immediately.
    beat_schedule_filename="/tmp/celerybeat-schedule",
    beat_schedule={
        "full-sync-hourly": {
            "task": "app.workers.tasks.run_full_sync",
            "schedule": settings.FULL_SYNC_INTERVAL_SECONDS,
        },
        "incremental-task-sync": {
            "task": "app.workers.tasks.run_incremental_sync",
            "schedule": settings.TASK_SYNC_INTERVAL_SECONDS,
        },
        "analytics-recompute-daily": {
            "task": "app.workers.tasks.run_analytics_recompute",
            "schedule": crontab(hour=2, minute=0),
        },
        "project-health-scoring": {
            "task": "app.workers.tasks.run_project_health_scoring",
            "schedule": 14400,  # Every 4 hours
        },
        "recommendation-generation": {
            "task": "app.workers.tasks.run_recommendation_generation",
            # Run shortly after incremental sync to ensure fresh data
            "schedule": settings.TASK_SYNC_INTERVAL_SECONDS + 120,
        },
    },
)
