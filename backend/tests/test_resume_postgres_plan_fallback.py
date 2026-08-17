from uuid import uuid4

import pytest

from app.db.repositories.execution import (
    ExecutionRepository,
)
from app.db.repositories.subtask import (
    SubTaskRepository,
)
from app.db.repositories.task import (
    TaskRepository,
)
from app.db.session import AsyncSessionLocal
from app.schemas.execution import (
    Complexity,
    Specialist,
    SubTask,
)


@pytest.mark.asyncio
async def test_subtask_repository_reconstructs_execution_plan():

    task_id = uuid4()
    execution_id = uuid4()
    subtask_id = uuid4()

    subtask = SubTask(
        id=subtask_id,
        description="Execute verification code.",
        assigned_specialist=Specialist.CODE_EXECUTION,
        required_inputs=[
            "supplied Python verification code"
        ],
        expected_output=(
            "Execution stdout and return code."
        ),
        estimated_complexity=Complexity.LOW,
        dependencies=[],
    )

    async with AsyncSessionLocal() as session:

        task_repo = TaskRepository(session)
        execution_repo = ExecutionRepository(session)
        subtask_repo = SubTaskRepository(session)

        # -----------------------------------------------------
        # Parent task must exist first.
        # -----------------------------------------------------

        await task_repo.create(
            task_id=task_id,
            user_id="resume-fallback-test",
            description=(
                "PostgreSQL plan reconstruction test"
            ),
        )

        # -----------------------------------------------------
        # Parent execution must exist before subtasks.
        # -----------------------------------------------------

        await execution_repo.create(
            task_id=task_id,
            execution_id=execution_id,
            status="running",
        )

        # -----------------------------------------------------
        # Persist the subtask.
        # -----------------------------------------------------

        await subtask_repo.create(
            execution_id=execution_id,
            subtask=subtask,
        )

        await session.commit()

    # ---------------------------------------------------------
    # New session simulates a later resume operation.
    # ---------------------------------------------------------

    async with AsyncSessionLocal() as session:

        subtask_repo = SubTaskRepository(session)

        plan = await subtask_repo.get_execution_plan(
            execution_id=execution_id,
            task_id=task_id,
        )

        assert plan is not None

        assert plan.task_id == task_id

        assert len(plan.subtasks) == 1

        restored = plan.subtasks[0]

        assert restored.id == subtask_id

        assert (
            restored.assigned_specialist
            == Specialist.CODE_EXECUTION
        )

        assert (
            restored.description
            == "Execute verification code."
        )

        assert (
            restored.required_inputs
            == [
                "supplied Python verification code"
            ]
        )

        assert (
            restored.expected_output
            == "Execution stdout and return code."
        )

        assert (
            restored.estimated_complexity
            == Complexity.LOW
        )

        assert restored.dependencies == []