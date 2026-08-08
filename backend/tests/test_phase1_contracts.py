from uuid import uuid4

import pytest

from app.schemas.execution import (
    Complexity,
    ExecutionPlan,
    Specialist,
    SubTask,
)
from app.tools.registry import ToolRegistry


def test_execution_plan_contract() -> None:
    first_id = uuid4()

    subtask = SubTask(
        id=first_id,
        description="Research the topic",
        assigned_specialist=Specialist.RESEARCH,
        required_inputs=["user question"],
        expected_output="Structured research findings",
        estimated_complexity=Complexity.MEDIUM,
    )

    plan = ExecutionPlan(
        task_id=uuid4(),
        subtasks=[subtask],
    )

    assert len(plan.subtasks) == 1
    assert (
        plan.subtasks[0].assigned_specialist
        == Specialist.RESEARCH
    )


def test_execution_plan_rejects_unknown_dependency() -> None:
    subtask = SubTask(
        id=uuid4(),
        description="Analyze research",
        assigned_specialist=Specialist.DATA_ANALYSIS,
        expected_output="Analysis",
        estimated_complexity=Complexity.MEDIUM,
        dependencies=[uuid4()],
    )

    with pytest.raises(ValueError):
        ExecutionPlan(
            task_id=uuid4(),
            subtasks=[subtask],
        )


def test_execution_plan_rejects_self_dependency() -> None:
    subtask_id = uuid4()

    with pytest.raises(ValueError):
        SubTask(
            id=subtask_id,
            description="Invalid task",
            assigned_specialist=Specialist.RESEARCH,
            expected_output="Result",
            estimated_complexity=Complexity.LOW,
            dependencies=[subtask_id],
        )


def test_tool_registry_register_and_lookup() -> None:
    class FakeTool:
        name = "fake"
        description = "Fake tool"
        allowed_specialists = [
            Specialist.RESEARCH.value,
        ]

    registry = ToolRegistry()

    registry.register(FakeTool())

    assert registry.get("fake").name == "fake"

    assert registry.has_access(
        "fake",
        Specialist.RESEARCH,
    )

    assert not registry.has_access(
        "fake",
        Specialist.WRITING,
    )

    assert registry.list() == ["fake"]