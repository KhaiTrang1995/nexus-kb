from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseMeta(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))


class ApiResponse(BaseModel, Generic[T]):
    data: T
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[Any] = Field(default_factory=list)


class ApiErrorResponse(BaseModel):
    error: ErrorDetail
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
