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
from app.schemas.hitl_review import (
    HITLReviewContext,
    HITLReviewResponse,
)
from app.tasks.resume import (
    resume_agentflow_execution,
)

from app.schemas.hitl_review import (
    HITLReviewContext,
    HITLReviewResponse,
    HITLReviewQueueItem,
    HITLReviewQueueResponse,
)


router = APIRouter(
    prefix="/api/executions",
    tags=["HITL"],
)


# ============================================================
# GET ESCALATION / HITL STATE
# ============================================================


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

        decision_repo = (
            HumanDecisionRepository(
                session
            )
        )

        execution = await execution_repo.get(
            execution_id
        )

        if execution is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="Execution not found.",
            )

        decision = (
            await decision_repo
            .get_latest_for_execution(
                execution.id
            )
        )

        human_decision_status = (
            execution.human_decision_status
            or "none"
        )

        human_decision = (
            execution.human_decision
        )

        human_feedback = (
            execution.human_feedback
        )

        human_decided_at = (
            execution.human_decided_at
        )

        if decision is not None:

            human_decision_status = (
                decision.status
            )

            human_decision = (
                decision.decision
            )

            human_feedback = (
                decision.feedback
            )

            human_decided_at = (
                decision.decided_at
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
                human_decision_status
            ),

            human_decision=(
                human_decision
            ),

            human_feedback=(
                human_feedback
            ),

            human_decided_at=(
                human_decided_at
            ),

            resume_node=(
                execution.resume_node
            ),

            resume_subtask_id=(
                execution.resume_subtask_id
            ),
        )
# ============================================================
# GET HITL REVIEW QUEUE
# ============================================================


@router.get(
    "/reviews/queue",
    response_model=HITLReviewQueueResponse,
)
async def get_review_queue(
    limit: int = 50,
) -> HITLReviewQueueResponse:

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100.",
        )

    async with AsyncSessionLocal() as session:

        decision_repo = HumanDecisionRepository(
            session
        )

        decisions = (
            await decision_repo.list_pending(
                limit=limit
            )
        )

        items: list[
            HITLReviewQueueItem
        ] = []

        for decision in decisions:

            review_context = (
                decision.review_context
            )

            original_task = None

            if isinstance(
                review_context,
                dict,
            ):
                original_task = (
                    review_context.get(
                        "original_task"
                    )
                )

            execution_repo = ExecutionRepository(
                session
            )

            execution = (
                await execution_repo.get(
                    decision.execution_id
                )
            )

            escalation_reason = None

            if execution is not None:
                escalation_reason = (
                    execution.escalation_reason
                )

            items.append(
                HITLReviewQueueItem(
                    decision_id=decision.id,

                    execution_id=(
                        decision.execution_id
                    ),

                    status=decision.status,

                    approval_level=(
                        decision.approval_level
                    ),

                    escalation_trigger=(
                        decision.escalation_trigger
                    ),

                    escalation_reason=(
                        escalation_reason
                    ),

                    proposed_action=(
                        decision.proposed_action
                    ),

                    original_task=(
                        original_task
                    ),

                    created_at=(
                        decision.created_at
                    ),
                )
            )

        return HITLReviewQueueResponse(
            items=items,
            total=len(items),
        )

# ============================================================
# GET FULL HITL REVIEW PACKET
# ============================================================


@router.get(
    "/{execution_id}/review",
    response_model=HITLReviewResponse,
)
async def get_review(
    execution_id: UUID,
) -> HITLReviewResponse:

    async with AsyncSessionLocal() as session:

        execution_repo = (
            ExecutionRepository(session)
        )

        decision_repo = (
            HumanDecisionRepository(session)
        )

        execution = await execution_repo.get(
            execution_id
        )

        if execution is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="Execution not found.",
            )

        decision = (
            await decision_repo
            .get_pending_for_execution(
                execution_id
            )
        )

        if decision is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    "No pending human review exists "
                    "for this execution."
                ),
            )

        if decision.review_context is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Human review context is unavailable."
                ),
            )

        return HITLReviewResponse(
            decision_id=decision.id,

            execution_id=(
                decision.execution_id
            ),

            status=decision.status,

            approval_level=(
                decision.approval_level
            ),

            escalation_trigger=(
                decision.escalation_trigger
            ),

            escalation_reason=(
                execution.escalation_reason
            ),

            context=(
                HITLReviewContext.model_validate(
                    decision.review_context
                )
            ),

            created_at=decision.created_at,
        )


# ============================================================
# GET HUMAN DECISION
# ============================================================


