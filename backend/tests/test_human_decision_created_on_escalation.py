from uuid import uuid4

import pytest

from app.db.repositories.execution import (
    ExecutionRepository,
)
from app.db.repositories.human_decision import (
    HumanDecisionRepository,
)
from app.db.repositories.task import (
    TaskRepository,
)
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_escalation_creates_pending_human_decision():

    task_id = uuid4()
    execution_id = uuid4()

    async with AsyncSessionLocal() as session:

        task_repo = TaskRepository(
            session
        )

        execution_repo = ExecutionRepository(
            session
        )

        decision_repo = HumanDecisionRepository(
            session
        )

        # -----------------------------------------------------
        # Create task
        # -----------------------------------------------------

        await task_repo.create(
            task_id=task_id,
            user_id="hitl-escalation-test",
            description="Automatic HITL decision creation",
        )

        # -----------------------------------------------------
        # Create execution
        # -----------------------------------------------------

        await execution_repo.create(
            task_id=task_id,
            execution_id=execution_id,
            status="running",
        )

        # -----------------------------------------------------
        # Escalate
        # -----------------------------------------------------

        execution = (
            await execution_repo.mark_escalated(
                execution_id=execution_id,
                escalation_required=True,
                human_escalation_required=True,
                escalation_reason=(
                    "Low specialist confidence."
                ),
                specialist_confidence=0.25,
                confidence_threshold=0.50,
                resume_node="post_specialist",
                resume_subtask_id=None,
            )
        )

        assert execution is not None

        assert execution.status == "escalated"

        assert (
            execution.human_decision_status
            == "pending"
        )

        # -----------------------------------------------------
        # Verify decision row exists
        # -----------------------------------------------------

        decision = (
            await decision_repo
            .get_pending_for_execution(
                execution_id
            )
        )

        assert decision is not None

        assert (
            decision.execution_id
            == execution_id
        )

        assert decision.status == "pending"

        assert decision.decision is None

        await session.commit()


@pytest.mark.asyncio
async def test_repeated_escalation_does_not_create_duplicate_pending_decisions():

    task_id = uuid4()
    execution_id = uuid4()

    async with AsyncSessionLocal() as session:

        task_repo = TaskRepository(
            session
        )

        execution_repo = ExecutionRepository(
            session
        )

        decision_repo = HumanDecisionRepository(
            session
        )

        await task_repo.create(
            task_id=task_id,
            user_id="hitl-duplicate-test",
            description="Duplicate escalation test",
        )

        await execution_repo.create(
            task_id=task_id,
            execution_id=execution_id,
            status="running",
        )

        # First escalation

        await execution_repo.mark_escalated(
            execution_id=execution_id,
            escalation_required=True,
            human_escalation_required=True,
            escalation_reason="First escalation",
            specialist_confidence=0.20,
            confidence_threshold=0.50,
            resume_node="post_specialist",
            resume_subtask_id=None,
        )

        # Second escalation

        await execution_repo.mark_escalated(
            execution_id=execution_id,
            escalation_required=True,
            human_escalation_required=True,
            escalation_reason="Second escalation",
            specialist_confidence=0.25,
            confidence_threshold=0.50,
            resume_node="post_review",
            resume_subtask_id=None,
        )

        pending = (
            await decision_repo
            .get_pending_for_execution(
                execution_id
            )
        )

        assert pending is not None

        # -----------------------------------------------------
        # Verify only one pending decision exists.
        # -----------------------------------------------------

        from sqlalchemy import select

        from app.db.models.human_decision import (
            HumanDecisionModel,
        )

        result = await session.execute(
            select(HumanDecisionModel)
            .where(
                HumanDecisionModel.execution_id
                == execution_id
            )
            .where(
                HumanDecisionModel.status
                == "pending"
            )
        )

        pending_decisions = (
            result.scalars().all()
        )

        assert len(
            pending_decisions
        ) == 1

        await session.commit()