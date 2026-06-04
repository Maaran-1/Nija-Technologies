from datetime import datetime, timezone
from typing import Optional
import structlog
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.integrations.zoho.client import ZohoAPIClient
from app.integrations.zoho.normalizer import (
    normalize_user, normalize_project, normalize_task,
    normalize_timesheet, normalize_milestone,
)
from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.models.timesheet import TimesheetEntry, Milestone
from app.models.analytics import SyncMetadata
import uuid

logger = structlog.get_logger()


class SyncOrchestrator:
    """Coordinates Zoho data ingestion in dependency order."""

    def __init__(self, db: Session, client: ZohoAPIClient):
        self.db = db
        self.client = client

    def _get_last_sync(self, entity_type: str) -> Optional[datetime]:
        record = self.db.query(SyncMetadata).filter(SyncMetadata.entity_type == entity_type).first()
        return record.last_synced_at if record else None

    def _update_sync_metadata(self, entity_type: str, count: int, status: str, error: str = None):
        record = self.db.query(SyncMetadata).filter(SyncMetadata.entity_type == entity_type).first()
        if not record:
            record = SyncMetadata(entity_type=entity_type)
            self.db.add(record)
        record.last_synced_at = datetime.now(timezone.utc)
        record.last_sync_count = count
        record.last_sync_status = status
        record.last_error = error
        self.db.commit()

    def sync_users(self) -> int:
        logger.info("sync_users_start")
        try:
            zoho_users = self.client.get_users()
            count = 0
            for zu in zoho_users:
                normalized = normalize_user(zu)
                if not normalized["zoho_user_id"] or not normalized["email"]:
                    continue
                stmt = insert(User).values(
                    id=uuid.uuid4(),
                    synced_at=datetime.now(timezone.utc),
                    **normalized,
                ).on_conflict_do_update(
                    index_elements=["zoho_user_id"],
                    set_={
                        "name": normalized["name"],
                        "email": normalized["email"],
                        "role": normalized["role"],
                        "is_active": normalized["is_active"],
                        "synced_at": datetime.now(timezone.utc),
                    },
                )
                self.db.execute(stmt)
                count += 1
            self.db.commit()
            self._update_sync_metadata("users", count, "success")
            logger.info("sync_users_complete", count=count)
            return count
        except Exception as e:
            self.db.rollback()
            self._update_sync_metadata("users", 0, "failed", str(e))
            logger.error("sync_users_failed", error=str(e))
            raise

    def sync_projects(self, delta: bool = False) -> int:
        logger.info("sync_projects_start", delta=delta)
        try:
            last_sync = self._get_last_sync("projects") if delta else None
            updated_time = last_sync.strftime("%m-%d-%Y") if last_sync else None
            zoho_projects = self.client.get_projects(updated_time=updated_time)
            count = 0
            for zp in zoho_projects:
                normalized = normalize_project(zp)
                if not normalized["zoho_project_id"]:
                    continue
                stmt = insert(Project).values(
                    id=uuid.uuid4(),
                    synced_at=datetime.now(timezone.utc),
                    **normalized,
                ).on_conflict_do_update(
                    index_elements=["zoho_project_id"],
                    set_={
                        "name": normalized["name"],
                        "status": normalized["status"],
                        "start_date": normalized["start_date"],
                        "end_date": normalized["end_date"],
                        "budget_hours": normalized["budget_hours"],
                        "description": normalized["description"],
                        "synced_at": datetime.now(timezone.utc),
                    },
                )
                self.db.execute(stmt)
                count += 1
            self.db.commit()
            self._update_sync_metadata("projects", count, "success")
            logger.info("sync_projects_complete", count=count)
            return count
        except Exception as e:
            self.db.rollback()
            self._update_sync_metadata("projects", 0, "failed", str(e))
            logger.error("sync_projects_failed", error=str(e))
            raise

    def sync_tasks(self, delta: bool = True) -> int:
        logger.info("sync_tasks_start", delta=delta)
        try:
            last_sync = self._get_last_sync("tasks") if delta else None
            updated_time = last_sync.strftime("%m-%d-%Y") if last_sync else None

            projects = self.db.query(Project).filter(Project.status == "active").all()
            # Build lookup maps
            user_map = {u.zoho_user_id: u.id for u in self.db.query(User).all()}
            project_map = {p.zoho_project_id: p.id for p in projects}

            count = 0
            for project in projects:
                zoho_tasks = self.client.get_tasks(project.zoho_project_id, updated_time=updated_time)
                for zt in zoho_tasks:
                    normalized = normalize_task(zt, project.zoho_project_id)
                    if not normalized["zoho_task_id"]:
                        continue

                    internal_project_id = project_map.get(normalized.pop("zoho_project_id"))
                    assignee_zoho_id = normalized.pop("assignee_zoho_id", None)
                    assigned_to = user_map.get(assignee_zoho_id) if assignee_zoho_id else None

                    stmt = insert(Task).values(
                        id=uuid.uuid4(),
                        project_id=internal_project_id,
                        assigned_to=assigned_to,
                        synced_at=datetime.now(timezone.utc),
                        **normalized,
                    ).on_conflict_do_update(
                        index_elements=["zoho_task_id"],
                        set_={
                            "title": normalized["title"],
                            "status": normalized["status"],
                            "priority": normalized["priority"],
                            "estimated_hours": normalized["estimated_hours"],
                            "due_date": normalized["due_date"],
                            "completed_at": normalized["completed_at"],
                            "assigned_to": assigned_to,
                            "tags": normalized["tags"],
                            "synced_at": datetime.now(timezone.utc),
                        },
                    )
                    self.db.execute(stmt)
                    count += 1
            self.db.commit()
            self._update_sync_metadata("tasks", count, "success")
            logger.info("sync_tasks_complete", count=count)
            return count
        except Exception as e:
            self.db.rollback()
            self._update_sync_metadata("tasks", 0, "failed", str(e))
            logger.error("sync_tasks_failed", error=str(e))
            raise

    def sync_timesheets(self, days_back: int = 7) -> int:
        logger.info("sync_timesheets_start", days_back=days_back)
        from datetime import timedelta
        try:
            date_from = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%m-%d-%Y")
            date_to = datetime.now(timezone.utc).strftime("%m-%d-%Y")

            projects = self.db.query(Project).filter(Project.status == "active").all()
            task_map = {t.zoho_task_id: t.id for t in self.db.query(Task).all()}
            user_map = {u.zoho_user_id: u.id for u in self.db.query(User).all()}

            count = 0
            for project in projects:
                entries = self.client.get_timesheets(
                    project.zoho_project_id, date_from=date_from, date_to=date_to
                )
                for ze in entries:
                    normalized = normalize_timesheet(ze)
                    task_id = task_map.get(normalized.pop("zoho_task_id"))
                    user_id = user_map.get(normalized.pop("zoho_user_id"))
                    if not task_id or not user_id or not normalized.get("work_date"):
                        continue

                    stmt = insert(TimesheetEntry).values(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        user_id=user_id,
                        synced_at=datetime.now(timezone.utc),
                        **normalized,
                    ).on_conflict_do_update(
                        index_elements=["zoho_entry_id"],
                        set_={
                            "hours_logged": normalized["hours_logged"],
                            "notes": normalized["notes"],
                            "synced_at": datetime.now(timezone.utc),
                        },
                    )
                    self.db.execute(stmt)
                    count += 1
            self.db.commit()
            self._update_sync_metadata("timesheets", count, "success")
            logger.info("sync_timesheets_complete", count=count)
            return count
        except Exception as e:
            self.db.rollback()
            self._update_sync_metadata("timesheets", 0, "failed", str(e))
            logger.error("sync_timesheets_failed", error=str(e))
            raise

    def sync_milestones(self) -> int:
        logger.info("sync_milestones_start")
        try:
            projects = self.db.query(Project).filter(Project.status == "active").all()
            project_map = {p.zoho_project_id: p.id for p in projects}
            count = 0
            for project in projects:
                zoho_milestones = self.client.get_milestones(project.zoho_project_id)
                for zm in zoho_milestones:
                    normalized = normalize_milestone(zm, project.zoho_project_id)
                    if not normalized["zoho_milestone_id"]:
                        continue
                    internal_project_id = project_map.get(normalized.pop("zoho_project_id"))
                    stmt = insert(Milestone).values(
                        id=uuid.uuid4(),
                        project_id=internal_project_id,
                        synced_at=datetime.now(timezone.utc),
                        **normalized,
                    ).on_conflict_do_update(
                        index_elements=["zoho_milestone_id"],
                        set_={
                            "name": normalized["name"],
                            "due_date": normalized["due_date"],
                            "is_completed": normalized["is_completed"],
                            "completed_at": normalized["completed_at"],
                            "synced_at": datetime.now(timezone.utc),
                        },
                    )
                    self.db.execute(stmt)
                    count += 1
            self.db.commit()
            self._update_sync_metadata("milestones", count, "success")
            logger.info("sync_milestones_complete", count=count)
            return count
        except Exception as e:
            self.db.rollback()
            self._update_sync_metadata("milestones", 0, "failed", str(e))
            logger.error("sync_milestones_failed", error=str(e))
            raise

    def run_full_sync(self):
        logger.info("full_sync_start")
        self.sync_users()
        self.sync_projects(delta=False)
        self.sync_tasks(delta=False)
        self.sync_timesheets(days_back=30)
        self.sync_milestones()
        logger.info("full_sync_complete")

    def run_incremental_sync(self):
        logger.info("incremental_sync_start")
        self.sync_tasks(delta=True)
        self.sync_timesheets(days_back=7)
        logger.info("incremental_sync_complete")
