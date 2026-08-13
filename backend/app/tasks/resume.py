from __future__ import annotations

import asyncio
from uuid import UUID

from app.celery_app import celery_app
from app.config import get_settings
from app.db.repositories.execution import ExecutionRepository
from app.db.repositories.human_decision import (
    HumanDecisionRepository,
)
from app.db.session import AsyncSessionLocal
from app.graph.workflow import build_workflow
from app.runtime.dependencies import build_agent_runtime
from app.schemas.execution import ExecutionPlan
from app.schemas.review import ReviewResult


async def _resume_agentflow_execution(
    *,
    execution_id: str,
    decision_id: str,
) -> dict:
    """
    Resume an escalated AgentFlow execution after a human decision.

    Supported decisions:

        approve
            Continue the existing execution.

        replan
            Create a new plan using human feedback.

        reject
            Permanently reject the execution.

        notify
            Continue execution after notifying the reviewer.

        approve_action
            Approve the proposed action and continue.

        approve_plan
            Approve the proposed plan and continue.

        take_over
            Transfer execution to human control.

    Redis working memory is used to reconstruct the graph state
    that existed when the workflow reached the HITL boundary.
    """

    execution_uuid = UUID(execution_id)
    decision_uuid = UUID(decision_id)

    settings = get_settings()

    async with AsyncSessionLocal() as session:
        execution_repo = ExecutionRepository(session)
        decision_repo = HumanDecisionRepository(session)

        # =====================================================
        # 1. Load execution
        # =====================================================

        execution = await execution_repo.get(
            execution_uuid
        )

        if execution is None:
            raise ValueError(
                "Execution was not found."
            )

        # -----------------------------------------------------
        # Idempotency
        #
        # Celery can deliver a task more than once. Never
        # execute an already-terminal execution again.
        # -----------------------------------------------------

        if execution.status == "completed":
            return {
                "task_id": str(execution.task_id),
                "execution_id": str(execution.id),
                "status": "completed",
                "final_output": None,
                "error": None,
            }

        if execution.status == "rejected":
            return {
                "task_id": str(execution.task_id),
                "execution_id": str(execution.id),
                "status": "rejected",
                "final_output": None,
                "error": (
                    "Execution was already rejected."
                ),
            }

        # -----------------------------------------------------
        # Only an escalated/resuming execution can be resumed.
        # A HITL resume can fail after the human decision has
        # already been persisted. The retry-resume endpoint
        # intentionally allows failed state.
        # -----------------------------------------------------

        if execution.status not in {
            "escalated",
            "resuming",
            "failed",
        }:
            raise ValueError(
                "Execution is not in a resumable HITL state."
            )

        # =====================================================
        # 2. Load decision
        # =====================================================

        decision = await decision_repo.get(
            decision_uuid
        )

        if decision is None:
            raise ValueError(
                "Human decision was not found."
            )

        if decision.execution_id != execution.id:
            raise ValueError(
                "Human decision does not belong "
                "to this execution."
            )

        if decision.status != "decided":
            raise ValueError(
                "Human decision has not been decided."
            )

        ALLOWED_HUMAN_DECISIONS = {
            "approve",
            "replan",
            "reject",
            "notify",
            "approve_action",
            "approve_plan",
            "take_over",
        }

        if decision.decision not in ALLOWED_HUMAN_DECISIONS:
            raise ValueError(
                "Unsupported human decision."
            )

        # -----------------------------------------------------
        # Move execution explicitly into resuming state.
        # -----------------------------------------------------

        if execution.status != "resuming":
            execution.status = "resuming"
            await session.flush()

        # =====================================================
        # 3. Load task
        # =====================================================

        task = execution.task

        if task is None:
            raise ValueError(
                "Execution has no associated task."
            )

        # =====================================================
        # 4. Reject
        # =====================================================

        if decision.decision == "reject":
            await execution_repo.update_status(
                execution.id,
                "rejected",
            )

            execution.human_decision_status = (
                "completed"
            )

            execution.human_escalation_required = False
            execution.escalation_required = False

            await session.commit()

            return {
                "task_id": str(task.id),
                "execution_id": str(execution.id),
                "status": "rejected",
                "final_output": None,
                "error": (
                    "Execution was rejected by "
                    "the human reviewer."
                ),
            }

        # =====================================================
        # 5. Human takeover
        # =====================================================

        if decision.decision == "take_over":
            await execution_repo.update_status(
                execution.id,
                "human_takeover",
            )

            execution.human_decision_status = "completed"

            execution.human_escalation_required = False
            execution.escalation_required = False

            execution.human_feedback = (
                decision.feedback
                or "Execution was transferred to human control."
            )

            await session.commit()

            return {
                "task_id": str(task.id),
                "execution_id": str(execution.id),
                "status": "human_takeover",
                "final_output": None,
                "error": None,
            }

        # =====================================================
        # 6. Build runtime
        # =====================================================

        runtime = await build_agent_runtime(
            settings
        )

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

        # =====================================================
        # 7. Restore Redis working-memory snapshot
        # =====================================================

        memory = runtime.working_memory

        snapshot = await memory.snapshot(
            str(task.id)
        )

        if not isinstance(snapshot, dict):
            raise ValueError(
                "Working-memory snapshot is invalid."
            )

        # -----------------------------------------------------
        # Plan
        # -----------------------------------------------------

        plan_data = snapshot.get(
            "plan"
        )

        resume_node = (
            execution.resume_node
            or ""
        ).strip().lower()

        # -----------------------------------------------------
        # A plan is not required when:
        #
        #   1. escalation happened before planning
        #   2. human selected replan
        #
        # In both cases the workflow can construct a fresh plan.
        # -----------------------------------------------------

        plan_required = (
            decision.decision != "replan"
            and resume_node != "planning"
        )

        if plan_required and not plan_data:
            raise ValueError(
                "Cannot resume execution because "
                "the execution plan was not found "
                "in working memory."
            )

        plan = None

        if plan_data:
            plan = ExecutionPlan.model_validate(
                plan_data
            )

        # -----------------------------------------------------
        # Specialist outputs
        # -----------------------------------------------------

        specialist_outputs = snapshot.get(
            "subtask_outputs",
            [],
        )

        if not isinstance(
            specialist_outputs,
            list,
        ):
            specialist_outputs = []

        valid_outputs: list[dict] = []

        for output in specialist_outputs:
            if isinstance(output, dict):
                valid_outputs.append(output)

        specialist_outputs = valid_outputs

        # -----------------------------------------------------
        # Completed subtasks
        # -----------------------------------------------------

        completed_subtasks: list[str] = []

        for output in specialist_outputs:
            subtask_id = output.get(
                "subtask_id"
            )

            if subtask_id is not None:
                completed_subtasks.append(
                    str(subtask_id)
                )

        completed_subtasks = list(
            dict.fromkeys(
                completed_subtasks
            )
        )

        # =====================================================
        # 8. Restore intermediate results
        # =====================================================

        intermediate_results = snapshot.get(
            "intermediate_results",
            {},
        )

        if not isinstance(
            intermediate_results,
            dict,
        ):
            intermediate_results = {}

        review_data = intermediate_results.get(
            "review"
        )

        review = None

        if (
            review_data is not None
            and isinstance(
                review_data,
                dict,
            )
        ):
            review = ReviewResult.model_validate(
                review_data
            )

        # =====================================================
        # 9. Restore long-term memory
        # =====================================================

        long_term_memories: list[dict] = []

        if task.user_id:
            memory_results = (
                await runtime.long_term_memory.search(
                    user_id=str(task.user_id),
                    query=task.description,
                    limit=5,
                )
            )

            long_term_memories = [
                {
                    "memory": result.memory.model_dump(
                        mode="json"
                    ),
                    "distance": result.distance,
                }
                for result in memory_results
            ]

        # =====================================================
        # 10. Determine confidence threshold
        # =====================================================

        confidence_threshold = (
            execution.confidence_threshold
        )

        if confidence_threshold is None:
            confidence_threshold = 0.5

        # =====================================================
        # 11. Build restored graph state
        # =====================================================

        state: dict = {
            "task_id": str(task.id),

            "user_id": (
                str(task.user_id)
                if task.user_id
                else ""
            ),

            "description": task.description,

            "plan": plan,

            "ready_subtasks": [],

            "completed_subtasks": (
                completed_subtasks
            ),

            "specialist_outputs": (
                specialist_outputs
            ),

            "long_term_memories": (
                long_term_memories
            ),

            "retry_count": 0,

            "max_retries": 2,

            "failure_reason": "",

            "retry_feedback": "",

            "review_retry_count": 0,

            "max_review_retries": 2,

            "review_feedback": (
                decision.feedback or ""
            ),

            "specialist_confidence": (
                1.0
                if decision.decision == "replan"
                else (
                    execution.specialist_confidence
                    if execution.specialist_confidence
                    is not None
                    else 1.0
                )
            ),

            "confidence_threshold": (
                confidence_threshold
            ),

            "human_escalation_required": False,

            "escalation_required": False,

            "escalation_reason": (
                execution.escalation_reason
                or ""
            ),

            "replan_required": (
                decision.decision == "replan"
            ),

            "resume_node": (
                execution.resume_node
                or "post_specialist"
            ),

            "resume_subtask_id": (
                str(
                    execution.resume_subtask_id
                )
                if execution.resume_subtask_id
                else None
            ),

            "human_decision_status": (
                "decided"
            ),

            "human_decision": (
                decision.decision
            ),

            "human_feedback": (
                decision.feedback
            ),

            "resume_from_human": True,

            "execution_status": "running",

            "error": "",
        }

        if review is not None:
            state["review"] = review

        # -----------------------------------------------------
        # Replan starts a fresh planning/specialist cycle.
        # Do not carry the previous low-confidence escalation
        # into the new plan.
        # -----------------------------------------------------

        if decision.decision == "replan":
            execution.specialist_confidence = None
            execution.escalation_required = False
            execution.human_escalation_required = False

            await session.flush()

        # =====================================================
        # 12. Resume workflow
        # =====================================================

        try:
            result = await workflow.ainvoke(
                state
            )

            if not isinstance(result, dict):
                raise ValueError(
                    "Workflow returned an invalid result."
                )

            final_status = result.get(
                "execution_status",
                "completed",
            )

            # -------------------------------------------------
            # Persist current workflow status first.
            # -------------------------------------------------

            await execution_repo.update_status(
                execution.id,
                final_status,
            )

            # =================================================
            # 13. New HITL boundary
            # =================================================

            if final_status == "escalated":

                escalation_required = bool(
                    result.get(
                        "escalation_required",
                        True,
                    )
                )

                human_escalation_required = bool(
                    result.get(
                        "human_escalation_required",
                        True,
                    )
                )

                escalation_reason = (
                    result.get(
                        "escalation_reason"
                    )
                    or execution.escalation_reason
                    or "Human review is required."
                )

                specialist_confidence = (
                    result.get(
                        "specialist_confidence"
                    )
                )

                new_confidence_threshold = (
                    result.get(
                        "confidence_threshold"
                    )
                )

                if new_confidence_threshold is None:
                    new_confidence_threshold = (
                        confidence_threshold
                    )

                new_resume_node = result.get(
                    "resume_node"
                )

                if new_resume_node is None:
                    new_resume_node = (
                        execution.resume_node
                        or "post_specialist"
                    )

                new_resume_subtask_id = (
                    result.get(
                        "resume_subtask_id"
                    )
                )

                if (
                    new_resume_subtask_id
                    is not None
                ):
                    new_resume_subtask_id = UUID(
                        str(
                            new_resume_subtask_id
                        )
                    )

                approval_level = result.get(
                    "approval_level"
                )

                escalation_trigger = result.get(
                    "escalation_trigger"
                )

                proposed_action = (
                    result.get(
                        "proposed_action"
                    )
                    or "Continue execution."
                )

                # -------------------------------------------------
                # IMPORTANT:
                #
                # A resumed workflow may not return review_context.
                #
                # The first escalation usually has it, but a second
                # escalation after approve/replan may only return the
                # workflow state.
                #
                # The reviewer API requires a complete context, so
                # reconstruct it here.
                # -------------------------------------------------

                review_context = result.get(
                    "review_context"
                )

                # Convert a Pydantic/model context if one was returned.
                if review_context is not None:
                    if hasattr(
                        review_context,
                        "model_dump",
                    ):
                        review_context = (
                            review_context.model_dump(
                                mode="json"
                            )
                        )
                    elif not isinstance(
                        review_context,
                        dict,
                    ):
                        review_context = None

                # -------------------------------------------------
                # Prefer explicit values from the workflow result.
                # Fall back to restored state/snapshot.
                # -------------------------------------------------

                result_plan = result.get(
                    "plan"
                )

                if result_plan is None:
                    result_plan = state.get(
                        "plan"
                    )

                if hasattr(
                    result_plan,
                    "model_dump",
                ):
                    result_plan = (
                        result_plan.model_dump(
                            mode="json"
                        )
                    )

                result_completed_steps = (
                    result.get(
                        "completed_steps"
                    )
                )

                if result_completed_steps is None:
                    result_completed_steps = (
                        result.get(
                            "specialist_outputs"
                        )
                    )

                if result_completed_steps is None:
                    result_completed_steps = (
                        state.get(
                            "specialist_outputs",
                            [],
                        )
                    )

                if not isinstance(
                    result_completed_steps,
                    list,
                ):
                    result_completed_steps = []

                result_current_step = (
                    result.get(
                        "current_step"
                    )
                )

                if result_current_step is None:
                    result_current_step = (
                        state.get(
                            "current_step"
                        )
                    )

                result_reasoning = (
                    result.get(
                        "reasoning"
                    )
                )

                if result_reasoning is None:
                    result_reasoning = (
                        execution.escalation_reason
                        or escalation_reason
                    )

                result_memories = (
                    result.get(
                        "relevant_memories"
                    )
                )

                if result_memories is None:
                    result_memories = (
                        state.get(
                            "long_term_memories",
                            [],
                        )
                    )

                result_past_decisions = (
                    result.get(
                        "past_decisions"
                    )
                )

                if result_past_decisions is None:
                    result_past_decisions = []

                # -------------------------------------------------
                # If the workflow did not provide review_context,
                # construct the exact packet expected by the
                # reviewer API/UI.
                # -------------------------------------------------

                if review_context is None:
                    review_context = {
                        "original_task": (
                            task.description
                        ),

                        "plan": (
                            result_plan
                        ),

                        "completed_steps": (
                            result_completed_steps
                        ),

                        "current_step": (
                            result_current_step
                        ),

                        "proposed_action": (
                            proposed_action
                        ),

                        "reasoning": (
                            result_reasoning
                        ),

                        "relevant_memories": (
                            result_memories
                        ),

                        "past_decisions": (
                            result_past_decisions
                        ),
                    }

                # -------------------------------------------------
                # Guarantee the two required reviewer fields are
                # always populated.
                # -------------------------------------------------

                if not review_context.get(
                    "original_task"
                ):
                    review_context[
                        "original_task"
                    ] = task.description

                if not review_context.get(
                    "proposed_action"
                ):
                    review_context[
                        "proposed_action"
                    ] = proposed_action

                if "plan" not in review_context:
                    review_context["plan"] = (
                        result_plan
                    )

                if "completed_steps" not in review_context:
                    review_context[
                        "completed_steps"
                    ] = result_completed_steps

                if "current_step" not in review_context:
                    review_context[
                        "current_step"
                    ] = result_current_step

                if "reasoning" not in review_context:
                    review_context[
                        "reasoning"
                    ] = result_reasoning

                if "relevant_memories" not in review_context:
                    review_context[
                        "relevant_memories"
                    ] = result_memories

                if "past_decisions" not in review_context:
                    review_context[
                        "past_decisions"
                    ] = result_past_decisions

                # -------------------------------------------------
                # Persist NEW escalation metadata.
                # -------------------------------------------------

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
                    new_confidence_threshold
                )

                execution.resume_node = (
                    new_resume_node
                )

                execution.resume_subtask_id = (
                    new_resume_subtask_id
                )

                # -------------------------------------------------
                # The previous human decision remains decided.
                # Create a NEW pending decision for the NEW
                # HITL boundary.
                # -------------------------------------------------

                execution.human_decision_status = (
                    "pending"
                )

                execution.human_decision = None

                execution.human_feedback = None

                execution.human_decided_at = None

                await decision_repo.create_pending(
                    execution_id=execution.id,
                    approval_level=approval_level,
                    escalation_trigger=(
                        escalation_trigger
                    ),
                    proposed_action=(
                        proposed_action
                    ),
                    review_context=(
                        review_context
                    ),
                )

            else:
                # =================================================
                # 14. Terminal/non-HITL state
                # =================================================

                execution.human_decision_status = (
                    "completed"
                )

                execution.human_escalation_required = (
                    False
                )

                execution.escalation_required = (
                    False
                )

                if result.get("error"):
                    execution.human_feedback = (
                        result.get(
                            "error"
                        )
                    )

            await session.commit()

            return {
                "task_id": str(task.id),
                "execution_id": str(execution.id),
                "status": final_status,
                "final_output": result.get(
                    "final_output"
                ),
                "error": result.get(
                    "error"
                ),
            }

        except Exception:
            await session.rollback()
            raise


@celery_app.task(
    bind=True,
    name="agentflow.resume_execution",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={
        "max_retries": 3,
    },
)
def resume_agentflow_execution(
    self,
    *,
    execution_id: str,
    decision_id: str,
) -> dict:
    """
    Celery entry point for HITL workflow resumption.
    """

    return asyncio.run(
        _resume_agentflow_execution(
            execution_id=execution_id,
            decision_id=decision_id,
        )
    )