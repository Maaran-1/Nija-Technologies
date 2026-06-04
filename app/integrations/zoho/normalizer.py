from typing import Dict, Any, Optional
from datetime import date, datetime, timezone
import structlog

logger = structlog.get_logger()


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    logger.warning("date_parse_failed", value=value)
    return None


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (ValueError, TypeError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pass
    return None


def _parse_hours(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def normalize_user(zoho_user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "zoho_user_id": str(zoho_user.get("id", "")),
        "name": zoho_user.get("name", "").strip(),
        "email": zoho_user.get("email", "").strip().lower(),
        "role": zoho_user.get("role", {}).get("name") if isinstance(zoho_user.get("role"), dict) else zoho_user.get("role"),
        "capacity_hours_per_week": 40.0,
        "is_active": zoho_user.get("status", "active").lower() == "active",
    }


def normalize_project(zoho_project: Dict[str, Any]) -> Dict[str, Any]:
    status_map = {
        "active": "active",
        "on_hold": "on_hold",
        "Inactive": "on_hold",
        "completed": "completed",
        "Completed": "completed",
        "cancelled": "cancelled",
    }
    raw_status = zoho_project.get("status", "active")
    return {
        "zoho_project_id": str(zoho_project.get("id", "")),
        "name": zoho_project.get("name", "").strip(),
        "status": status_map.get(raw_status, "active"),
        "start_date": _parse_date(zoho_project.get("start_date")),
        "end_date": _parse_date(zoho_project.get("end_date")),
        "budget_hours": _parse_hours(zoho_project.get("budget_hours")),
        "description": zoho_project.get("description"),
    }


def normalize_task(zoho_task: Dict[str, Any], project_zoho_id: str) -> Dict[str, Any]:
    status_map = {
        "open": "open",
        "Open": "open",
        "inprogress": "in_progress",
        "in_progress": "in_progress",
        "In Progress": "in_progress",
        "closed": "completed",
        "Closed": "completed",
        "completed": "completed",
        "on_hold": "on_hold",
    }
    priority_map = {"high": 1, "High": 1, "medium": 2, "Medium": 2, "low": 3, "Low": 3, "none": 2}

    owners = zoho_task.get("details", {}).get("owners", [])
    assignee_zoho_id = owners[0].get("id") if owners else None

    raw_status = zoho_task.get("status", {})
    if isinstance(raw_status, dict):
        status_str = raw_status.get("name", "open")
    else:
        status_str = raw_status

    tags = zoho_task.get("tasklists", {})
    tag_str = None
    if isinstance(tags, dict):
        tag_str = tags.get("name")

    return {
        "zoho_task_id": str(zoho_task.get("id", "")),
        "zoho_project_id": project_zoho_id,
        "assignee_zoho_id": str(assignee_zoho_id) if assignee_zoho_id else None,
        "title": zoho_task.get("name", "").strip()[:500],
        "status": status_map.get(status_str, "open"),
        "priority": priority_map.get(zoho_task.get("priority", "medium"), 2),
        "estimated_hours": _parse_hours(zoho_task.get("duration")),
        "due_date": _parse_date(zoho_task.get("end_date")),
        "completed_at": _parse_datetime(zoho_task.get("completed_time")),
        "tags": tag_str,
    }


def normalize_timesheet(zoho_entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "zoho_entry_id": str(zoho_entry.get("id", "")),
        "zoho_task_id": str(zoho_entry.get("task_id", "")),
        "zoho_user_id": str(zoho_entry.get("owner_id", "")),
        "work_date": _parse_date(zoho_entry.get("log_date")),
        "hours_logged": _parse_hours(zoho_entry.get("hours")) or 0.5,
        "notes": zoho_entry.get("notes"),
    }


def normalize_milestone(zoho_milestone: Dict[str, Any], project_zoho_id: str) -> Dict[str, Any]:
    return {
        "zoho_milestone_id": str(zoho_milestone.get("id", "")),
        "zoho_project_id": project_zoho_id,
        "name": zoho_milestone.get("name", "").strip()[:255],
        "due_date": _parse_date(zoho_milestone.get("end_date")),
        "is_completed": zoho_milestone.get("flag", "notcompleted") == "completed",
        "completed_at": _parse_datetime(zoho_milestone.get("completed_time")),
    }
