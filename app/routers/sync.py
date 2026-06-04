from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.core.auth import get_current_user, require_role
from app.core.responses import success_response
from app.models.analytics import SyncMetadata
from app.schemas.analytics import SyncStatusOut, SyncTriggerResponse
from app.integrations.zoho.oauth import ZohoOAuthManager

router = APIRouter()
logger = structlog.get_logger()


def _get_zoho_client(db: Session):
    from app.integrations.zoho.client import ZohoAPIClient
    oauth = ZohoOAuthManager(db)
    return ZohoAPIClient(oauth)


@router.get("/status", response_model=dict)
def get_sync_status(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get sync status for all entity types."""
    records = db.query(SyncMetadata).filter(
        ~SyncMetadata.entity_type.startswith("oauth_")
    ).all()

    return success_response([SyncStatusOut.model_validate(r).model_dump() for r in records])


@router.post("/full", response_model=dict)
def trigger_full_sync(
    background_tasks: BackgroundTasks,
    current_user=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Trigger a full sync via Celery worker."""
    from app.workers.tasks import run_full_sync
    task = run_full_sync.delay()
    logger.info("full_sync_triggered", task_id=task.id, actor=str(current_user.id))
    return success_response(SyncTriggerResponse(
        message="Full sync queued",
        task_id=task.id,
    ).model_dump())


@router.post("/incremental", response_model=dict)
def trigger_incremental_sync(
    current_user=Depends(require_role("admin", "manager")),
    db: Session = Depends(get_db),
):
    """Trigger an incremental sync (tasks + timesheets only)."""
    from app.workers.tasks import run_incremental_sync
    task = run_incremental_sync.delay()
    logger.info("incremental_sync_triggered", task_id=task.id, actor=str(current_user.id))
    return success_response(SyncTriggerResponse(
        message="Incremental sync queued",
        task_id=task.id,
    ).model_dump())


@router.get("/zoho/auth-url", response_model=dict)
def get_zoho_auth_url(
    current_user=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Get the Zoho OAuth authorization URL for initial setup."""
    oauth = ZohoOAuthManager(db)
    url = oauth.get_authorization_url()
    return success_response({"authorization_url": url})


@router.get("/zoho/callback", response_model=dict)
def zoho_oauth_callback(
    code: str,
    db: Session = Depends(get_db),
):
    """Handle Zoho OAuth callback and exchange code for tokens."""
    oauth = ZohoOAuthManager(db)
    try:
        data = oauth.exchange_code(code)
        logger.info("zoho_oauth_connected")
        return success_response({"message": "Zoho OAuth connected successfully"})
    except Exception as e:
        logger.error("zoho_oauth_callback_error", error=str(e))
        from app.core.exceptions import ZohoAPIError
        raise ZohoAPIError(f"OAuth exchange failed: {str(e)}")
