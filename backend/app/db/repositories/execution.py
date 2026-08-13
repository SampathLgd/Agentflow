from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.execution import ExecutionModel
from app.db.models.human_decision import HumanDecisionModel


class ExecutionRepository:

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        *,
        task_id: UUID,
        execution_id: UUID | None = None,
        status: str = "planned",
    ) -> ExecutionModel:

        execution = ExecutionModel(
            id=execution_id or uuid4(),
            task_id=task_id,
            status=status,
        )

        self.session.add(execution)

        await self.session.flush()

        return execution

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        execution_id: UUID,
    ) -> ExecutionModel | None:

        result = await self.session.execute(
            select(ExecutionModel)
            .options(
                selectinload(
                    ExecutionModel.task
                ),
                selectinload(
                    ExecutionModel.subtasks
                ),
                selectinload(
                    ExecutionModel.reviews
                ),
                selectinload(
                    ExecutionModel.human_decisions
                ),
            )
            .where(
                ExecutionModel.id == execution_id
            )
        )

        return result.scalar_one_or_none()

    # =========================================================
    # UPDATE STATUS
    # =========================================================

    async def update_status(
        self,
        execution_id: UUID,
        status: str,
    ) -> ExecutionModel | None:

        execution = await self.get(
            execution_id
        )

        if execution is None:
            return None

        execution.status = status

        await self.session.flush()

        return execution

    # =========================================================
    # ENSURE PENDING HUMAN DECISION
    # =========================================================

    async def _ensure_pending_human_decision(
        self,
        execution: ExecutionModel,
    ) -> HumanDecisionModel:

        # -----------------------------------------------------
        # Do not create duplicate pending decisions.
        # -----------------------------------------------------

        result = await self.session.execute(
            select(HumanDecisionModel)
            .where(
                HumanDecisionModel.execution_id
                == execution.id
            )
            .where(
                HumanDecisionModel.status
                == "pending"
            )
            .order_by(
                HumanDecisionModel.created_at.desc()
            )
        )

        existing = result.scalars().first()

        if existing is not None:
            return existing

        # -----------------------------------------------------
        # Create a new pending decision.
        #
        # This is intentionally a new decision when a previous
        # decision was already processed and the execution
        # escalates again later.
        # -----------------------------------------------------

        decision = HumanDecisionModel(
            execution_id=execution.id,
            status="pending",
        )

        self.session.add(decision)

        await self.session.flush()

        return decision

    # =========================================================
    # MARK ESCALATED
    # =========================================================

    async def mark_escalated(
        self,
        *,
        execution_id: UUID,
        escalation_required: bool,
        human_escalation_required: bool,
        escalation_reason: str | None,
        specialist_confidence: float | None,
        confidence_threshold: float | None,
        resume_node: str | None,
        resume_subtask_id: UUID | None,
    ) -> ExecutionModel | None:

        execution = await self.get(
            execution_id
        )

        if execution is None:
            return None

        # -----------------------------------------------------
        # Execution state
        # -----------------------------------------------------

        execution.status = "escalated"

        execution.escalation_required = (
            escalation_required
        )

        execution.human_escalation_required = (
            human_escalation_required
        )

        execution.escalation_reason = (
            escalation_reason
        )

        execution.specialist_confidence = (
            specialist_confidence
        )

        execution.confidence_threshold = (
            confidence_threshold
        )

        # -----------------------------------------------------
        # Resume information
        # -----------------------------------------------------

        execution.resume_node = (
            resume_node
        )

        execution.resume_subtask_id = (
            resume_subtask_id
        )

        # -----------------------------------------------------
        # HITL decision
        # -----------------------------------------------------

        if human_escalation_required:

            execution.human_decision_status = (
                "pending"
            )

            await self._ensure_pending_human_decision(
                execution
            )

        else:

            execution.human_decision_status = (
                "none"
            )

        await self.session.flush()

        return execution

    # =========================================================
    # APPLY HUMAN DECISION
    # =========================================================

    async def apply_human_decision(
        self,
        *,
        execution_id: UUID,
        decision: str,
        feedback: str | None,
        decided_at: datetime | None = None,
    ) -> ExecutionModel | None:

        execution = await self.get(
            execution_id
        )

        if execution is None:
            return None

        execution.human_decision_status = (
            "decided"
        )

        execution.human_decision = (
            decision.strip().lower()
        )

        execution.human_feedback = (
            feedback
        )

        execution.human_decided_at = (
            decided_at
            or datetime.now(timezone.utc)
        )

        await self.session.flush()

        return execution

    # =========================================================
    # MARK RESUMING
    # =========================================================

    async def mark_resuming(
        self,
        execution_id: UUID,
    ) -> ExecutionModel | None:

        execution = await self.get(
            execution_id
        )

        if execution is None:
            return None

        execution.status = "resuming"

        await self.session.flush()

        return execution

    # =========================================================
    # CLEAR ESCALATION
    # =========================================================

    async def clear_escalation(
        self,
        execution_id: UUID,
    ) -> ExecutionModel | None:

        execution = await self.get(
            execution_id
        )

        if execution is None:
            return None

        execution.escalation_required = False

        execution.human_escalation_required = False

        await self.session.flush()

        return execution