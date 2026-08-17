from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

from app.celery_app import celery_app
from app.config import get_settings
from app.db.repositories.execution import ExecutionRepository
from app.db.repositories.human_decision import (
    HumanDecisionRepository,
)
from app.db.repositories.task import TaskRepository
from app.db.repositories.subtask import SubTaskRepository
from app.db.session import AsyncSessionLocal
from app.graph.workflow import (
    _build_hitl_review_context,
    build_workflow,
)
from app.observability.repository import TraceRepository
from app.observability.tracing import (
    ExecutionTrace,
    current_trace,
    start_trace,
    use_trace,
)
from app.runtime.dependencies import build_agent_runtime
from app.schemas.execution import Complexity, Specialist, SubTask


def _coerce_complexity(
    value: Any,
) -> Complexity:
    """
    Normalize persisted replay complexity values.

    Supports:
        low
        LOW
        Low
        Complexity.LOW
        "Complexity.LOW"

    The database/replay payload may contain enum names while
    the Pydantic model expects enum values.
    """

    if isinstance(value, Complexity):
        return value

    if value is None:
        return Complexity.MEDIUM

    text = str(value).strip()

    if not text:
        return Complexity.MEDIUM

    # Handle strings such as "Complexity.LOW".
    if text.lower().startswith("complexity."):
        text = text.split(".", 1)[1]

    # First try enum VALUE.
    try:
        return Complexity(text.lower())
    except ValueError:
        pass

    # Then try enum NAME.
    try:
        return Complexity[text.upper()]
    except KeyError as exc:
        raise ValueError(
            f"Unknown complexity value: {value!r}"
        ) from exc


def _coerce_specialist(
    value: Any,
) -> Specialist:
    """
    Normalize persisted specialist values.

    Supports:
        code_execution
        CODE_EXECUTION
        Specialist.CODE_EXECUTION
    """

    if isinstance(value, Specialist):
        return value

    if value is None:
        raise ValueError(
            "Replay source subtask is missing assigned_specialist."
        )

    text = str(value).strip()

    if text.lower().startswith("specialist."):
        text = text.split(".", 1)[1]

    try:
        return Specialist(text.lower())
    except ValueError:
        try:
            return Specialist[text.upper()]
        except KeyError as exc:
            raise ValueError(
                f"Unknown specialist value: {value!r}"
            ) from exc


async def _persist_trace(
    *,
    session,
    trace: ExecutionTrace,
    status: str,
) -> bool:
    print(
        "[TRACE] persist start "
        f"execution_id={trace.execution_id} "
        f"trace_id={trace.trace_id} "
        f"status={status} "
        f"spans={len(trace.spans)}"
    )

    trace.finish(status)

    try:
        trace_repo = TraceRepository(session)

        await trace_repo.save(trace)

        print(
            "[TRACE] repository save complete "
            f"execution_id={trace.execution_id} "
            f"trace_id={trace.trace_id}"
        )

        return True

    except Exception as exc:
        print(
            "[TRACE] repository save FAILED "
            f"{type(exc).__name__}: {exc}"
        )
        return False


