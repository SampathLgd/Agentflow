import operator

from typing import Annotated, Any

from typing_extensions import TypedDict

from app.schemas.execution import ExecutionPlan, SubTask
from app.schemas.review import ReviewResult


class AgentGraphState(TypedDict, total=False):
    """
    Shared state for the LangGraph orchestration workflow.

    Infrastructure dependencies such as Redis working memory are
    intentionally NOT stored in graph state. They are injected into
    the compiled workflow and accessed by node closures.
    """

    task_id: str
    user_id: str
    description: str

    # Relevant long-term memories retrieved for this task.
    long_term_memories: list[dict[str, Any]]

    plan: ExecutionPlan

    ready_subtasks: list[SubTask]

    current_subtask: SubTask

    completed_subtasks: Annotated[
        list[str],
        operator.add,
    ]

    specialist_outputs: Annotated[
        list[dict[str, Any]],
        operator.add,
    ]

    # Structured reviewer decision.
    review: ReviewResult

    # Feedback from reviewer rejection.
    review_feedback: str

    # Number of reviewer-driven retries.
    review_retry_count: int

    # Maximum reviewer rejection retries.
    max_review_retries: int

    # Specialist failure/retry state.
    retry_count: int
    max_retries: int
    failure_reason: str
    retry_feedback: str

    # Specialist confidence.
    specialist_confidence: float

    # Confidence threshold used for escalation.
    confidence_threshold: float

    # Specialist confidence escalation.
    human_escalation_required: bool
    escalation_reason: str

    # Reviewer confidence escalation.
    escalation_required: bool
    replan_required: bool

    final_output: str

    error: str