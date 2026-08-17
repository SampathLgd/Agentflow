from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.db.repositories.execution import (
    ExecutionRepository,
)
from app.db.repositories.task import TaskRepository
from app.db.repositories.subtask import SubTaskRepository
from app.db.session import AsyncSessionLocal
from app.observability.analytics import (
    get_observability_analytics,
)
from app.observability.models import (
    SpanModel,
    TraceModel,
)
from app.observability.repository import TraceRepository
from app.schemas.replay import (
    ReplayComparisonResponse,
    ReplayExecutionRequest,
    ReplayExecutionResponse,
)
from app.tasks.execution import (
    execute_agentflow_task,
)


router = APIRouter(
    prefix="/api/executions",
    tags=["trace"],
)


# ============================================================
# Execution traces
# ============================================================


@router.get(
    "/traces",
)
async def list_execution_traces(
    limit: int = 25,
) -> list[dict[str, object]]:
    """
    Return the most recent persisted execution traces.
    """

    if limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be greater than zero.",
        )

    limit = min(limit, 100)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TraceModel)
            .order_by(
                TraceModel.started_at.desc()
            )
            .limit(limit)
        )

        traces = list(
            result.scalars().all()
        )

    return [
        {
            "trace_id": trace.trace_id,
            "execution_id": str(
                trace.execution_id
            ),
            "task_id": (
                str(trace.task_id)
                if trace.task_id
                else None
            ),
            "user_id": trace.user_id,
            "status": trace.status,
            "started_at": trace.started_at,
            "completed_at": trace.completed_at,
            "wall_clock_ms": trace.wall_clock_ms,
            "total_input_tokens": (
                trace.total_input_tokens
            ),
            "total_output_tokens": (
                trace.total_output_tokens
            ),
            "total_tokens": trace.total_tokens,
            "total_tool_calls": (
                trace.total_tool_calls
            ),
            "total_cost": trace.total_cost,
        }
        for trace in traces
    ]


# ============================================================
# Observability analytics
# ============================================================


@router.get(
    "/analytics",
)
async def get_execution_analytics() -> dict[str, object]:
    """
    Return cross-execution observability analytics.

    Covers Phase 4 cost/performance tracking:

    - cost by task type
    - most expensive agents
    - model/provider usage
    - tool usage patterns
    - escalation trends
    - token usage
    - wall-clock latency
    - human-review time
    """

    async with AsyncSessionLocal() as session:
        return await get_observability_analytics(
            session
        )


# ============================================================
# Replay
# ============================================================


