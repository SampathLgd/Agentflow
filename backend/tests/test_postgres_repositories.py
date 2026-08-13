from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.db.models import (
    ExecutionModel,
    ReviewModel,
    SubTaskModel,
    TaskModel,
)
from app.db.repositories import (
    ExecutionRepository,
    ReviewRepository,
    SubTaskRepository,
    TaskRepository,
)
from app.db.session import AsyncSessionLocal
from app.schemas.execution import (
    Complexity,
    Specialist,
    SubTask,
)
from app.schemas.review import ReviewResult


@pytest.mark.asyncio
async def test_postgres_repositories_persist_complete_execution():
    task_id = uuid4()
    execution_id = uuid4()

    subtask_a_id = uuid4()
    subtask_b_id = uuid4()

    async with AsyncSessionLocal() as session:
        task_repo = TaskRepository(session)
        execution_repo = ExecutionRepository(session)
        subtask_repo = SubTaskRepository(session)
        review_repo = ReviewRepository(session)

        # -------------------------------------------------
        # 1. Create task
        # -------------------------------------------------

        task = await task_repo.create(
            task_id=task_id,
            user_id="postgres-test-user",
            description="Repository integration test",
        )

        assert task.id == task_id

        # -------------------------------------------------
        # 2. Create execution
        # -------------------------------------------------

        execution = await execution_repo.create(
            task_id=task_id,
            execution_id=execution_id,
            status="planned",
        )

        assert execution.id == execution_id
        assert execution.task_id == task_id

        # -------------------------------------------------
        # 3. Create subtasks
        # -------------------------------------------------

        subtask_a = SubTask(
            id=subtask_a_id,
            description="Research the topic",
            assigned_specialist=Specialist.RESEARCH,
            required_inputs=[],
            expected_output="Research findings",
            estimated_complexity=Complexity.MEDIUM,
        )

        subtask_b = SubTask(
            id=subtask_b_id,
            description="Analyze the findings",
            assigned_specialist=Specialist.DATA_ANALYSIS,
            required_inputs=["research findings"],
            expected_output="Analysis",
            estimated_complexity=Complexity.MEDIUM,
            dependencies=[subtask_a_id],
        )

        subtasks = await subtask_repo.create_many(
            execution_id=execution_id,
            subtasks=[
                subtask_a,
                subtask_b,
            ],
        )

        assert len(subtasks) == 2

        # -------------------------------------------------
        # 4. Create review
        # -------------------------------------------------

        review = ReviewResult(
            approved=True,
            quality_score=0.95,
            confidence=0.92,
            feedback="Good result.",
            issues=[],
        )

        review_model = await review_repo.create(
            execution_id=execution_id,
            review=review,
        )

        assert review_model.approved is True
        assert review_model.quality_score == 0.95
        assert review_model.confidence == 0.92

        # -------------------------------------------------
        # 5. Mark execution completed
        # -------------------------------------------------

        updated_execution = (
            await execution_repo.update_status(
                execution_id,
                "completed",
            )
        )

        assert updated_execution is not None
        assert updated_execution.status == "completed"

        await session.commit()

    # -----------------------------------------------------
    # 6. Read everything back from PostgreSQL
    # -----------------------------------------------------

    async with AsyncSessionLocal() as session:
        task_repo = TaskRepository(session)
        execution_repo = ExecutionRepository(session)
        review_repo = ReviewRepository(session)
        subtask_repo = SubTaskRepository(session)

        stored_task = await task_repo.get(
            task_id
        )

        assert stored_task is not None
        assert stored_task.user_id == (
            "postgres-test-user"
        )

        stored_execution = (
            await execution_repo.get(
                execution_id
            )
        )

        assert stored_execution is not None
        assert (
            stored_execution.status
            == "completed"
        )

        assert len(
            stored_execution.subtasks
        ) == 2

        assert len(
            stored_execution.reviews
        ) == 1

        stored_subtask_b = (
            await subtask_repo.get(
                subtask_b_id
            )
        )

        assert stored_subtask_b is not None

        assert (
            len(
                stored_subtask_b.dependencies
            )
            == 1
        )

        assert (
            stored_subtask_b.dependencies[0].id
            == subtask_a_id
        )

        reviews = (
            await review_repo.get_for_execution(
                execution_id
            )
        )

        assert len(reviews) == 1
        assert reviews[0].approved is True

        # -------------------------------------------------
        # 7. Cleanup
        # -------------------------------------------------

        await session.execute(
            delete(ReviewModel).where(
                ReviewModel.execution_id
                == execution_id
            )
        )

        await session.execute(
            delete(SubTaskModel).where(
                SubTaskModel.execution_id
                == execution_id
            )
        )

        await session.execute(
            delete(ExecutionModel).where(
                ExecutionModel.id
                == execution_id
            )
        )

        await session.execute(
            delete(TaskModel).where(
                TaskModel.id == task_id
            )
        )

        await session.commit()