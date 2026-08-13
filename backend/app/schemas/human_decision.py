from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from app.schemas.hitl_review import HITLReviewContext

class HumanDecisionType(str, Enum):
    """
    Supported human-in-the-loop decisions.

    The first three values preserve the existing HITL behavior.
    The remaining values provide granular HITL control.
    """

    APPROVE = "approve"
    REPLAN = "replan"
    REJECT = "reject"

    NOTIFY = "notify"
    APPROVE_ACTION = "approve_action"
    APPROVE_PLAN = "approve_plan"
    TAKE_OVER = "take_over"


class HumanDecisionCreate(BaseModel):
    decision: HumanDecisionType = Field(
        description=(
            "Human decision. Supported values are "
            "approve, replan, reject, notify, "
            "approve_action, approve_plan, and take_over."
        )
    )

    feedback: str | None = Field(
        default=None,
        description=(
            "Optional instructions or feedback supplied "
            "by the human reviewer."
        ),
    )

    decided_by: str | None = Field(
        default=None,
        description=(
            "Identifier of the human reviewer."
        ),
    )


class HumanDecisionResponse(BaseModel):
    id: UUID

    execution_id: UUID

    status: str

    decision: HumanDecisionType | None

    feedback: str | None

    decided_by: str | None

    decided_at: datetime | None

    created_at: datetime

    resume_task_id: str | None = None

    execution_status: str | None = None

    model_config = {
        "from_attributes": True,
    }

    approval_level: str | None

    escalation_trigger: str | None

    proposed_action: str | None

    review_context: HITLReviewContext | None

    


class EscalationResponse(BaseModel):
    execution_id: UUID

    status: str

    escalation_required: bool

    human_escalation_required: bool

    escalation_reason: str | None

    specialist_confidence: float | None

    confidence_threshold: float | None

    human_decision_status: str

    human_decision: HumanDecisionType | None

    human_feedback: str | None

    human_decided_at: datetime | None

    resume_node: str | None

    resume_subtask_id: UUID | None