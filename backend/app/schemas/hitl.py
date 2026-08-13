from enum import Enum

from pydantic import BaseModel, Field


class HITLDecision(str, Enum):
    APPROVE = "approved"
    REJECT = "rejected"
    REPLAN = "replan"


class HITLDecisionRequest(BaseModel):
    decision: HITLDecision
    feedback: str | None = Field(
        default=None,
        max_length=10000,
    )


class HITLDecisionResponse(BaseModel):
    execution_id: str
    status: str
    decision: HITLDecision
    feedback: str | None = None


class HITLExecutionResponse(BaseModel):
    execution_id: str
    task_id: str
    status: str
    escalation_required: bool
    human_escalation_required: bool
    escalation_type: str | None
    escalation_reason: str | None
    specialist_confidence: float | None
    confidence_threshold: float | None
    human_decision: str | None
    human_feedback: str | None