from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HITLReviewContext(BaseModel):
    """
    Complete context presented to a human reviewer.
    """

    original_task: str

    plan: dict | None = None

    completed_steps: list[dict] = Field(
        default_factory=list
    )

    current_step: dict | None = None

    proposed_action: str

    reasoning: str | None = None

    relevant_memories: list[dict] = Field(
        default_factory=list
    )

    past_decisions: list[dict] = Field(
        default_factory=list
    )


class HITLReviewResponse(BaseModel):
    """
    Review queue item presented to the human operator.
    """

    decision_id: UUID

    execution_id: UUID

    status: str

    approval_level: str | None

    escalation_trigger: str | None

    escalation_reason: str | None

    context: HITLReviewContext

    created_at: datetime