from datetime import datetime, timezone
import structlog

from app.workers.celery_app import celery_app
from app.database import SessionLocal

logger = structlog.get_logger()


def _get_zoho_client(db):
    from app.integrations.zoho.oauth import ZohoOAuthManager
    from app.integrations.zoho.client import ZohoAPIClient
    oauth = ZohoOAuthManager(db)
    return ZohoAPIClient(oauth)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="app.workers.tasks.run_full_sync")
def run_full_sync(self):
    """Full entity sync: users, projects, tasks, timesheets, milestones."""
    logger.info("celery_full_sync_start")
    db = SessionLocal()
    try:
        client = _get_zoho_client(db)
        from app.integrations.zoho.orchestrator import SyncOrchestrator
        orchestrator = SyncOrchestrator(db, client)
        orchestrator.run_full_sync()

        # Trigger analytics recompute after sync
        run_analytics_recompute.delay()
        logger.info("celery_full_sync_complete")
    except Exception as exc:
        logger.error("celery_full_sync_failed", error=str(exc))
        self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="app.workers.tasks.run_incremental_sync")
def run_incremental_sync(self):
    """Incremental sync: tasks and timesheets only (delta since last sync)."""
    logger.info("celery_incremental_sync_start")
    db = SessionLocal()
    try:
        client = _get_zoho_client(db)
        from app.integrations.zoho.orchestrator import SyncOrchestrator
        orchestrator = SyncOrchestrator(db, client)
        orchestrator.run_incremental_sync()

        # Queue analytics after sync
        run_analytics_recompute.delay()
        logger.info("celery_incremental_sync_complete")
    except Exception as exc:
        logger.error("celery_incremental_sync_failed", error=str(exc))
        self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_analytics_recompute")
def run_analytics_recompute():
    """Recompute utilization snapshots for all active users."""
    logger.info("celery_analytics_recompute_start")
    db = SessionLocal()
    try:
        from app.analytics.utilization_calculator import compute_and_save_utilization_snapshots
        from datetime import date
        count = compute_and_save_utilization_snapshots(db, snapshot_date=date.today())
        logger.info("celery_analytics_recompute_complete", snapshots=count)

        # Queue recommendation generation after analytics
        run_recommendation_generation.delay()
    except Exception as e:
        logger.error("celery_analytics_recompute_failed", error=str(e))
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_project_health_scoring")
def run_project_health_scoring():
    """Recompute project health scores for all active projects."""
    logger.info("celery_project_health_start")
    db = SessionLocal()
    try:
        from app.analytics.project_scorer import score_all_projects
        count = score_all_projects(db)
        logger.info("celery_project_health_complete", scored=count)
    except Exception as e:
        logger.error("celery_project_health_failed", error=str(e))
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_recommendation_generation")
def run_recommendation_generation():
    """Generate task redistribution recommendations."""
    logger.info("celery_recommendation_generation_start")
    db = SessionLocal()
    try:
        from app.recommendations.engine import generate_recommendations
        count = generate_recommendations(db)
        logger.info("celery_recommendation_generation_complete", created=count)
    except Exception as e:
        logger.error("celery_recommendation_generation_failed", error=str(e))
    finally:
        db.close()
