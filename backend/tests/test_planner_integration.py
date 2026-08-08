from uuid import UUID

import pytest

from app.agents.supervisor.planner import TaskPlanner
from app.config import get_settings
from app.llm.router import LLMRouter
from app.schemas.execution import ExecutionPlan


@pytest.mark.asyncio
async def test_real_supervisor_planner() -> None:
    """
    Real LLM integration test.

    This test calls the configured provider and verifies that
    the Supervisor produces a valid structured ExecutionPlan.
    """

    settings = get_settings()

    router = LLMRouter(settings)

    planner = TaskPlanner(router)

    task_id = UUID(
        "11111111-1111-1111-1111-111111111111"
    )

    plan = await planner.create_plan(
        task_id=task_id,
        task_description=(
            "Research the current applications of AI agents "
            "in software engineering, analyze the major use cases, "
            "and prepare a structured summary."
        ),
    )

    assert isinstance(plan, ExecutionPlan)

    assert plan.task_id == task_id

    assert len(plan.subtasks) > 0

    for subtask in plan.subtasks:
        assert subtask.description
        assert subtask.assigned_specialist
        assert subtask.expected_output
        assert subtask.estimated_complexity