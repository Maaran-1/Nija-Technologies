from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import json
import uuid
import structlog

from app.database import get_db
from app.core.auth import get_current_user, require_role
from app.core.exceptions import NotFoundError, ForbiddenError
from app.core.responses import success_response, paginated_response
from app.models.task import Task
from app.models.user import User
from app.models.recommendation import AuditLog
from app.schemas.project import TaskOut, TaskAssignRequest

router = APIRouter()
logger = structlog.get_logger()


@router.get("", response_model=dict)
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    project_id: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[int] = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List tasks with filters."""
    query = db.query(Task)
    if project_id:
        query = query.filter(Task.project_id == project_id)
    if assigned_to:
        query = query.filter(Task.assigned_to == assigned_to)
    if status:
        query = query.filter(Task.status == status)
    if priority is not None:
        query = query.filter(Task.priority == priority)

    total = query.count()
    tasks = query.offset((page - 1) * page_size).limit(page_size).all()

    return paginated_response(
        [TaskOut.model_validate(t).model_dump() for t in tasks],
        page, page_size, total,
    )


@router.get("/{task_id}", response_model=dict)
def get_task(
    task_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise NotFoundError("Task", task_id)

    return success_response(TaskOut.model_validate(task).model_dump())


@router.patch("/{task_id}/assign", response_model=dict)
def assign_task(
    task_id: str,
    payload: TaskAssignRequest,
    current_user=Depends(require_role("admin", "manager")),
    db: Session = Depends(get_db),
):
    """Manually reassign a task to a user (or unassign)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise NotFoundError("Task", task_id)

    previous_assignee = str(task.assigned_to) if task.assigned_to else None

    if payload.user_id:
        user = db.query(User).filter(User.id == payload.user_id, User.is_active == True).first()
        if not user:
            raise NotFoundError("User", str(payload.user_id))
        task.assigned_to = payload.user_id
        new_assignee = str(payload.user_id)
    else:
        task.assigned_to = None
        new_assignee = None

    db.commit()

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        action="task_manually_reassigned",
        actor_id=current_user.id,
        entity_type="task",
        entity_id=task.id,
        metadata=json.dumps({
            "previous_assignee": previous_assignee,
            "new_assignee": new_assignee,
        }),
    )
    db.add(audit)
    db.commit()

    logger.info("task_assigned_manually", task_id=task_id, new_assignee=new_assignee)
    return success_response(TaskOut.model_validate(task).model_dump())
