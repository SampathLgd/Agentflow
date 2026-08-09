from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryErrorRecord(BaseModel):
    """
    Structured error stored in task-scoped working memory.
    """

    message: str
    source: str = "unknown"
    timestamp: datetime = Field(
        default_factory=utc_now
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class WorkingMemorySnapshot(BaseModel):
    """
    Complete task-scoped working-memory snapshot.

    This represents the information shared by agents during
    a single execution.
    """

    task_id: str

    plan: dict[str, Any] | None = None

    subtask_outputs: list[dict[str, Any]] = Field(
        default_factory=list
    )

    intermediate_results: dict[str, Any] = Field(
        default_factory=dict
    )

    errors: list[MemoryErrorRecord] = Field(
        default_factory=list
    )