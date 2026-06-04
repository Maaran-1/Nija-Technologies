from fastapi import HTTPException
from typing import Optional


class WOPException(Exception):
    def __init__(self, message: str, status_code: int = 400, error_code: str = "BAD_REQUEST"):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


class NotFoundError(WOPException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} '{identifier}' not found",
            status_code=404,
            error_code="NOT_FOUND",
        )


class UnauthorizedError(WOPException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, status_code=401, error_code="UNAUTHORIZED")


class ForbiddenError(WOPException):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message=message, status_code=403, error_code="FORBIDDEN")


class ConflictError(WOPException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=409, error_code="CONFLICT")


class ZohoAPIError(WOPException):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message=message, status_code=status_code, error_code="ZOHO_API_ERROR")


class SyncError(WOPException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=500, error_code="SYNC_ERROR")


class ValidationError(WOPException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=422, error_code="VALIDATION_ERROR")
