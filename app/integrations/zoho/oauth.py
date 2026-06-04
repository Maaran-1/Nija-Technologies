from cryptography.fernet import Fernet
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


def _init_fernet() -> Fernet:
    """
    Initialize Fernet cipher from the ENCRYPTION_KEY setting.
    Raises ValueError at startup if the key is missing or malformed.
    A valid key is exactly 44 characters (URL-safe base64 of 32 bytes).
    Generate one with:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    key = settings.ENCRYPTION_KEY
    if not key or len(key.strip()) != 44:
        raise ValueError(
            "ENCRYPTION_KEY is missing or invalid. "
            "It must be a valid 44-character Fernet key. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.strip().encode())
    except Exception as exc:
        raise ValueError(f"ENCRYPTION_KEY is not a valid Fernet key: {exc}") from exc


_fernet = _init_fernet()


def encrypt_token(token: str) -> str:
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()


class ZohoTokenStore:
    """
    In-database encrypted token storage for Zoho OAuth credentials.
    Uses a dedicated OAuthToken record stored in SyncMetadata with entity_type
    prefixed 'oauth_' to isolate from sync state records.

    NOTE: Tokens are stored in the 'last_error' column which is a 500-char
    String column. Encrypted Fernet tokens are ~180-220 chars for short tokens,
    which fits, but this is semantically wrong. A future migration should add a
    dedicated oauth_tokens table with a Text column.
    """

    def __init__(self, db):
        self.db = db

    def _get_setting(self, key: str) -> Optional[str]:
        from app.models.analytics import SyncMetadata
        record = self.db.query(SyncMetadata).filter(
            SyncMetadata.entity_type == f"oauth_{key}"
        ).first()
        return record.last_error if record else None

    def _set_setting(self, key: str, value: str):
        from app.models.analytics import SyncMetadata
        # Validate value fits in column before saving
        if len(value) > 500:
            raise ValueError(
                f"Encrypted token exceeds 500-char column limit for key='{key}'. "
                "Run the migration to add an oauth_tokens table with Text columns."
            )
        record = self.db.query(SyncMetadata).filter(
            SyncMetadata.entity_type == f"oauth_{key}"
        ).first()
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
        try:
            return decrypt_token(encrypted)
        except Exception as exc:
            logger.error("zoho_token_decrypt_failed", key="access_token", error=str(exc))
            return None

    def get_refresh_token(self) -> Optional[str]:
        encrypted = self._get_setting("refresh_token")
        if not encrypted:
            return None
        try:
            return decrypt_token(encrypted)
        except Exception as exc:
            logger.error("zoho_token_decrypt_failed", key="refresh_token", error=str(exc))
            return None

    def is_access_token_valid(self) -> bool:
        expires_at_str = self._get_setting("expires_at")
        if not expires_at_str:
            return False
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            return datetime.now(timezone.utc) < expires_at
        except (ValueError, TypeError):
            return False


class ZohoOAuthManager:
    """Manages Zoho OAuth 2.0 flow: initial authorization, token refresh."""

    def __init__(self, db):
        self.db = db
        self.token_store = ZohoTokenStore(db)

    def get_authorization_url(self) -> str:
        import urllib.parse
        params = {
            "response_type": "code",
            "client_id": settings.ZOHO_CLIENT_ID,
            "scope": (
                "ZohoProjects.portals.READ,ZohoProjects.projects.READ,"
                "ZohoProjects.tasks.READ,ZohoProjects.timesheets.READ,"
                "ZohoProjects.users.READ,ZohoProjects.milestones.READ"
            ),
            "redirect_uri": settings.ZOHO_REDIRECT_URI,
            "access_type": "offline",
        }
        param_str = urllib.parse.urlencode(params)
        return f"{settings.ZOHO_ACCOUNTS_URL}/auth?{param_str}"

    def exchange_code(self, code: str) -> Dict:
        with httpx.Client(timeout=30.0) as client:
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

        with httpx.Client(timeout=30.0) as client:
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
                refresh_token,  # Zoho refresh tokens do not rotate
                data.get("expires_in", 3600),
            )
            logger.info("zoho_token_refreshed")
            return data["access_token"]

    def get_valid_access_token(self) -> str:
        if self.token_store.is_access_token_valid():
            return self.token_store.get_access_token()
        return self.refresh_access_token()
