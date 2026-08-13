from uuid import uuid4

import pytest

from app.db.models.human_decision import HumanDecisionModel
from app.db.repositories.execution import ExecutionRepository
from app.db.repositories.human_decision import (
    HumanDecisionRepository,
)
from app.db.repositories.task import TaskRepository
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_human_decision_can_be_created_and_decided():
    task_id = uuid4()
    execution_id = uuid4()

    async with AsyncSessionLocal() as session:
        task_repo = TaskRepository(session)
        execution_repo = ExecutionRepository(session)
        decision_repo = HumanDecisionRepository(session)

        # -----------------------------------------------------
        # Create task
        # -----------------------------------------------------

        await task_repo.create(
            task_id=task_id,
            user_id="user-hitl-test",
            description="HITL repository test",
        )

        # -----------------------------------------------------
        # Create execution
        # -----------------------------------------------------

        await execution_repo.create(
            task_id=task_id,
            execution_id=execution_id,
            status="escalated",
        )

        await session.flush()

        # -----------------------------------------------------
        # Create pending human decision
        # -----------------------------------------------------

        decision = (
            await decision_repo.create_pending(
                execution_id=execution_id,
            )
        )

        assert decision.execution_id == execution_id
        assert decision.status == "pending"
        assert decision.decision is None

        await session.commit()

    # ---------------------------------------------------------
    # Decide
    # ---------------------------------------------------------

    async with AsyncSessionLocal() as session:
        decision_repo = HumanDecisionRepository(
            session
        )

        updated = await decision_repo.decide(
            decision_id=decision.id,
            decision="approve",
            feedback="Approved by reviewer.",
            decided_by="human-001",
        )

        await session.commit()

        assert updated.status == "decided"
        assert updated.decision == "approve"
        assert (
            updated.feedback
            == "Approved by reviewer."
        )
        assert (
            updated.decided_by
            == "human-001"
        )
        assert updated.decided_at is not None


@pytest.mark.asyncio
async def test_human_decision_rejects_invalid_decision():
    task_id = uuid4()
    execution_id = uuid4()

    async with AsyncSessionLocal() as session:
        task_repo = TaskRepository(session)
        execution_repo = ExecutionRepository(session)
        decision_repo = HumanDecisionRepository(session)

        await task_repo.create(
            task_id=task_id,
            user_id="user-hitl-test",
            description="Invalid decision test",
        )

        await execution_repo.create(
            task_id=task_id,
            execution_id=execution_id,
            status="escalated",
        )

        decision = (
            await decision_repo.create_pending(
                execution_id=execution_id,
            )
        )

        with pytest.raises(ValueError):
            await decision_repo.decide(
                decision_id=decision.id,
                decision="invalid",
                feedback=None,
                decided_by="human-001",
            )
@pytest.mark.asyncio
async def test_decision_cannot_be_decided_twice(
    db_session,
):
    from uuid import uuid4

    from app.db.models.human_decision import (
        HumanDecisionModel,
    )
    from app.db.repositories.human_decision import (
        HumanDecisionRepository,
    )

    task_id = uuid4()
    execution_id = uuid4()

    task_repo = TaskRepository(db_session)
    execution_repo = ExecutionRepository(db_session)

    await task_repo.create(
        task_id=task_id,
        user_id="user-hitl-test",
        description="Decision cannot be decided twice test",
    )

    await execution_repo.create(
        task_id=task_id,
        execution_id=execution_id,
        status="escalated",
    )

    await db_session.flush()

    decision = HumanDecisionModel(
        execution_id=execution_id,
        status="pending",
    )

    db_session.add(decision)
    await db_session.flush()

    repo = HumanDecisionRepository(
        db_session
    )

    await repo.decide(
        decision_id=decision.id,
        decision="approve",
        feedback=None,
        decided_by="human-1",
    )

    with pytest.raises(ValueError):
        await repo.decide(
            decision_id=decision.id,
            decision="reject",
            feedback=None,
            decided_by="human-2",
        )