def _apply_trace_statuses(
    *,
    trace: ExecutionTrace,
    execution_status: str,
    specialist_confidence: float | None,
    confidence_threshold: float | None,
    resume_subtask_id: UUID | None,
) -> None:
    """
    Align persisted span statuses with the final execution outcome.

    The workflow/agent spans describe whether an individual operation
    completed, while the execution span describes the overall outcome.

    Therefore:
        execution -> escalated when the workflow requires HITL
        specialist -> warning when it completed but confidence is below
                       the configured threshold
    """

    # ---------------------------------------------------------
    # Root execution span
    # ---------------------------------------------------------

    root_span = next(
        (
            span
            for span in trace.spans
            if span.name == "execution"
            and span.parent_span_id is None
        ),
        None,
    )

    if root_span is not None:
        root_span.status = execution_status

        root_span.attributes[
            "execution_status"
        ] = execution_status

    # ---------------------------------------------------------
    # Low-confidence specialist
    # ---------------------------------------------------------

    if (
        specialist_confidence is None
        or confidence_threshold is None
        or specialist_confidence >= confidence_threshold
    ):
        return

    specialist_spans = [
        span
        for span in trace.spans
        if span.name == "specialist"
    ]

    if not specialist_spans:
        return

    target_span = None

    # Prefer the exact subtask that caused the escalation.
    if resume_subtask_id is not None:
        target_span = next(
            (
                span
                for span in specialist_spans
                if span.subtask_id == resume_subtask_id
            ),
            None,
        )

    # Backward-compatible fallback for traces where the
    # specialist span does not contain a subtask_id.
    if target_span is None:
        target_span = specialist_spans[-1]

    target_span.status = "warning"
    target_span.confidence = specialist_confidence

    target_span.attributes[
        "confidence_threshold"
    ] = confidence_threshold

    target_span.attributes[
        "status_reason"
    ] = (
        "Specialist completed with confidence "
        "below the configured escalation threshold."
    )


