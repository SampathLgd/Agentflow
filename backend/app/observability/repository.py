from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.models import SpanModel, TraceModel
from app.observability.tracing import (
    ExecutionTrace,
    SpanRecord,
)


def _json_safe(value):
    """
    Convert arbitrary trace attributes into values supported by
    SQLAlchemy's PostgreSQL JSON column.

    Observability must never fail because an attribute is not JSON
    serializable.
    """

    if value is None:
        return None

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Enum):
        return _json_safe(value.value)

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            _json_safe(item)
            for item in value
        ]

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


class TraceRepository:
    """
    Persistence adapter for AgentFlow execution traces.

    A trace belongs to one execution.

    Saving is snapshot-based:

        ExecutionTrace -> TraceModel + SpanModel rows

    This supports:

    - normal execution
    - escalation
    - retry
    - HITL resume
    - terminal failure
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def save(
        self,
        execution_trace: ExecutionTrace,
    ) -> TraceModel:
        """
        Persist the complete execution trace.
        """

        existing = await self.get_by_execution(
            execution_trace.execution_id
        )

        total_input_tokens = sum(
            span.input_tokens or 0
            for span in execution_trace.spans
        )

        total_output_tokens = sum(
            span.output_tokens or 0
            for span in execution_trace.spans
        )

        total_tokens = sum(
            span.total_tokens or 0
            for span in execution_trace.spans
        )

        total_tool_calls = sum(
            1
            for span in execution_trace.spans
            if span.kind == "tool"
        )

        total_cost = sum(
            span.cost or 0.0
            for span in execution_trace.spans
        )

        trace_attributes = _json_safe(
            execution_trace.attributes
        )

        if existing is not None:
            old_trace_id = existing.trace_id

            existing.trace_id = (
                execution_trace.trace_id
            )
            existing.task_id = (
                execution_trace.task_id
            )
            existing.user_id = (
                execution_trace.user_id
            )
            existing.status = (
                execution_trace.status
            )
            existing.started_at = (
                execution_trace.started_at
            )
            existing.completed_at = (
                execution_trace.completed_at
            )
            existing.wall_clock_ms = (
                execution_trace.wall_clock_ms
            )

            existing.total_input_tokens = (
                total_input_tokens
            )
            existing.total_output_tokens = (
                total_output_tokens
            )
            existing.total_tokens = (
                total_tokens
            )
            existing.total_tool_calls = (
                total_tool_calls
            )
            existing.total_cost = (
                total_cost
            )

            # Important for Phase 4 analytics:
            # preserve execution-level attributes such as task_type.
            existing.attributes = trace_attributes

            trace_model = existing

            await self.session.execute(
                delete(SpanModel).where(
                    SpanModel.trace_id == old_trace_id
                )
            )

        else:
            trace_model = TraceModel(
                execution_id=(
                    execution_trace.execution_id
                ),
                task_id=(
                    execution_trace.task_id
                ),
                user_id=(
                    execution_trace.user_id
                ),
                trace_id=(
                    execution_trace.trace_id
                ),
                status=(
                    execution_trace.status
                ),
                started_at=(
                    execution_trace.started_at
                ),
                completed_at=(
                    execution_trace.completed_at
                ),
                wall_clock_ms=(
                    execution_trace.wall_clock_ms
                ),
                total_input_tokens=(
                    total_input_tokens
                ),
                total_output_tokens=(
                    total_output_tokens
                ),
                total_tokens=(
                    total_tokens
                ),
                total_tool_calls=(
                    total_tool_calls
                ),
                total_cost=(
                    total_cost
                ),
                attributes=trace_attributes,
            )

            self.session.add(trace_model)

        for span in execution_trace.spans:
            self.session.add(
                SpanModel(
                    trace_id=(
                        execution_trace.trace_id
                    ),
                    span_id=span.span_id,
                    parent_span_id=(
                        span.parent_span_id
                    ),
                    execution_id=(
                        span.execution_id
                    ),
                    name=span.name,
                    kind=span.kind,
                    status=span.status,
                    agent=span.agent,
                    specialist=span.specialist,
                    subtask_id=span.subtask_id,
                    tool_name=span.tool_name,
                    provider=span.provider,
                    model=span.model,
                    confidence=span.confidence,
                    started_at=span.started_at,
                    ended_at=span.ended_at,
                    duration_ms=span.duration_ms,
                    input=span.input,
                    output=span.output,
                    prompt=span.prompt,
                    raw_response=span.raw_response,
                    error=span.error,
                    input_tokens=span.input_tokens,
                    output_tokens=span.output_tokens,
                    total_tokens=span.total_tokens,
                    cost=span.cost,
                    attributes=_json_safe(
                        span.attributes
                    ),
                )
            )

        await self.session.flush()

        return trace_model

    async def get_by_execution(
        self,
        execution_id: UUID,
    ) -> TraceModel | None:
        result = await self.session.execute(
            select(TraceModel).where(
                TraceModel.execution_id
                == execution_id
            )
        )

        return result.scalar_one_or_none()

    async def get_by_trace_id(
        self,
        trace_id: str,
    ) -> TraceModel | None:
        result = await self.session.execute(
            select(TraceModel).where(
                TraceModel.trace_id == trace_id
            )
        )

        return result.scalar_one_or_none()

    async def get_spans(
        self,
        trace_id: str,
    ) -> list[SpanModel]:
        result = await self.session.execute(
            select(SpanModel)
            .where(
                SpanModel.trace_id == trace_id
            )
            .order_by(
                SpanModel.started_at.asc()
            )
        )

        return list(
            result.scalars().all()
        )

    async def load_execution_trace(
        self,
        execution_id: UUID,
    ) -> ExecutionTrace | None:
        """
        Reconstruct an ExecutionTrace from PostgreSQL.

        Used by HITL resume so the resumed execution continues
        the same durable trace.
        """

        trace_model = await self.get_by_execution(
            execution_id
        )

        if trace_model is None:
            return None

        span_models = await self.get_spans(
            trace_model.trace_id
        )

        execution_trace = ExecutionTrace(
            execution_id=(
                trace_model.execution_id
            ),
            task_id=trace_model.task_id,
            user_id=trace_model.user_id,
            trace_id=trace_model.trace_id,
            started_at=trace_model.started_at,
            completed_at=trace_model.completed_at,
            status=trace_model.status,
        )

        execution_trace.attributes = (
            trace_model.attributes or {}
        )

        execution_trace.spans = [
            self._span_record_from_model(
                span_model
            )
            for span_model in span_models
        ]

        return execution_trace

    @staticmethod
    def _span_record_from_model(
        span: SpanModel,
    ) -> SpanRecord:
        return SpanRecord(
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            name=span.name,
            kind=span.kind,
            execution_id=span.execution_id,
            started_at=span.started_at,
            ended_at=span.ended_at,
            duration_ms=span.duration_ms,
            status=span.status,
            error=span.error,
            agent=span.agent,
            specialist=span.specialist,
            subtask_id=span.subtask_id,
            tool_name=span.tool_name,
            provider=span.provider,
            model=span.model,
            confidence=span.confidence,
            input=span.input,
            output=span.output,
            prompt=span.prompt,
            raw_response=span.raw_response,
            input_tokens=span.input_tokens,
            output_tokens=span.output_tokens,
            total_tokens=span.total_tokens,
            cost=span.cost,
            attributes=_json_safe(
                span.attributes or {}
            ),
        )