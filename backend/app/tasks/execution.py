from __future__ import annotations

import asyncio
from uuid import UUID

from app.config import get_settings
from app.db.repositories.execution import ExecutionRepository
from app.celery_app import celery_app
from app.db.repositories.human_decision import (
    HumanDecisionRepository,
)
from app.db.repositories.task import TaskRepository
from app.db.session import AsyncSessionLocal
from app.graph.workflow import (
    _build_hitl_review_context,
    build_workflow,
)
from app.runtime.dependencies import build_agent_runtime


async def _execute_agentflow_task(
    *,
    task_id: str,
    execution_id: str,
    user_id: str,
    description: str,
) -> dict:

    settings = get_settings()

    task_uuid = UUID(task_id)
    execution_uuid = UUID(execution_id)

    async with AsyncSessionLocal() as session:

        task_repo = TaskRepository(session)

        execution_repo = ExecutionRepository(
            session
        )

        human_decision_repo = (
            HumanDecisionRepository(session)
        )

        # =====================================================
        # 1. Task
        # =====================================================

        task = await task_repo.get(
            task_uuid
        )

        if task is None:
            task = await task_repo.create(
                task_id=task_uuid,
                user_id=user_id,
                description=description,
            )

        # =====================================================
        # 2. Execution
        # =====================================================

        execution = await execution_repo.get(
            execution_uuid
        )

        if execution is None:

            execution = await execution_repo.create(
                task_id=task.id,
                execution_id=execution_uuid,
                status="running",
            )

        else:

            await execution_repo.update_status(
                execution.id,
                "running",
            )

        await session.commit()

        try:

            # =================================================
            # 3. Runtime
            # =================================================

            runtime = await build_agent_runtime(
                settings
            )

            # =================================================
            # 4. Workflow
            # =================================================

            workflow = build_workflow(
                supervisor=runtime.supervisor,
                research_agent=runtime.research_agent,
                analysis_agent=runtime.analysis_agent,
                writing_agent=runtime.writing_agent,
                coding_agent=runtime.coding_agent,
                reviewer_agent=runtime.reviewer_agent,
                working_memory=runtime.working_memory,
                long_term_memory=runtime.long_term_memory,
                memory_service=runtime.memory_service,
            )

            # =================================================
            # 5. Execute
            # =================================================

            result = await workflow.ainvoke(
                {
                    "task_id": str(task.id),
                    "user_id": str(user_id),
                    "description": description,
                    "resume_from_human": False,
                }
            )

            # =================================================
            # 6. Result metadata
            # =================================================

            execution_status = result.get(
                "execution_status",
                "completed",
            )

            escalation_required = bool(
                result.get(
                    "escalation_required",
                    False,
                )
            )

            human_escalation_required = bool(
                result.get(
                    "human_escalation_required",
                    False,
                )
            )

            escalation_reason = result.get(
                "escalation_reason"
            )

            specialist_confidence = result.get(
                "specialist_confidence"
            )

            confidence_threshold = result.get(
                "confidence_threshold"
            )

            resume_node = result.get(
                "resume_node"
            )

            resume_subtask_id = result.get(
                "resume_subtask_id"
            )

            if resume_subtask_id is not None:
                resume_subtask_id = UUID(
                    str(resume_subtask_id)
                )

            # =================================================
            # 7. HITL escalation
            # =================================================

            if (
                execution_status == "escalated"
                or human_escalation_required
            ):

                # -------------------------------------------------
                # HITL review metadata
                # -------------------------------------------------

                approval_level = result.get(
                    "approval_level"
                )

                escalation_trigger = result.get(
                    "escalation_trigger"
                )

                proposed_action = result.get(
                    "proposed_action",
                    "Continue execution.",
                )

                # -------------------------------------------------
                # Build the complete review packet while the
                # workflow state is still available.
                # -------------------------------------------------

                review_context = (
                    _build_hitl_review_context(
                        result,
                        proposed_action=proposed_action,
                        reasoning=(
                            escalation_reason
                        ),
                    )
                )

                # -------------------------------------------------
                # Persist execution escalation.
                # -------------------------------------------------

                persisted_execution = (
                    await execution_repo.mark_escalated(
                        execution_id=execution.id,
                        escalation_required=(
                            escalation_required
                        ),
                        human_escalation_required=True,
                        escalation_reason=(
                            escalation_reason
                        ),
                        specialist_confidence=(
                            specialist_confidence
                        ),
                        confidence_threshold=(
                            confidence_threshold
                        ),
                        resume_node=(
                            resume_node
                        ),
                        resume_subtask_id=(
                            resume_subtask_id
                        ),
                    )
                )

                if persisted_execution is None:
                    raise RuntimeError(
                        "Execution disappeared while "
                        "persisting escalation."
                    )

                # -------------------------------------------------
                # Create one durable pending HITL decision.
                #
                # IMPORTANT:
                # Existing pending decisions are preserved so
                # repeated execution/retry cannot create duplicate
                # approval queue entries.
                # -------------------------------------------------

                decision = await human_decision_repo.get_or_create_pending(
                    execution_id=execution.id,
                    approval_level=approval_level,
                    escalation_trigger=escalation_trigger,
                    proposed_action=proposed_action,
                    review_context=review_context,
                )

                await session.commit()

                return {
                    "task_id": str(task.id),
                    "execution_id": str(
                        execution.id
                    ),
                    "status": "escalated",
                    "final_output": None,
                    "error": result.get(
                        "error"
                    ),
                    "escalation_required": (
                        escalation_required
                    ),
                    "human_escalation_required": True,
                    "escalation_reason": (
                        escalation_reason
                    ),
                    "specialist_confidence": (
                        specialist_confidence
                    ),
                    "confidence_threshold": (
                        confidence_threshold
                    ),
                    "approval_level": (
                        approval_level
                    ),
                    "escalation_trigger": (
                        escalation_trigger
                    ),
                    "proposed_action": (
                        proposed_action
                    ),
                    "review_context": (
                        review_context
                    ),
                    "resume_node": (
                        resume_node
                    ),
                    "resume_subtask_id": (
                        str(
                            resume_subtask_id
                        )
                        if resume_subtask_id
                        else None
                    ),
                }

            # =================================================
            # 8. Rejected
            # =================================================

            if execution_status == "rejected":

                await execution_repo.update_status(
                    execution.id,
                    "rejected",
                )

                await session.commit()

                return {
                    "task_id": str(task.id),
                    "execution_id": str(
                        execution.id
                    ),
                    "status": "rejected",
                    "final_output": None,
                    "error": result.get(
                        "error"
                    ),
                }

            # =================================================
            # 9. Normal completion
            # =================================================

            await execution_repo.update_status(
                execution.id,
                execution_status,
            )

            await session.commit()

            return {
                "task_id": str(task.id),
                "execution_id": str(
                    execution.id
                ),
                "status": execution_status,
                "final_output": result.get(
                    "final_output"
                ),
                "error": result.get(
                    "error"
                ),
                "escalation_required": (
                    escalation_required
                ),
                "human_escalation_required": (
                    human_escalation_required
                ),
                "escalation_reason": (
                    escalation_reason
                ),
                "specialist_confidence": (
                    specialist_confidence
                ),
                "confidence_threshold": (
                    confidence_threshold
                ),
                "resume_node": (
                    resume_node
                ),
                "resume_subtask_id": (
                    str(
                        resume_subtask_id
                    )
                    if resume_subtask_id
                    else None
                ),
            }

        except Exception:

            await execution_repo.update_status(
                execution.id,
                "failed",
            )

            await session.commit()

            raise


@celery_app.task(
    bind=True,
    name="agentflow.execute_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={
        "max_retries": 3,
    },
)
def execute_agentflow_task(
    self,
    *,
    task_id: str,
    execution_id: str,
    user_id: str,
    description: str,
) -> dict:
    """
    Celery entry point for a new AgentFlow execution.
    """

    return asyncio.run(
        _execute_agentflow_task(
            task_id=task_id,
            execution_id=execution_id,
            user_id=user_id,
            description=description,
        )
    )