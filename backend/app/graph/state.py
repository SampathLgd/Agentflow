import operator

from typing import Annotated, Any

from typing_extensions import TypedDict

from app.schemas.execution import ExecutionPlan, SubTask
from app.schemas.review import ReviewResult


class AgentGraphState(TypedDict, total=False):
    """
    Shared state for the LangGraph orchestration workflow.
    """

    task_id: str
    user_id: str
    description: str

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

    final_output: str

    error: str