@router.post(
    "/replay",
    response_model=ReplayExecutionResponse,
)
async def replay_execution(
    payload: ReplayExecutionRequest,
) -> ReplayExecutionResponse:
    """
    Create a new execution by replaying a historical execution.

    The original execution and trace are never modified.

    When source_span_id is provided, the replay is a selected-span
    replay:

        original execution
            ↓
        selected specialist span
            ↓
        persisted source SubTask definition
            ↓
        new replay execution
            ↓
        replay_only=True
            ↓
        selected specialist only

    The replayed specialist receives replay_input_override when supplied.
    """

    source_execution_id = (
        payload.source_execution_id
    )

    async with AsyncSessionLocal() as session:

        execution_repo = ExecutionRepository(
            session
        )

        task_repo = TaskRepository(
            session
        )

        trace_repo = TraceRepository(
            session
        )

        # ====================================================
        # 1. Load source execution
        # ====================================================

        source_execution = (
            await execution_repo.get(
                source_execution_id
            )
        )

        if source_execution is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source execution not found.",
            )

        # ====================================================
        # 2. Load source task
        # ====================================================

        source_task = (
            source_execution.task
        )

        if source_task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source task not found.",
            )

        # ====================================================
        # 3. Load source trace
        # ====================================================

        source_trace = (
            await trace_repo.get_by_execution(
                source_execution_id
            )
        )

        if source_trace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source execution trace not found.",
            )

        # ====================================================
        # 4. Resolve selected source span
        # ====================================================

        source_span = None

        if payload.source_span_id:

            spans = await trace_repo.get_spans(
                source_trace.trace_id
            )

            source_span = next(
                (
                    span
                    for span in spans
                    if span.span_id
                    == payload.source_span_id
                ),
                None,
            )

            if source_span is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Source span not found.",
                )

            # Selected-span replay is intentionally limited to
            # specialist spans because only specialist spans carry
            # the persisted logical SubTask required to execute the
            # selected step in isolation.
            span_name = (
                (source_span.name or "")
                .strip()
                .lower()
            )
            span_kind = (
                (source_span.kind or "")
                .strip()
                .lower()
            )

            if (
                source_span.subtask_id is None
                or (
                    span_name != "specialist"
                    and not span_name.startswith("specialist")
                    and span_kind != "specialist"
                )
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Selected span is not replayable. "
                        "Select a persisted specialist span "
                        "with a subtask_id."
                    ),
                )

        # ====================================================
        # 5. Resolve source SubTask definition
        #
        # Selected-span replay must reuse the persisted logical
        # SubTask rather than asking the supervisor to generate
        # a potentially different plan.
        # ====================================================

        replay_source_subtask = None

        replay_target_subtask_id = None

        if source_span is not None:
            if source_span.subtask_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Selected replay span does not reference "
                        "a subtask."
                    ),
                )

            replay_target_subtask_id = (
                str(source_span.subtask_id)
            )

            # ------------------------------------------------
            # Load the persisted SubTask directly.
            #
            # Do not access async SQLAlchemy relationships here.
            # A lazy relationship can trigger MissingGreenlet in
            # an async FastAPI request. The repository performs an
            # explicit SELECT and is therefore deterministic.
            # ------------------------------------------------

            subtask_repo = SubTaskRepository(
                session
            )

            source_subtask = await subtask_repo.get(
                source_span.subtask_id
            )

            if source_subtask is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        "Selected replay span references a "
                        "subtask that could not be found."
                    ),
                )

            assigned_specialist = getattr(
                source_subtask,
                "assigned_specialist",
                None,
            )

            if assigned_specialist is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Source replay subtask is missing "
                        "assigned_specialist."
                    ),
                )

            specialist_value = getattr(
                assigned_specialist,
                "value",
                str(assigned_specialist),
            )

            estimated_complexity = getattr(
                source_subtask,
                "estimated_complexity",
                None,
            )

            if estimated_complexity is not None:
                estimated_complexity = getattr(
                    estimated_complexity,
                    "value",
                    str(
                        estimated_complexity
                    ),
                )

            replay_source_subtask = {
                "description": (
                    source_subtask.description
                ),

                "assigned_specialist": (
                    specialist_value
                ),

                "required_inputs": list(
                    source_subtask.required_inputs
                    or []
                ),

                "expected_output": (
                    source_subtask.expected_output
                ),

                "estimated_complexity": (
                    estimated_complexity
                ),
            }

        # ====================================================
        # 6. Create new replay task/execution
        # ====================================================

        replay_task_id = uuid4()
        replay_execution_id = uuid4()

        replay_description = (
            payload.description_override
            or source_task.description
        )

        replay_task = await task_repo.create(
            task_id=replay_task_id,
            user_id=source_task.user_id,
            description=replay_description,
        )

        await execution_repo.create(
            task_id=replay_task.id,
            execution_id=replay_execution_id,
            status="planned",
        )

        await session.commit()

        # ====================================================
        # 7. Determine logical replay selectors
        # ====================================================

        replay_target_subtask_description = None
        replay_target_specialist = None
        replay_target_span_name = None
        replay_target_span_kind = None

        if replay_source_subtask is not None:

            replay_target_subtask_description = (
                replay_source_subtask[
                    "description"
                ]
            )

            replay_target_specialist = (
                replay_source_subtask[
                    "assigned_specialist"
                ]
            )

            # A selected source span is expected to represent
            # the specialist operation that should be replayed.
            replay_target_span_name = "specialist"
            replay_target_span_kind = "specialist"

        # ====================================================
        # 8. Activate selected-span replay
        # ====================================================

        replay_only = (
            replay_target_subtask_id is not None
        )

        # ====================================================
        # 9. Queue Celery execution
        # ====================================================

        celery_result = (
            execute_agentflow_task.delay(
                task_id=str(
                    replay_task.id
                ),

                execution_id=str(
                    replay_execution_id
                ),

                user_id=str(
                    source_task.user_id
                ),

                description=replay_description,

                # --------------------------------------------
                # Replay source
                # --------------------------------------------

                replay_source_execution_id=(
                    str(
                        source_execution_id
                    )
                ),

                replay_source_span_id=(
                    payload.source_span_id
                ),

                # --------------------------------------------
                # Replay target
                # --------------------------------------------

                replay_target_subtask_id=(
                    replay_target_subtask_id
                ),

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

                # --------------------------------------------
                # Selected-span replay
                # --------------------------------------------

                replay_only=replay_only,

                replay_source_subtask=(
                    replay_source_subtask
                ),

                # --------------------------------------------
                # Optional input override
                # --------------------------------------------

                replay_input_override=(
                    payload.input_override
                ),
            )
        )

    # ========================================================
    # 10. Response
    # ========================================================

    return ReplayExecutionResponse(
        source_execution_id=(
            source_execution_id
        ),

        source_trace_id=(
            source_trace.trace_id
        ),

        replay_task_id=(
            replay_task_id
        ),

        replay_execution_id=(
            replay_execution_id
        ),

        source_span_id=(
            payload.source_span_id
        ),

        applied_subtask_id=(
            UUID(
                replay_target_subtask_id
            )
            if replay_target_subtask_id
            else None
        ),

        status="queued",

        celery_task_id=(
            celery_result.id
        ),
    )


