from typing import Any, Optional, List, Dict
from pydantic import BaseModel


class Meta(BaseModel):
    page: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None
    total_pages: Optional[int] = None


class ErrorDetail(BaseModel):
    message: str
    code: str
    field: Optional[str] = None


class APIResponse(BaseModel):
    data: Any = None
    meta: Dict[str, Any] = {}
    errors: List[ErrorDetail] = []


def success_response(data: Any, meta: Optional[Dict[str, Any]] = None) -> dict:
    return {
        "data": data,
        "meta": meta or {},
        "errors": [],
    }


def paginated_response(data: Any, page: int, page_size: int, total: int) -> dict:
    total_pages = (total + page_size - 1) // page_size
    return {
        "data": data,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
        "errors": [],
    }
