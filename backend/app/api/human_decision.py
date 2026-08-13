from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.db.repositories.execution import ExecutionRepository
from app.db.repositories.human_decision import (
    HumanDecisionRepository,
)
from app.db.session import AsyncSessionLocal
from app.schemas.human_decision import (
    EscalationResponse,
    HumanDecisionCreate,
    HumanDecisionResponse,
)
from app.tasks.resume import (
    resume_agentflow_execution,
)


router = APIRouter(
    prefix="/executions",
    tags=["human-in-the-loop"],
)


@router.get(
    "/{execution_id}/escalation",
    response_model=EscalationResponse,
)
async def get_escalation(
    execution_id: UUID,
) -> EscalationResponse:

    async with AsyncSessionLocal() as session:

        execution_repo = ExecutionRepository(
            session
        )

        execution = await execution_repo.get(
            execution_id
        )

        if execution is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution not found.",
            )

        return EscalationResponse(
            execution_id=execution.id,
            status=execution.status,
            escalation_required=(
                execution.escalation_required
            ),
            human_escalation_required=(
                execution.human_escalation_required
            ),
            escalation_reason=(
                execution.escalation_reason
            ),
            specialist_confidence=(
                execution.specialist_confidence
            ),
            confidence_threshold=(
                execution.confidence_threshold
            ),
            human_decision_status=(
                execution.human_decision_status
            ),
            human_decision=(
                execution.human_decision
            ),
            human_feedback=(
                execution.human_feedback
            ),
            human_decided_at=(
                execution.human_decided_at
            ),
            resume_node=(
                execution.resume_node
            ),
            resume_subtask_id=(
                execution.resume_subtask_id
            ),
        )


@router.get(
    "/{execution_id}/human-decision",
    response_model=HumanDecisionResponse,
)
async def get_human_decision(
    execution_id: UUID,
) -> HumanDecisionResponse:

    async with AsyncSessionLocal() as session:

        decision_repo = HumanDecisionRepository(
            session
        )

        decision = (
            await decision_repo
            .get_pending_for_execution(
                execution_id
            )
        )

        if decision is None:
            decision = (
                await decision_repo
                .get_latest_for_execution(
                    execution_id
                )
            )

        if decision is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No human decision exists "
                    "for this execution."
                ),
            )

        return HumanDecisionResponse(
            id=decision.id,
            execution_id=decision.execution_id,
            status=decision.status,
            decision=decision.decision,
            feedback=decision.feedback,
            decided_by=decision.decided_by,
            decided_at=decision.decided_at,
            created_at=decision.created_at,
        )


@router.post(
    "/{execution_id}/human-decision",
    response_model=HumanDecisionResponse,
)
async def decide_human_decision(
    execution_id: UUID,
    payload: HumanDecisionCreate,
) -> HumanDecisionResponse:

    async with AsyncSessionLocal() as session:

        execution_repo = ExecutionRepository(
            session
        )

        execution = await execution_repo.get(
            execution_id
        )

        if execution is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution not found.",
            )

        # -----------------------------------------------------
        # Only escalated executions may receive a decision.
        # -----------------------------------------------------

        if execution.status != "escalated":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Execution is not waiting "
                    "for a human decision."
                ),
            )

        decision_repo = HumanDecisionRepository(
            session
        )

        decision = (
            await decision_repo
            .get_pending_for_execution(
                execution_id
            )
        )

        if decision is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Pending human decision not found."
                ),
            )

        # -----------------------------------------------------
        # Persist decision.
        # -----------------------------------------------------

        try:

            decision_value = payload.decision.value

            decision = await decision_repo.decide(
                decision_id=decision.id,
                decision=decision_value,
                feedback=payload.feedback,
                decided_by=payload.decided_by,
            )

            execution = (
                await execution_repo
                .apply_human_decision(
                    execution_id=execution_id,
                    decision=decision_value,
                    feedback=payload.feedback,
                )
            )

            if execution is None:
                raise ValueError(
                    "Execution disappeared while "
                    "saving the human decision."
                )

            await execution_repo.mark_resuming(
                execution_id
            )

            await session.commit()

        except ValueError as exc:

            await session.rollback()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        # -----------------------------------------------------
        # Queue resume.
        # -----------------------------------------------------

        try:

            celery_result = (
                resume_agentflow_execution.delay(
                    execution_id=str(
                        execution_id
                    ),
                    decision_id=str(
                        decision.id
                    ),
                )
            )

        except Exception:

            async with AsyncSessionLocal() as recovery_session:

                recovery_repo = ExecutionRepository(
                    recovery_session
                )

                await recovery_repo.update_status(
                    execution_id,
                    "escalated",
                )

                await recovery_session.commit()

            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail=(
                    "Human decision was saved, but "
                    "the resume task could not be queued."
                ),
            )

        return HumanDecisionResponse(
            id=decision.id,
            execution_id=decision.execution_id,
            status=decision.status,
            decision=decision.decision,
            feedback=decision.feedback,
            decided_by=decision.decided_by,
            decided_at=decision.decided_at,
            created_at=decision.created_at,
            resume_task_id=celery_result.id,
        )