# ============================================================
# Replay comparison helpers
# ============================================================


_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}\b"
)


_VOLATILE_KEYS = {
    "execution_id",
    "task_id",
    "span_id",
    "parent_span_id",
    "subtask_id",
    "replay_source_execution_id",
    "replay_source_span_id",
    "replay_target_subtask_id",
    "celery_task_id",
}


def _normalize_execution_status(
    value: str | None,
) -> str:
    """Normalize equivalent runtime status spellings."""

    normalized = (
        value or ""
    ).strip().lower()

    aliases = {
        "success": "completed",
        "completed": "completed",
        "failure": "failed",
        "failed": "failed",
        "error": "failed",
        "human_review": "escalated",
        "escalated": "escalated",
        "running": "running",
        "pending": "running",
        "planned": "running",
        "warning": "warning",
    }

    return aliases.get(
        normalized,
        normalized,
    )


def _normalize_comparable_value(
    value: Any,
) -> Any:
    """
    Remove runtime-only UUID noise from structured payloads.

    A replay creates new execution/task/subtask/span UUIDs.
    Those identifiers must not make otherwise identical
    inputs/outputs appear changed.
    """

    if isinstance(
        value,
        dict,
    ):
        return {
            key: (
                "<runtime-id>"
                if key in _VOLATILE_KEYS
                else _normalize_comparable_value(
                    item
                )
            )
            for key, item in sorted(
                value.items(),
                key=lambda item: str(
                    item[0]
                ),
            )
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            _normalize_comparable_value(
                item
            )
            for item in value
        ]

    if isinstance(
        value,
        str,
    ):
        try:
            parsed = json.loads(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return _UUID_RE.sub(
                "<runtime-uuid>",
                value,
            )

        return _normalize_comparable_value(
            parsed
        )

    return value


def _comparison_values_equal(
    field_name: str,
    original_value: Any,
    replay_value: Any,
) -> bool:

    if field_name == "status":
        return (
            _normalize_execution_status(
                str(original_value)
                if original_value is not None
                else None
            )
            == _normalize_execution_status(
                str(replay_value)
                if replay_value is not None
                else None
            )
        )

    if field_name in {
        "input",
        "output",
    }:
        return (
            _normalize_comparable_value(
                original_value
            )
            == _normalize_comparable_value(
                replay_value
            )
        )

    if field_name == "duration_ms":

        if (
            original_value is None
            or replay_value is None
        ):
            return (
                original_value
                == replay_value
            )

        try:
            original_number = float(
                original_value
            )

            replay_number = float(
                replay_value
            )

        except (
            TypeError,
            ValueError,
        ):
            return (
                original_value
                == replay_value
            )

        absolute_delta = abs(
            replay_number
            - original_number
        )

        tolerance = max(
            5.0,
            abs(original_number)
            * 0.01,
        )

        return (
            absolute_delta
            <= tolerance
        )

    if field_name == "cost":

        if (
            original_value is None
            or replay_value is None
        ):
            return (
                original_value
                == replay_value
            )

        try:
            return (
                abs(
                    float(
                        replay_value
                    )
                    - float(
                        original_value
                    )
                )
                <= 1e-8
            )

        except (
            TypeError,
            ValueError,
        ):
            return (
                original_value
                == replay_value
            )

    return (
        original_value
        == replay_value
    )


def _span_identity(
    span: SpanModel,
) -> tuple[str, str, str, str, str]:
    """
    Stable logical identity for replay comparison.

    Runtime UUIDs are intentionally excluded. Agent/specialist
    metadata is included so same-named nodes owned by different
    agents are not paired.
    """

    return (
        (
            span.kind
            or ""
        ).strip(),

        (
            span.name
            or ""
        ).strip(),

        (
            span.agent
            or ""
        ).strip(),

        (
            span.specialist
            or ""
        ).strip(),

        (
            span.tool_name
            or ""
        ).strip(),
    )


def _span_display_key(
    span: SpanModel,
    occurrence: int,
) -> str:

    (
        kind,
        name,
        agent,
        specialist,
        tool_name,
    ) = _span_identity(
        span
    )

    return "|".join(
        [
            kind,
            name,
            agent,
            specialist,
            tool_name,
            f"#{occurrence}",
        ]
    )


def _span_snapshot(
    span: SpanModel,
) -> dict[str, Any]:

    return {
        "span_id": span.span_id,

        "name": span.name,

        "kind": span.kind,

        "status": span.status,

        "agent": span.agent,

        "specialist": span.specialist,

        "subtask_id": (
            str(span.subtask_id)
            if span.subtask_id
            else None
        ),

        "tool_name": span.tool_name,

        "provider": span.provider,

        "model": span.model,

        "confidence": span.confidence,

        "duration_ms": span.duration_ms,

        "input_tokens": (
            span.input_tokens
        ),

        "output_tokens": (
            span.output_tokens
        ),

        "total_tokens": (
            span.total_tokens
        ),

        "cost": span.cost,

        "input": span.input,

        "output": span.output,

        "prompt": span.prompt,

        "raw_response": (
            span.raw_response
        ),

        "error": span.error,
    }


def _compare_spans(
    original_spans: list[SpanModel],
    replay_spans: list[SpanModel],
    replay_status: str | None,
) -> list[dict[str, Any]]:
    """
    Compare spans using logical identity rather than runtime UUIDs.

    Missing original spans are classified as:

      * not_reached
          replay terminated before they could execute

      * removed
          replay completed but the logical span disappeared

    This prevents a failed replay from incorrectly reporting
    every downstream original span as "removed".
    """

    original_groups: dict[
        tuple[str, str, str, str, str],
        list[tuple[int, SpanModel]],
    ] = defaultdict(
        list
    )

    replay_groups: dict[
        tuple[str, str, str, str, str],
        list[tuple[int, SpanModel]],
    ] = defaultdict(
        list
    )

    for index, span in enumerate(
        original_spans
    ):
        original_groups[
            _span_identity(span)
        ].append(
            (
                index,
                span,
            )
        )

    for index, span in enumerate(
        replay_spans
    ):
        replay_groups[
            _span_identity(span)
        ].append(
            (
                index,
                span,
            )
        )

    differences: list[
        tuple[
            int,
            dict[str, Any],
        ]
    ] = []

    replay_terminated_early = (
        _normalize_execution_status(
            replay_status
        )
        in {
            "failed",
            "escalated",
        }
    )

    fields_to_compare = (
        "status",
        "duration_ms",
        "total_tokens",
        "cost",
        "input",
        "output",
        "confidence",
        "model",
        "provider",
        "error",
        "input_tokens",
        "output_tokens",
    )

    all_keys = (
        set(original_groups)
        | set(replay_groups)
    )

    for identity in all_keys:

        original_items = (
            original_groups.get(
                identity,
                [],
            )
        )

        replay_items = (
            replay_groups.get(
                identity,
                [],
            )
        )

        count = max(
            len(original_items),
            len(replay_items),
        )

        for occurrence_index in range(
            count
        ):

            original_entry = (
                original_items[
                    occurrence_index
                ]
                if occurrence_index
                < len(
                    original_items
                )
                else None
            )

            replay_entry = (
                replay_items[
                    occurrence_index
                ]
                if occurrence_index
                < len(
                    replay_items
                )
                else None
            )

            occurrence = (
                occurrence_index + 1
            )

            original = (
                original_entry[1]
                if original_entry
                is not None
                else None
            )

            replay = (
                replay_entry[1]
                if replay_entry
                is not None
                else None
            )

            original_position = (
                original_entry[0]
                if original_entry
                is not None
                else None
            )

            replay_position = (
                replay_entry[0]
                if replay_entry
                is not None
                else None
            )

            sort_position = min(
                position
                for position in (
                    original_position,
                    replay_position,
                )
                if position is not None
            )

            if (
                original is None
                and replay is not None
            ):
                differences.append(
                    (
                        sort_position,
                        {
                            "change": "added",

                            "key": (
                                _span_display_key(
                                    replay,
                                    occurrence,
                                )
                            ),

                            "original": None,

                            "replay": (
                                _span_snapshot(
                                    replay
                                )
                            ),

                            "fields": [],

                            "field_diffs": {},
                        },
                    )
                )

                continue

            if (
                replay is None
                and original is not None
            ):
                differences.append(
                    (
                        sort_position,
                        {
                            "change": (
                                "not_reached"
                                if replay_terminated_early
                                else "removed"
                            ),

                            "key": (
                                _span_display_key(
                                    original,
                                    occurrence,
                                )
                            ),

                            "original": (
                                _span_snapshot(
                                    original
                                )
                            ),

                            "replay": None,

                            "fields": [],

                            "field_diffs": {},
                        },
                    )
                )

                continue

            if (
                original is None
                or replay is None
            ):
                continue

            field_diffs: dict[
                str,
                dict[str, Any],
            ] = {}

            for field_name in (
                fields_to_compare
            ):

                original_value = getattr(
                    original,
                    field_name,
                    None,
                )

                replay_value = getattr(
                    replay,
                    field_name,
                    None,
                )

                if not _comparison_values_equal(
                    field_name,
                    original_value,
                    replay_value,
                ):
                    field_diffs[
                        field_name
                    ] = {
                        "original": (
                            original_value
                        ),
                        "replay": (
                            replay_value
                        ),
                    }

            differences.append(
                (
                    sort_position,
                    {
                        "change": (
                            "changed"
                            if field_diffs
                            else "unchanged"
                        ),

                        "key": (
                            _span_display_key(
                                original,
                                occurrence,
                            )
                        ),

                        "original": (
                            _span_snapshot(
                                original
                            )
                        ),

                        "replay": (
                            _span_snapshot(
                                replay
                            )
                        ),

                        "fields": list(
                            field_diffs.keys()
                        ),

                        "field_diffs": (
                            field_diffs
                        ),
                    },
                )
            )

    differences.sort(
        key=lambda item: item[0]
    )

    return [
        difference
        for _, difference in differences
    ]


# ============================================================
# Replay comparison endpoint
# ============================================================


@router.get(
    "/replay/compare",
    response_model=ReplayComparisonResponse,
)
async def compare_replay(
    original_execution_id: UUID,
    replay_execution_id: UUID,
) -> ReplayComparisonResponse:

    async with AsyncSessionLocal() as session:

        repository = TraceRepository(
            session
        )

        original_trace = (
            await repository.get_by_execution(
                original_execution_id
            )
        )

        replay_trace = (
            await repository.get_by_execution(
                replay_execution_id
            )
        )

        if original_trace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original trace not found.",
            )

        if replay_trace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Replay trace not found yet.",
            )

        original_spans = (
            await repository.get_spans(
                original_trace.trace_id
            )
        )

        replay_spans = (
            await repository.get_spans(
                replay_trace.trace_id
            )
        )

    original = {
        "status": (
            original_trace.status
        ),

        "wall_clock_ms": (
            original_trace.wall_clock_ms
        ),

        "total_tokens": (
            original_trace.total_tokens
        ),

        "total_tool_calls": (
            original_trace.total_tool_calls
        ),

        "total_cost": (
            original_trace.total_cost
        ),
    }

    replay = {
        "status": (
            replay_trace.status
        ),

        "wall_clock_ms": (
            replay_trace.wall_clock_ms
        ),

        "total_tokens": (
            replay_trace.total_tokens
        ),

        "total_tool_calls": (
            replay_trace.total_tool_calls
        ),

        "total_cost": (
            replay_trace.total_cost
        ),
    }

    changes = {
        "status_changed": (
            _normalize_execution_status(
                original_trace.status
            )
            != _normalize_execution_status(
                replay_trace.status
            )
        ),

        "latency_delta_ms": (
            (
                replay_trace.wall_clock_ms
                or 0
            )
            - (
                original_trace.wall_clock_ms
                or 0
            )
        ),

        "token_delta": (
            (
                replay_trace.total_tokens
                or 0
            )
            - (
                original_trace.total_tokens
                or 0
            )
        ),

        "tool_call_delta": (
            (
                replay_trace.total_tool_calls
                or 0
            )
            - (
                original_trace.total_tool_calls
                or 0
            )
        ),

        "cost_delta": (
            (
                replay_trace.total_cost
                or 0
            )
            - (
                original_trace.total_cost
                or 0
            )
        ),

        "span_count_delta": (
            len(replay_spans)
            - len(original_spans)
        ),
    }

    return ReplayComparisonResponse(
        original_execution_id=(
            original_execution_id
        ),

        replay_execution_id=(
            replay_execution_id
        ),

        original=original,

        replay=replay,

        changes=changes,

        span_differences=_compare_spans(
            original_spans,
            replay_spans,
            replay_trace.status,
        ),
    )


