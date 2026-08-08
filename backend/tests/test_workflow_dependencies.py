from uuid import uuid4

from app.graph.workflow import (
    _all_subtasks_completed,
    _get_ready_subtasks,
)
from app.schemas.execution import (
    Complexity,
    ExecutionPlan,
    Specialist,
    SubTask,
)


def test_independent_subtasks_are_ready():
    task_a = SubTask(
        id=uuid4(),
        description="Research topic",
        assigned_specialist=Specialist.RESEARCH,
        expected_output="Research findings",
        estimated_complexity=Complexity.MEDIUM,
    )

    task_b = SubTask(
        id=uuid4(),
        description="Analyze data",
        assigned_specialist=Specialist.DATA_ANALYSIS,
        expected_output="Analysis",
        estimated_complexity=Complexity.MEDIUM,
    )

    plan = ExecutionPlan(
        task_id=uuid4(),
        subtasks=[
            task_a,
            task_b,
        ],
    )

    ready = _get_ready_subtasks(
        plan,
        set(),
    )

    assert len(ready) == 2


def test_dependent_subtask_waits_for_dependency():
    task_a = SubTask(
        id=uuid4(),
        description="Research topic",
        assigned_specialist=Specialist.RESEARCH,
        expected_output="Research findings",
        estimated_complexity=Complexity.MEDIUM,
    )

    task_b = SubTask(
        id=uuid4(),
        description="Analyze research",
        assigned_specialist=Specialist.DATA_ANALYSIS,
        expected_output="Analysis",
        estimated_complexity=Complexity.MEDIUM,
        dependencies=[task_a.id],
    )

    plan = ExecutionPlan(
        task_id=uuid4(),
        subtasks=[
            task_a,
            task_b,
        ],
    )

    ready = _get_ready_subtasks(
        plan,
        set(),
    )

    assert len(ready) == 1
    assert ready[0].id == task_a.id


def test_dependent_subtask_becomes_ready():
    task_a = SubTask(
        id=uuid4(),
        description="Research topic",
        assigned_specialist=Specialist.RESEARCH,
        expected_output="Research findings",
        estimated_complexity=Complexity.MEDIUM,
    )

    task_b = SubTask(
        id=uuid4(),
        description="Analyze research",
        assigned_specialist=Specialist.DATA_ANALYSIS,
        expected_output="Analysis",
        estimated_complexity=Complexity.MEDIUM,
        dependencies=[task_a.id],
    )

    plan = ExecutionPlan(
        task_id=uuid4(),
        subtasks=[
            task_a,
            task_b,
        ],
    )

    ready = _get_ready_subtasks(
        plan,
        {str(task_a.id)},
    )

    assert len(ready) == 1
    assert ready[0].id == task_b.id


def test_all_subtasks_completed():
    task_a = SubTask(
        id=uuid4(),
        description="Research topic",
        assigned_specialist=Specialist.RESEARCH,
        expected_output="Research findings",
        estimated_complexity=Complexity.LOW,
    )

    task_b = SubTask(
        id=uuid4(),
        description="Write report",
        assigned_specialist=Specialist.WRITING,
        expected_output="Final report",
        estimated_complexity=Complexity.MEDIUM,
        dependencies=[task_a.id],
    )

    plan = ExecutionPlan(
        task_id=uuid4(),
        subtasks=[
            task_a,
            task_b,
        ],
    )

    assert _all_subtasks_completed(
        plan,
        {
            str(task_a.id),
            str(task_b.id),
        },
    )

    assert not _all_subtasks_completed(
        plan,
        {str(task_a.id)},
    )