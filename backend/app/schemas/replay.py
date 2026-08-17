from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReplayExecutionRequest(BaseModel):
    source_execution_id: UUID
    source_span_id: str | None = None
    input_override: Any = None
    description_override: str | None = None


class ReplayExecutionResponse(BaseModel):
    source_execution_id: UUID
    source_trace_id: str
    replay_task_id: UUID
    replay_execution_id: UUID
    source_span_id: str | None = None
    applied_subtask_id: UUID | None = None
    status: str
    celery_task_id: str | None = None


class ReplayComparisonResponse(BaseModel):
    original_execution_id: UUID
    replay_execution_id: UUID
    original: dict[str, Any]
    replay: dict[str, Any]
    changes: dict[str, Any]
    span_differences: list[dict[str, Any]] = Field(default_factory=list)