# ============================================================
# Complete execution trace
# ============================================================


@router.get(
    "/{execution_id}/trace",
)
async def get_execution_trace(
    execution_id: UUID,
) -> dict[str, object]:
    """
    Return one complete execution trace.
    """

    async with AsyncSessionLocal() as session:

        repository = TraceRepository(
            session
        )

        trace = (
            await repository.get_by_execution(
                execution_id
            )
        )

        if trace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution trace not found.",
            )

        spans = await repository.get_spans(
            trace.trace_id
        )

    return {
        "trace_id": trace.trace_id,

        "execution_id": str(
            trace.execution_id
        ),

        "task_id": (
            str(trace.task_id)
            if trace.task_id
            else None
        ),

        "user_id": trace.user_id,

        "status": trace.status,

        "started_at": trace.started_at,

        "completed_at": trace.completed_at,

        "wall_clock_ms": (
            trace.wall_clock_ms
        ),

        "total_input_tokens": (
            trace.total_input_tokens
        ),

        "total_output_tokens": (
            trace.total_output_tokens
        ),

        "total_tokens": (
            trace.total_tokens
        ),

        "total_tool_calls": (
            trace.total_tool_calls
        ),

        "total_cost": (
            trace.total_cost
        ),

        "attributes": (
            trace.attributes or {}
        ),

        "spans": [
            {
                "span_id": span.span_id,

                "parent_span_id": (
                    span.parent_span_id
                ),

                "execution_id": str(
                    span.execution_id
                ),

                "name": span.name,

                "kind": span.kind,

                "status": span.status,

                "agent": span.agent,

                "specialist": span.specialist,

                "subtask_id": (
                    str(span.subtask_id)
                    if span.subtask_id
                    else None
                ),

                "tool_name": span.tool_name,

                "provider": span.provider,

                "model": span.model,

                "confidence": span.confidence,

                "started_at": span.started_at,

                "ended_at": span.ended_at,

                "duration_ms": (
                    span.duration_ms
                ),

                "input": span.input,

                "output": span.output,

                "prompt": span.prompt,

                "raw_response": (
                    span.raw_response
                ),

                "error": span.error,

                "input_tokens": (
                    span.input_tokens
                ),

                "output_tokens": (
                    span.output_tokens
                ),

                "total_tokens": (
                    span.total_tokens
                ),

                "cost": span.cost,

                "attributes": (
                    span.attributes or {}
                ),
            }
            for span in spans
        ],
    }


