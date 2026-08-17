from __future__ import annotations

import operator
from typing import Annotated, Any

from typing_extensions import TypedDict

from app.schemas.execution import ExecutionPlan, SubTask
from app.schemas.review import ReviewResult


class AgentGraphState(TypedDict, total=False):
    task_id: str
    execution_id: str
    user_id: str
    description: str
    context: dict[str, Any]
    # ---------------------------------------------------------
    # Replay
    # ---------------------------------------------------------

    replay_source_execution_id: str | None

    replay_source_span_id: str | None

    replay_target_subtask_id: str | None

    # Stable logical selector for replay. The original subtask UUID is
    # execution-specific and normally changes when the replay is planned.
    replay_target_subtask_description: str | None
    replay_target_specialist: str | None
    replay_target_span_name: str | None
    replay_target_span_kind: str | None
    replay_source_subtask: SubTask | None

    # When true, replay dispatches only the selected logical subtask and
    # terminates after that specialist finishes.
    replay_only: bool

    replay_input_override: Any

    # Memory
    long_term_memories: list[dict[str, Any]]

    # Planning
    plan: ExecutionPlan
    ready_subtasks: list[SubTask]
    current_subtask: SubTask

    # Specialist execution
    completed_subtasks: Annotated[
        list[str],
        operator.add,
    ]

    specialist_outputs: Annotated[
        list[dict[str, Any]],
        operator.add,
    ]

    # Reviewer
    review: ReviewResult
    review_feedback: str

    review_retry_count: int
    max_review_retries: int

    # Specialist retry
    retry_count: int
    max_retries: int

    failure_reason: str
    retry_feedback: str

    # Confidence
    specialist_confidence: float
    confidence_threshold: float

    # Escalation
    human_escalation_required: bool
    escalation_required: bool
    escalation_reason: str
    replan_required: bool

    # HITL
    resume_node: str
    resume_subtask_id: str | None

    human_decision_status: str
    human_decision: str | None
    human_feedback: str | None

    # HITL approval policy


    approval_level: str
    escalation_trigger: str
    proposed_action: str

    # Resume control
    resume_from_human: bool

    # Final result
    final_output: str
    error: str
    execution_status: str


class SpecialistBranchState(TypedDict, total=False):
    task_id: str
    user_id: str
    description: str
    context: dict[str, Any]

    replay_source_execution_id: str | None

    replay_source_span_id: str | None

    replay_target_subtask_id: str | None

    replay_target_subtask_description: str | None
    replay_target_specialist: str | None
    replay_target_span_name: str | None
    replay_target_span_kind: str | None
    replay_source_subtask: SubTask | None
    
    replay_only: bool

    replay_input_override: Any

    plan: ExecutionPlan
    current_subtask: SubTask

    specialist_outputs: list[dict[str, Any]]
    long_term_memories: list[dict[str, Any]]

    retry_count: int
    max_retries: int

    failure_reason: str
    retry_feedback: str
    review_feedback: str

    confidence_threshold: float