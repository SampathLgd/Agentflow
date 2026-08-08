from uuid import uuid4

from app.graph.workflow import route_after_specialists
from app.schemas.execution import (
    Complexity,
    ExecutionPlan,
    Specialist,
    SubTask,
)


def create_plan():
    task_id = uuid4()

    subtask = SubTask(
        id=uuid4(),
        description="Research topic",
        assigned_specialist=Specialist.RESEARCH,
        expected_output="Research findings",
        estimated_complexity=Complexity.MEDIUM,
    )

    return ExecutionPlan(
        task_id=task_id,
        subtasks=[subtask],
    )


def test_successful_specialist_continues_to_dispatch():
    plan = create_plan()

    state = {
        "plan": plan,
        "completed_subtasks": [],
        "failure_reason": "",
    }

    assert route_after_specialists(state) == "dispatch"


def test_failed_specialist_retries():
    plan = create_plan()

    state = {
        "plan": plan,
        "completed_subtasks": [],
        "failure_reason": "Tool execution failed",
        "retry_count": 1,
        "max_retries": 2,
    }

    assert route_after_specialists(state) == "retry"


def test_failed_specialist_stops_after_retry_limit():
    plan = create_plan()

    state = {
        "plan": plan,
        "completed_subtasks": [],
        "failure_reason": "Tool execution failed",
        "retry_count": 3,
        "max_retries": 2,
    }

    assert route_after_specialists(state) == "failed"