# ============================================================
# Execution trace spans
# ============================================================


@router.get(
    "/{execution_id}/trace/spans",
)
async def get_execution_trace_spans(
    execution_id: UUID,
) -> dict[str, object]:
    """
    Return only the spans for one execution.
    """

    async with AsyncSessionLocal() as session:

        repository = TraceRepository(
            session
        )

        trace = (
            await repository.get_by_execution(
                execution_id
            )
        )

        if trace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution trace not found.",
            )

        spans = await repository.get_spans(
            trace.trace_id
        )

    return {
        "trace_id": trace.trace_id,

        "execution_id": str(
            execution_id
        ),

        "spans": [
            {
                "span_id": span.span_id,

                "parent_span_id": (
                    span.parent_span_id
                ),

                "execution_id": str(
                    span.execution_id
                ),

                "name": span.name,

                "kind": span.kind,

                "status": span.status,

                "agent": span.agent,

                "specialist": span.specialist,

                "subtask_id": (
                    str(span.subtask_id)
                    if span.subtask_id
                    else None
                ),

                "tool_name": span.tool_name,

                "provider": span.provider,

                "model": span.model,

                "confidence": span.confidence,

                "started_at": span.started_at,

                "ended_at": span.ended_at,

                "duration_ms": (
                    span.duration_ms
                ),

                "input": span.input,

                "output": span.output,

                "prompt": span.prompt,

                "raw_response": (
                    span.raw_response
                ),

                "error": span.error,

                "input_tokens": (
                    span.input_tokens
                ),

                "output_tokens": (
                    span.output_tokens
                ),

                "total_tokens": (
                    span.total_tokens
                ),

                "cost": span.cost,

                "attributes": (
                    span.attributes or {}
                ),
            }
            for span in spans
        ],
    }