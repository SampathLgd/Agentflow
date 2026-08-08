from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ToolInvocation(BaseModel):
    """
    Audit record for one tool invocation.
    """

    invocation_id: UUID = Field(
        default_factory=uuid4,
    )

    task_id: UUID

    subtask_id: UUID | None = None

    specialist: str

    tool_name: str

    arguments: dict[str, Any] = Field(
        default_factory=dict,
    )

    success: bool

    result: Any = None

    error: str | None = None

    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    latency_ms: float | None = None