@router.get(
    "/{execution_id}/human-decision",
    response_model=HumanDecisionResponse,
)
async def get_human_decision(
    execution_id: UUID,
) -> HumanDecisionResponse:

    async with AsyncSessionLocal() as session:

        execution_repo = (
            ExecutionRepository(session)
        )

        decision_repo = (
            HumanDecisionRepository(session)
        )

        execution = await execution_repo.get(
            execution_id
        )

        if execution is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="Execution not found.",
            )

        # ----------------------------------------------------
        # Prefer a currently pending decision.
        # ----------------------------------------------------

        decision = (
            await decision_repo
            .get_pending_for_execution(
                execution.id
            )
        )

        # ----------------------------------------------------
        # Otherwise return the latest historical decision.
        # ----------------------------------------------------

        if decision is None:

            decision = (
                await decision_repo
                .get_latest_for_execution(
                    execution.id
                )
            )

        if decision is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    "No human decision exists "
                    "for this execution."
                ),
            )

        return HumanDecisionResponse(
            id=decision.id,

            execution_id=(
                decision.execution_id
            ),

            status=decision.status,

            decision=decision.decision,

            feedback=decision.feedback,

            decided_by=decision.decided_by,

            decided_at=decision.decided_at,

            approval_level=(
                decision.approval_level
            ),

            escalation_trigger=(
                decision.escalation_trigger
            ),

            proposed_action=(
                decision.proposed_action
            ),

            review_context=(
                HITLReviewContext.model_validate(
                    decision.review_context
                )
                if decision.review_context
                is not None
                else None
            ),

            created_at=decision.created_at,
        )


# ============================================================
# SUBMIT HUMAN DECISION
# ============================================================


@router.post(
    "/{execution_id}/human-decision",
    response_model=HumanDecisionResponse,
    status_code=status.HTTP_200_OK,
)
async def decide_human_decision(
    execution_id: UUID,
    payload: HumanDecisionCreate,
) -> HumanDecisionResponse:

    async with AsyncSessionLocal() as session:

        execution_repo = (
            ExecutionRepository(session)
        )

        decision_repo = (
            HumanDecisionRepository(session)
        )

        # ----------------------------------------------------
        # 1. Find execution
        # ----------------------------------------------------

        execution = await execution_repo.get(
            execution_id
        )

        if execution is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="Execution not found.",
            )

        # ----------------------------------------------------
        # 2. Execution must be waiting for HITL
        # ----------------------------------------------------

        if execution.status != "escalated":

            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Execution is not waiting "
                    "for a human decision."
                ),
            )

        if not execution.human_escalation_required:

            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Execution does not currently "
                    "require human intervention."
                ),
            )

        # ----------------------------------------------------
        # 3. Find pending decision
        # ----------------------------------------------------

        decision = (
            await decision_repo
            .get_pending_for_execution(
                execution.id
            )
        )

        if decision is None:

            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    "Pending human decision not found."
                ),
            )

        # ----------------------------------------------------
        # 4. Persist human decision
        # ----------------------------------------------------

        try:

            decision_value = (
                payload.decision.value
            )

            decision = (
                await decision_repo.decide(
                    decision_id=decision.id,

                    decision=decision_value,

                    feedback=payload.feedback,

                    decided_by=payload.decided_by,
                )
            )

            execution = (
                await execution_repo
                .apply_human_decision(
                    execution_id=execution.id,

                    decision=decision_value,

                    feedback=decision.feedback,

                    decided_at=decision.decided_at,
                )
            )

            if execution is None:

                raise ValueError(
                    "Execution disappeared while "
                    "saving the human decision."
                )

            # ------------------------------------------------
            # Mark as resuming before publishing Celery.
            # ------------------------------------------------

            await execution_repo.mark_resuming(
                execution.id
            )

            await session.commit()

        except ValueError as exc:

            await session.rollback()

            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=str(exc),
            ) from exc

        # ----------------------------------------------------
        # 5. Queue resume task
        # ----------------------------------------------------

        try:

            celery_result = (
                resume_agentflow_execution.delay(
                    execution_id=str(
                        execution.id
                    ),

                    decision_id=str(
                        decision.id
                    ),
                )
            )

        except Exception as exc:

            # ------------------------------------------------
            # Decision is already durable.
            #
            # Restore escalated state so the resume endpoint
            # can be used again.
            # ------------------------------------------------

            async with AsyncSessionLocal() as recovery_session:

                recovery_repo = (
                    ExecutionRepository(
                        recovery_session
                    )
                )

                await recovery_repo.update_status(
                    execution.id,
                    "escalated",
                )

                recovery_execution = (
                    await recovery_repo.get(
                        execution.id
                    )
                )

                if recovery_execution is not None:

                    recovery_execution.human_decision_status = (
                        "decided"
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
            ) from exc

        # ----------------------------------------------------
        # 6. Return decision
        # ----------------------------------------------------

        return HumanDecisionResponse(
            id=decision.id,

            execution_id=(
                decision.execution_id
            ),

            status=decision.status,

            decision=decision.decision,

            feedback=decision.feedback,

            decided_by=decision.decided_by,

            decided_at=decision.decided_at,

            approval_level=(
                decision.approval_level
            ),

            escalation_trigger=(
                decision.escalation_trigger
            ),

            proposed_action=(
                decision.proposed_action
            ),

            review_context=(
                HITLReviewContext.model_validate(
                    decision.review_context
                )
                if decision.review_context
                is not None
                else None
            ),

            created_at=decision.created_at,

            resume_task_id=(
                celery_result.id
            ),
        )


