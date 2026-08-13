from uuid import uuid4

import pytest

from app.db.repositories.execution import (
    ExecutionRepository,
)
from app.db.repositories.task import (
    TaskRepository,
)
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_execution_persists_escalation_metadata():
    task_id = uuid4()
    execution_id = uuid4()
    subtask_id = uuid4()

    async with AsyncSessionLocal() as session:
        task_repo = TaskRepository(session)
        execution_repo = ExecutionRepository(session)

        await task_repo.create(
            task_id=task_id,
            user_id="user-escalation-test",
            description="Escalation persistence test",
        )

        await execution_repo.create(
            task_id=task_id,
            execution_id=execution_id,
            status="running",
        )

        execution = (
            await execution_repo.mark_escalated(
                execution_id=execution_id,
                escalation_required=False,
                human_escalation_required=True,
                escalation_reason=(
                    "Specialist confidence "
                    "0.30 is below the "
                    "configured threshold 0.50."
                ),
                specialist_confidence=0.30,
                confidence_threshold=0.50,
                resume_node="specialist",
                resume_subtask_id=subtask_id,
            )
        )

        await session.commit()

        assert execution is not None
        assert execution.status == "escalated"

        assert (
            execution.escalation_required
            is False
        )

        assert (
            execution.human_escalation_required
            is True
        )

        assert (
            execution.specialist_confidence
            == 0.30
        )

        assert (
            execution.confidence_threshold
            == 0.50
        )

        assert (
            execution.resume_node
            == "specialist"
        )

        assert (
            execution.resume_subtask_id
            == subtask_id
        )

        assert (
            execution.human_decision_status
            == "pending"
        )