async def _execute_agentflow_task(
    *,
    task_id: str,
    execution_id: str,
    user_id: str,
    description: str,
    context: dict | None = None,

    # ---------------------------------------------------------
    # Replay
    # ---------------------------------------------------------

    replay_source_execution_id: str | None = None,
    replay_source_span_id: str | None = None,
    replay_target_subtask_id: str | None = None,

    replay_target_subtask_description: str | None = None,
    replay_target_specialist: str | None = None,
    replay_target_span_name: str | None = None,
    replay_target_span_kind: str | None = None,

    replay_only: bool = False,

    replay_input_override=None,
    replay_source_subtask: dict | None = None,
) -> dict:

    settings = get_settings()
    execution_context = dict(context or {})

    task_uuid = UUID(task_id)
    execution_uuid = UUID(execution_id)

    async with AsyncSessionLocal() as session:

        task_repo = TaskRepository(session)

        execution_repo = ExecutionRepository(
            session
        )

        subtask_repo = SubTaskRepository(
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

        # =====================================================
        # 3. Create execution trace
        # =====================================================

        trace = start_trace(
            execution_id=execution.id,
            task_id=task.id,
            user_id=user_id,
        )

        if replay_source_execution_id:
            trace.attributes.update(
                {
                    "replay": True,

                    "replay_source_execution_id": (
                        replay_source_execution_id
                    ),

                    "replay_source_span_id": (
                        replay_source_span_id
                    ),

                    "replay_target_subtask_id": (
                        replay_target_subtask_id
                    ),

                    "replay_target_subtask_description": (
                        replay_target_subtask_description
                    ),

                    "replay_target_specialist": (
                        replay_target_specialist
                    ),

                    "replay_target_span_name": (
                        replay_target_span_name
                    ),

                    "replay_target_span_kind": (
                        replay_target_span_kind
                    ),

                    "replay_only": replay_only,
                }
            )

        try:

            # =================================================
            # 4. Runtime
            # =================================================

            runtime = await build_agent_runtime(
                settings
            )

            # =================================================
            # 5. Workflow
            # =================================================

            async def persist_plan_subtasks(
                *,
                execution_id: UUID,
                subtasks: list[SubTask],
            ) -> None:
                await subtask_repo.create_many(
                    execution_id=execution_id,
                    subtasks=subtasks,
                )
                await session.flush()

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
                persist_plan_subtasks=persist_plan_subtasks,
            )

            # =================================================
            # 6. Selected-span replay source SubTask
            # =================================================

            replay_source_subtask_model = None

            if replay_only:
                if not replay_source_subtask:
                    raise ValueError(
                        "Selected replay requires the persisted "
                        "source subtask definition."
                    )

                assigned_specialist = _coerce_specialist(
                    replay_source_subtask.get(
                        "assigned_specialist"
                    )
                )

                estimated_complexity = _coerce_complexity(
                    replay_source_subtask.get(
                        "estimated_complexity",
                        replay_source_subtask.get(
                            "complexity",
                            Complexity.MEDIUM.value,
                        ),
                    )
                )

                source_subtask_id = (
                    replay_source_subtask.get("id")
                    or replay_target_subtask_id
                )

                replay_source_subtask_model = SubTask(
                    id=(
                        UUID(str(source_subtask_id))
                        if source_subtask_id
                        else uuid4()
                    ),
                    description=str(
                        replay_source_subtask.get(
                            "description",
                            replay_target_subtask_description
                            or description,
                        )
                    ),
                    assigned_specialist=assigned_specialist,
                    required_inputs=list(
                        replay_source_subtask.get(
                            "required_inputs",
                            [],
                        )
                        or []
                    ),
                    expected_output=str(
                        replay_source_subtask.get(
                            "expected_output",
                            "",
                        )
                    ),
                    estimated_complexity=estimated_complexity,
                    dependencies=[],
                )

                # Never allow missing logical selectors to reach
                # workflow._get_replay_target_subtask().
                #
                # The planner creates a new UUID, so description +
                # specialist are the durable replay identity.
                if not replay_target_subtask_description:
                    replay_target_subtask_description = (
                        replay_source_subtask_model.description
                    )

                if not replay_target_specialist:
                    replay_target_specialist = (
                        replay_source_subtask_model
                        .assigned_specialist
                        .value
                    )

                if not replay_target_span_name:
                    replay_target_span_name = "specialist"

                if not replay_target_span_kind:
                    replay_target_span_kind = "specialist"

                # Keep the trace metadata consistent with the logical
                # selector actually sent to the workflow.
                trace.attributes.update(
                    {
                        "replay_target_subtask_description": (
                            replay_target_subtask_description
                        ),
                        "replay_target_specialist": (
                            replay_target_specialist
                        ),
                        "replay_target_span_name": (
                            replay_target_span_name
                        ),
                        "replay_target_span_kind": (
                            replay_target_span_kind
                        ),
                        "replay_source_subtask_id": (
                            str(
                                replay_source_subtask_model.id
                            )
                        ),
                    }
                )

            # =================================================
            # 7. Execute workflow inside trace context
            # =================================================

            with use_trace(trace):

                with current_trace(
                    name="execution",
                    kind="workflow",
                    execution_id=execution.id,
                    task_id=task.id,
                    user_id=user_id,
                ):

                    result = await workflow.ainvoke(
                        {
                            "task_id": str(task.id),

                            "execution_id": str(execution.id),

                            "user_id": user_id,

                            "description": description,

                            "context": execution_context,

                            # -----------------------------
                            # Replay source
                            # -----------------------------

                            "replay_source_execution_id": (
                                replay_source_execution_id
                            ),

                            "replay_source_span_id": (
                                replay_source_span_id
                            ),

                            "replay_source_subtask": (
                                replay_source_subtask_model
                            ),

                            # -----------------------------
                            # Replay target
                            # -----------------------------

                            "replay_target_subtask_id": (
                                replay_target_subtask_id
                            ),

                            "replay_target_subtask_description": (
                                replay_target_subtask_description
                            ),

                            "replay_target_specialist": (
                                replay_target_specialist
                            ),

                            "replay_target_span_name": (
                                replay_target_span_name
                            ),

                            "replay_target_span_kind": (
                                replay_target_span_kind
                            ),

                            "replay_only": (
                                replay_only
                            ),

                            # -----------------------------
                            # Replay override
                            # -----------------------------

                            "replay_input_override": (
                                replay_input_override
                            ),
                        }
                    )


            if (
                replay_only
                and result.get("plan") is not None
                and result["plan"].subtasks
            ):
                trace.attributes[
                    "replay_subtask_id"
                ] = str(
                    result["plan"].subtasks[0].id
                )

            # =================================================
            # 8. Result metadata
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
            # 9. HITL escalation
            # =================================================

            if (
                execution_status == "escalated"
                or human_escalation_required
            ):

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

                review_context = (
                    _build_hitl_review_context(
                        result,
                        proposed_action=proposed_action,
                        reasoning=(
                            escalation_reason
                        ),
                    )
                )

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

                await human_decision_repo.get_or_create_pending(
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

                _apply_trace_statuses(
                    trace=trace,
                    execution_status="escalated",
                    specialist_confidence=specialist_confidence,
                    confidence_threshold=confidence_threshold,
                    resume_subtask_id=resume_subtask_id,
                )

                await _persist_trace(
                    session=session,
                    trace=trace,
                    status="escalated",
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
            # 10. Rejected
            # =================================================

            if execution_status == "rejected":

                await execution_repo.update_status(
                    execution.id,
                    "rejected",
                )

                _apply_trace_statuses(
                    trace=trace,
                    execution_status="rejected",
                    specialist_confidence=specialist_confidence,
                    confidence_threshold=confidence_threshold,
                    resume_subtask_id=resume_subtask_id,
                )

                await _persist_trace(
                    session=session,
                    trace=trace,
                    status="rejected",
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
            # 11. Normal completion
            # =================================================

            await execution_repo.update_status(
                execution.id,
                execution_status,
            )

            _apply_trace_statuses(
                trace=trace,
                execution_status=execution_status,
                specialist_confidence=specialist_confidence,
                confidence_threshold=confidence_threshold,
                resume_subtask_id=resume_subtask_id,
            )

            await _persist_trace(
                session=session,
                trace=trace,
                status=execution_status,
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
            # =================================================
            # 12. Failure handling
            # =================================================

            await session.rollback()

            try:
                failed_execution = await execution_repo.get(
                    execution_uuid
                )

                if failed_execution is None:
                    await execution_repo.create(
                        task_id=task_uuid,
                        execution_id=execution_uuid,
                        status="failed",
                    )
                else:
                    await execution_repo.update_status(
                        execution_uuid,
                        "failed",
                    )

                _apply_trace_statuses(
                    trace=trace,
                    execution_status="failed",
                    specialist_confidence=None,
                    confidence_threshold=None,
                    resume_subtask_id=None,
                )

                await _persist_trace(
                    session=session,
                    trace=trace,
                    status="failed",
                )

                await session.commit()

            except Exception:
                await session.rollback()

            # Never replace the original workflow exception.
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
    context: dict | None = None,

    # ---------------------------------------------------------
    # Replay
    # ---------------------------------------------------------

    replay_source_execution_id: str | None = None,
    replay_source_span_id: str | None = None,
    replay_target_subtask_id: str | None = None,

    replay_target_subtask_description: str | None = None,
    replay_target_specialist: str | None = None,
    replay_target_span_name: str | None = None,
    replay_target_span_kind: str | None = None,

    replay_only: bool = False,

    replay_input_override=None,
    replay_source_subtask: dict | None = None,
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
            context=context,

            # -----------------------------
            # Replay source
            # -----------------------------

            replay_source_execution_id=(
                replay_source_execution_id
            ),

            replay_source_span_id=(
                replay_source_span_id
            ),

            replay_target_subtask_id=(
                replay_target_subtask_id
            ),

            # -----------------------------
            # Replay logical target
            # -----------------------------

            replay_target_subtask_description=(
                replay_target_subtask_description
            ),

            replay_target_specialist=(
                replay_target_specialist
            ),

            replay_target_span_name=(
                replay_target_span_name
            ),

            replay_target_span_kind=(
                replay_target_span_kind
            ),

            replay_only=(
                replay_only
            ),

            # -----------------------------
            # Replay override
            # -----------------------------

            replay_input_override=(
                replay_input_override
            ),

            replay_source_subtask=(
                replay_source_subtask
            ),
        )
    )