# ============================================================
# RETRY RESUME
# ============================================================


@router.post(
    "/{execution_id}/human-decision/"
    "{decision_id}/resume",
    response_model=HumanDecisionResponse,
    status_code=status.HTTP_200_OK,
)
async def retry_human_decision_resume(
    execution_id: UUID,
    decision_id: UUID,
) -> HumanDecisionResponse:

    async with AsyncSessionLocal() as session:

        execution_repo = (
            ExecutionRepository(session)
        )

        decision_repo = (
            HumanDecisionRepository(session)
        )

        # ----------------------------------------------------
        # 1. Find execution
        # ----------------------------------------------------

        execution = await execution_repo.get(
            execution_id
        )

        if execution is None:

            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="Execution not found.",
            )

        # ----------------------------------------------------
        # 2. Find decision
        # ----------------------------------------------------

        decision = await decision_repo.get(
            decision_id
        )

        if decision is None:

            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="Human decision not found.",
            )

        # ----------------------------------------------------
        # 3. Verify ownership
        # ----------------------------------------------------

        if decision.execution_id != execution.id:

            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Human decision does not belong "
                    "to this execution."
                ),
            )

        # ----------------------------------------------------
        # 4. Decision must already be decided
        # ----------------------------------------------------

        if decision.status != "decided":

            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Human decision has not been decided."
                ),
            )

        # ----------------------------------------------------
        # 5. Execution must be resumable
        # ----------------------------------------------------

        if execution.status not in {
            "escalated",
            "resuming",
            # The previous Celery resume attempt may have failed
            # after the decision was durably saved. Allow the
            # reviewer to explicitly retry that resume.
            "failed",
        }:

            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Execution is not waiting "
                    "for HITL resume."
                ),
            )

        # ----------------------------------------------------
        # 6. Mark the execution as resuming before publishing
        # the retry task.
        # ----------------------------------------------------

        await execution_repo.mark_resuming(
            execution.id
        )
        await session.commit()

        # ----------------------------------------------------
        # 7. Queue resume task
        # ----------------------------------------------------

        try:

            celery_result = (
                resume_agentflow_execution.delay(
                    execution_id=str(
                        execution.id
                    ),

                    decision_id=str(
                        decision.id
                    ),
                )
            )

        except Exception as exc:

            # Restore the resumable HITL state if Celery could not
            # be reached. The decision remains durable and can be
            # retried through this endpoint.
            await session.rollback()

            recovery_execution = await execution_repo.get(
                execution.id
            )

            if recovery_execution is not None:
                recovery_execution.status = "escalated"
                recovery_execution.human_decision_status = "decided"
                recovery_execution.human_escalation_required = True
                recovery_execution.escalation_required = True
                await session.commit()

            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail=(
                    "The resume task could not be queued."
                ),
            ) from exc

        # ----------------------------------------------------
        # 8. Return existing decision
        # ----------------------------------------------------

        return HumanDecisionResponse(
            id=decision.id,

            execution_id=(
                decision.execution_id
            ),

            status=decision.status,

            decision=decision.decision,

            feedback=decision.feedback,

            decided_by=decision.decided_by,

            decided_at=decision.decided_at,

            approval_level=(
                decision.approval_level
            ),

            escalation_trigger=(
                decision.escalation_trigger
            ),

            proposed_action=(
                decision.proposed_action
            ),

            review_context=(
                HITLReviewContext.model_validate(
                    decision.review_context
                )
                if decision.review_context
                is not None
                else None
            ),

            created_at=decision.created_at,

            resume_task_id=(
                celery_result.id
            ),
        )