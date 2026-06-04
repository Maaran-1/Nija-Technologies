from cryptography.fernet import Fernet
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

_fernet = Fernet(settings.ENCRYPTION_KEY.encode() if len(settings.ENCRYPTION_KEY) == 44
                 else Fernet.generate_key())


def encrypt_token(token: str) -> str:
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()


class ZohoTokenStore:
    """In-database encrypted token storage for Zoho OAuth credentials."""

    def __init__(self, db):
        self.db = db

    def _get_setting(self, key: str) -> Optional[str]:
        from app.models.analytics import SyncMetadata
        record = self.db.query(SyncMetadata).filter(SyncMetadata.entity_type == f"oauth_{key}").first()
        return record.last_error if record else None  # reuse last_error field as value storage

    def _set_setting(self, key: str, value: str):
        from app.models.analytics import SyncMetadata
        record = self.db.query(SyncMetadata).filter(SyncMetadata.entity_type == f"oauth_{key}").first()
        if not record:
            record = SyncMetadata(entity_type=f"oauth_{key}")
            self.db.add(record)
        record.last_error = value
        record.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def save_tokens(self, access_token: str, refresh_token: str, expires_in: int):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
        self._set_setting("access_token", encrypt_token(access_token))
        self._set_setting("refresh_token", encrypt_token(refresh_token))
        self._set_setting("expires_at", expires_at.isoformat())
        logger.info("zoho_tokens_saved")

    def get_access_token(self) -> Optional[str]:
        encrypted = self._get_setting("access_token")
        if not encrypted:
            return None
        return decrypt_token(encrypted)

    def get_refresh_token(self) -> Optional[str]:
        encrypted = self._get_setting("refresh_token")
        if not encrypted:
            return None
        return decrypt_token(encrypted)

    def is_access_token_valid(self) -> bool:
        expires_at_str = self._get_setting("expires_at")
        if not expires_at_str:
            return False
        expires_at = datetime.fromisoformat(expires_at_str)
        return datetime.now(timezone.utc) < expires_at


class ZohoOAuthManager:
    """Manages Zoho OAuth 2.0 flow: initial authorization, token refresh."""

    def __init__(self, db):
        self.db = db
        self.token_store = ZohoTokenStore(db)

    def get_authorization_url(self) -> str:
        params = {
            "response_type": "code",
            "client_id": settings.ZOHO_CLIENT_ID,
            "scope": "ZohoProjects.portals.READ,ZohoProjects.projects.READ,ZohoProjects.tasks.READ,ZohoProjects.timesheets.READ,ZohoProjects.users.READ,ZohoProjects.milestones.READ",
            "redirect_uri": settings.ZOHO_REDIRECT_URI,
            "access_type": "offline",
        }
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{settings.ZOHO_ACCOUNTS_URL}/auth?{param_str}"

    def exchange_code(self, code: str) -> Dict:
        with httpx.Client() as client:
            response = client.post(
                f"{settings.ZOHO_ACCOUNTS_URL}/token",
                data={
                    "code": code,
                    "client_id": settings.ZOHO_CLIENT_ID,
                    "client_secret": settings.ZOHO_CLIENT_SECRET,
                    "redirect_uri": settings.ZOHO_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            data = response.json()
            self.token_store.save_tokens(
                data["access_token"],
                data["refresh_token"],
                data.get("expires_in", 3600),
            )
            return data

    def refresh_access_token(self) -> str:
        refresh_token = self.token_store.get_refresh_token()
        if not refresh_token:
            raise RuntimeError("No refresh token stored. Re-authorize Zoho OAuth.")

        with httpx.Client() as client:
            response = client.post(
                f"{settings.ZOHO_ACCOUNTS_URL}/token",
                data={
                    "refresh_token": refresh_token,
                    "client_id": settings.ZOHO_CLIENT_ID,
                    "client_secret": settings.ZOHO_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            data = response.json()
            self.token_store.save_tokens(
                data["access_token"],
                refresh_token,  # refresh token does not rotate in Zoho
                data.get("expires_in", 3600),
            )
            logger.info("zoho_token_refreshed")
            return data["access_token"]

    def get_valid_access_token(self) -> str:
        if self.token_store.is_access_token_valid():
            return self.token_store.get_access_token()
        return self.refresh_access_token()
