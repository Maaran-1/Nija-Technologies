from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectOut(BaseModel):
    id: UUID
    zoho_project_id: str
    name: str
    status: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget_hours: Optional[float] = None
    description: Optional[str] = None
    synced_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectWithHealth(ProjectOut):
    latest_health_score: Optional[float] = None
    health_band: Optional[str] = None
    risk_level: Optional[str] = None


# ── Task ──────────────────────────────────────────────────────────────────────

class TaskOut(BaseModel):
    id: UUID
    zoho_task_id: str
    project_id: UUID
    assigned_to: Optional[UUID] = None
    title: str
    status: str
    priority: Optional[int] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    tags: Optional[str] = None
    synced_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TaskAssignRequest(BaseModel):
    user_id: Optional[UUID] = None  # None = unassign


# ── Milestone ─────────────────────────────────────────────────────────────────

class MilestoneOut(BaseModel):
    id: UUID
    zoho_milestone_id: str
    project_id: UUID
    name: str
    due_date: Optional[date] = None
    is_completed: bool
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Timesheet ─────────────────────────────────────────────────────────────────

class TimesheetEntryOut(BaseModel):
    id: UUID
    zoho_entry_id: str
    task_id: UUID
    user_id: UUID
    work_date: date
    hours_logged: float
    notes: Optional[str] = None

    class Config:
        from_attributes = True
