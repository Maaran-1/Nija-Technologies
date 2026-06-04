import httpx
import time
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog

from app.config import settings
from app.core.exceptions import ZohoAPIError

logger = structlog.get_logger()

# Simple in-memory rate limiter (per process)
_request_timestamps: List[float] = []
_RATE_WINDOW = 3600  # 1 hour in seconds


def _check_rate_limit():
    now = time.time()
    cutoff = now - _RATE_WINDOW
    # Prune old timestamps
    while _request_timestamps and _request_timestamps[0] < cutoff:
        _request_timestamps.pop(0)
    if len(_request_timestamps) >= settings.ZOHO_RATE_LIMIT_PER_HOUR:
        sleep_for = _request_timestamps[0] - cutoff
        logger.warning("zoho_rate_limit_sleep", sleep_seconds=sleep_for)
        time.sleep(sleep_for)
    _request_timestamps.append(now)


class ZohoAPIClient:
    """Thin HTTP wrapper for Zoho Projects REST API v3."""

    def __init__(self, oauth_manager):
        self.oauth_manager = oauth_manager
        self.base_url = settings.ZOHO_BASE_URL
        self.portal_id = settings.ZOHO_PORTAL_ID

    def _get_headers(self) -> Dict[str, str]:
        token = self.oauth_manager.get_valid_access_token()
        return {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True,
    )
    def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        _check_rate_limit()
        url = f"{self.base_url}/portal/{self.portal_id}/{path}"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=self._get_headers(), params=params or {})
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning("zoho_rate_limited", retry_after=retry_after)
                    time.sleep(retry_after)
                    raise httpx.HTTPStatusError("Rate limited", request=response.request, response=response)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            raise ZohoAPIError(f"Zoho API error {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            raise ZohoAPIError(f"Zoho API request failed: {str(e)}")

    def get_users(self) -> List[Dict]:
        """Fetch all users in the portal."""
        data = self._get("users/")
        return data.get("users", [])

    def get_projects(self, updated_time: Optional[str] = None) -> List[Dict]:
        """Fetch all projects, optionally filtered by updated_time for delta sync."""
        params = {"status": "all"}
        if updated_time:
            params["updated_time"] = updated_time
        data = self._get("projects/", params=params)
        return data.get("projects", [])

    def get_tasks(self, project_id: str, updated_time: Optional[str] = None) -> List[Dict]:
        """Fetch all tasks for a project."""
        params = {}
        if updated_time:
            params["updated_time"] = updated_time
        data = self._get(f"projects/{project_id}/tasks/", params=params)
        return data.get("tasks", [])

    def get_timesheets(self, project_id: str, users: Optional[str] = None,
                       date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict]:
        """Fetch timesheet entries for a project."""
        params = {}
        if users:
            params["users_list"] = users
        if date_from:
            params["date"] = date_from
        if date_to:
            params["date_end"] = date_to
        data = self._get(f"projects/{project_id}/logs/", params=params)
        return data.get("timelogs", {}).get("timelog", [])

    def get_milestones(self, project_id: str) -> List[Dict]:
        """Fetch milestones for a project."""
        data = self._get(f"projects/{project_id}/milestones/")
        return data.get("milestones", [])

    def update_task_owner(self, project_id: str, task_id: str, user_id: str) -> Dict:
        """Write back task assignment to Zoho (Phase 2 feature, basic implementation)."""
        _check_rate_limit()
        url = f"{self.base_url}/portal/{self.portal_id}/projects/{project_id}/tasks/{task_id}/"
        payload = {"owner": user_id}
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            raise ZohoAPIError(f"Task update failed: {e.response.status_code}: {e.response.text[:200]}")
