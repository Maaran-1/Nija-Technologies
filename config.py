from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import secrets


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Workforce Optimization Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    # Redis
    REDIS_URL: str = Field(..., env="REDIS_URL")
    CACHE_TTL_SECONDS: int = 300  # 5 minutes default
    RECOMMENDATION_CACHE_TTL: int = 1800  # 30 minutes

    # JWT
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Zoho OAuth
    ZOHO_CLIENT_ID: str = Field(..., env="ZOHO_CLIENT_ID")
    ZOHO_CLIENT_SECRET: str = Field(..., env="ZOHO_CLIENT_SECRET")
    ZOHO_REDIRECT_URI: str = Field(..., env="ZOHO_REDIRECT_URI")
    ZOHO_PORTAL_ID: str = Field(..., env="ZOHO_PORTAL_ID")
    ZOHO_BASE_URL: str = "https://projectsapi.zoho.com/restapi"
    ZOHO_ACCOUNTS_URL: str = "https://accounts.zoho.com/oauth/v2"
    ZOHO_RATE_LIMIT_PER_HOUR: int = 2500

    # Encryption key for Zoho tokens at rest
    ENCRYPTION_KEY: str = Field(..., env="ENCRYPTION_KEY")

    # Analytics
    UTILIZATION_WINDOW_WEEKS: int = 2
    UTILIZATION_UNDERUTILIZED_THRESHOLD: float = 60.0
    UTILIZATION_OPTIMAL_MAX: float = 85.0
    UTILIZATION_OVERLOADED_MAX: float = 110.0

    # Recommendation engine
    MAX_PROJECTED_UTILIZATION: float = 90.0
    MIN_IMPACT_SCORE: float = 5.0
    RECOMMENDATION_BATCH_SIZE: int = 50

    # Celery
    CELERY_BROKER_URL: str = Field(..., env="REDIS_URL")
    CELERY_RESULT_BACKEND: str = Field(..., env="REDIS_URL")

    # Sync schedules (in seconds for Celery beat)
    FULL_SYNC_INTERVAL_SECONDS: int = 3600
    TASK_SYNC_INTERVAL_SECONDS: int = 900
    TIMESHEET_SYNC_INTERVAL_SECONDS: int = 1800

    # API rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:80"]

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
