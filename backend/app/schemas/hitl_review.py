from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HITLReviewContext(BaseModel):
    original_task: str

    plan: dict[str, Any] | None = None

    completed_steps: list[dict[str, Any]] = Field(
        default_factory=list
    )

    current_step: dict[str, Any] | None = None

    proposed_action: str

    reasoning: str | None = None

    relevant_memories: list[Any] = Field(
        default_factory=list
    )

    past_decisions: list[dict[str, Any]] = Field(
        default_factory=list
    )


class HITLReviewResponse(BaseModel):
    decision_id: UUID
    execution_id: UUID

    status: str

    approval_level: str | None = None

    escalation_trigger: str | None = None

    escalation_reason: str | None = None

    context: HITLReviewContext

    created_at: datetime

    model_config = {
        "from_attributes": True,
    }

class HITLReviewQueueItem(BaseModel):
    decision_id: UUID
    execution_id: UUID

    status: str

    approval_level: str | None = None

    escalation_trigger: str | None = None

    escalation_reason: str | None = None

    proposed_action: str | None = None

    original_task: str | None = None

    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class HITLReviewQueueResponse(BaseModel):
    items: list[HITLReviewQueueItem]

    total: int