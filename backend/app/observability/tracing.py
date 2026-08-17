from __future__ import annotations

import contextvars
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


_MAX_SERIALIZED = 20_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_json(
    value: Any,
    *,
    limit: int = _MAX_SERIALIZED,
) -> str | None:
    """
    Serialize a value into bounded JSON text.

    Strings are intentionally JSON-encoded as well. For example:

        "hello" -> '"hello"'

    This keeps all recorded span inputs/prompts/raw responses
    consistently serialized and makes the trace payload unambiguous.
    """
    if value is None:
        return None

    try:
        text = json.dumps(
            value,
            default=str,
            ensure_ascii=False,
        )
    except Exception:
        try:
            text = json.dumps(
                repr(value),
                ensure_ascii=False,
            )
        except Exception:
            text = repr(value)

    if len(text) > limit:
        return text[:limit] + "...[truncated]"

    return text


@dataclass
class SpanRecord:
    span_id: str
    parent_span_id: str | None
    name: str
    kind: str
    execution_id: UUID

    started_at: datetime = field(
        default_factory=_utcnow,
    )

    ended_at: datetime | None = None
    duration_ms: float | None = None
    status: str = "running"
    error: str | None = None

    # Agent / workflow metadata
    agent: str | None = None
    specialist: str | None = None
    subtask_id: UUID | None = None

    # Tool / LLM metadata
    tool_name: str | None = None
    provider: str | None = None
    model: str | None = None

    # Quality metadata
    confidence: float | None = None

    # Serialized payloads
    input: str | None = None
    output: str | None = None
    prompt: str | None = None
    raw_response: str | None = None

    # Usage / cost metadata
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost: float | None = None

    # Arbitrary trace attributes
    attributes: dict[str, Any] = field(
        default_factory=dict,
    )
    
@dataclass
class SpanContext:
    record: SpanRecord
    otel_span: trace.Span

    _started: float = field(
        default_factory=time.perf_counter
    )

    def finish(
        self,
        *,
        status: str = "success",
        output: Any = None,
        error: Exception | str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        cost: float | None = None,
        confidence: float | None = None,
    ) -> None:
        """
        Finish the span exactly once.

        This method is intentionally idempotent because callers such as
        record_llm_usage() may finish the span before the surrounding
        context manager exits.
        """
        if self.record.ended_at is not None:
            return

        self.record.ended_at = _utcnow()

        self.record.duration_ms = (
            time.perf_counter() - self._started
        ) * 1000

        self.record.status = status

        if output is not None:
            self.record.output = _safe_json(output)

        if error is not None:
            self.record.error = str(error)

        if input_tokens is not None:
            self.record.input_tokens = input_tokens

        if output_tokens is not None:
            self.record.output_tokens = output_tokens

        if total_tokens is not None:
            self.record.total_tokens = total_tokens

        if cost is not None:
            self.record.cost = cost

        if confidence is not None:
            self.record.confidence = confidence

        # OpenTelemetry error handling.
        if error is not None or status == "failure":
            exception = (
                error
                if isinstance(error, Exception)
                else Exception(
                    str(error)
                    if error is not None
                    else "Span failed"
                )
            )

            try:
                self.otel_span.record_exception(
                    exception
                )
            except Exception:
                pass

            try:
                self.otel_span.set_status(
                    Status(
                        StatusCode.ERROR,
                        str(exception),
                    )
                )
            except Exception:
                pass

        else:
            try:
                self.otel_span.set_status(
                    Status(StatusCode.OK)
                )
            except Exception:
                pass

        # Copy custom attributes onto the OTel span.
        for key, value in self.record.attributes.items():
            try:
                if isinstance(
                    value,
                    (str, int, float, bool),
                ):
                    attribute_value = value
                else:
                    attribute_value = str(value)

                self.otel_span.set_attribute(
                    key,
                    attribute_value,
                )
            except Exception:
                # Observability should never break the actual workflow.
                pass

        try:
            self.otel_span.end()
        except Exception:
            # Again, tracing must never become a source of application
            # failure.
            pass


@dataclass
class ExecutionTrace:
    execution_id: UUID
    task_id: UUID | None = None
    user_id: str | None = None

    # Execution-level attributes.
    #
    # These are persisted to TraceModel.attributes and are used
    # by cross-execution analytics for metadata such as task_type.
    attributes: dict[str, Any] = field(
        default_factory=dict
    )

    trace_id: str = field(
        default_factory=lambda: uuid4().hex
    )

    spans: list[SpanRecord] = field(
        default_factory=list
    )

    started_at: datetime = field(
        default_factory=_utcnow
    )

    completed_at: datetime | None = None
    status: str = "running"

    started_at: datetime = field(
        default_factory=_utcnow
    )

    completed_at: datetime | None = None
    status: str = "running"

    def finish(
        self,
        status: str,
    ) -> None:
        self.status = status
        self.completed_at = _utcnow()

    @property
    def total_tokens(self) -> int:
        return sum(
            span.total_tokens or 0
            for span in self.spans
        )

    @property
    def total_cost(self) -> float:
        return sum(
            span.cost or 0.0
            for span in self.spans
        )

    @property
    def total_tool_calls(self) -> int:
        return sum(
            1
            for span in self.spans
            if span.kind == "tool"
        )

    @property
    def wall_clock_ms(self) -> float | None:
        if self.completed_at is None:
            return None

        return (
            self.completed_at - self.started_at
        ).total_seconds() * 1000


_current_trace: contextvars.ContextVar[
    ExecutionTrace | None
] = contextvars.ContextVar(
    "agentflow_current_trace",
    default=None,
)


_current_span: contextvars.ContextVar[
    SpanContext | None
] = contextvars.ContextVar(
    "agentflow_current_span",
    default=None,
)


tracer = trace.get_tracer("agentflow")


def get_current_trace() -> ExecutionTrace | None:
    return _current_trace.get()


def get_current_span() -> SpanContext | None:
    return _current_span.get()


@contextmanager
def use_trace(
    execution_trace: ExecutionTrace,
) -> Iterator[ExecutionTrace]:
    """
    Make an ExecutionTrace available to all nested operations
    within the current context.
    """
    token = _current_trace.set(
        execution_trace
    )

    try:
        yield execution_trace
    finally:
        _current_trace.reset(token)


def start_trace(
    *,
    execution_id: UUID,
    task_id: UUID | None = None,
    user_id: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> ExecutionTrace:
    """
    Create a new execution trace.

    Execution-level attributes are persisted with the trace and are
    available to cross-execution analytics.

    The trace is not automatically registered as the current trace.
    Use:

        with use_trace(trace):
            ...

    around the execution.
    """
    return ExecutionTrace(
        execution_id=execution_id,
        task_id=task_id,
        user_id=user_id,
        attributes=dict(attributes or {}),
    )

    
@contextmanager
def current_trace(
    *,
    name: str,
    kind: str,
    execution_id: UUID | None = None,
    **metadata: Any,
) -> Iterator[SpanContext | None]:
    """
    Create a child span inside the current execution trace.

    Parent-child relationships are maintained using a ContextVar,
    allowing nested workflow, agent, specialist, LLM, and tool spans.
    """
    execution_trace = get_current_trace()

    # If tracing is not active, behave as a no-op context manager.
    if execution_trace is None:
        yield None
        return

    parent = _current_span.get()

    resolved_execution_id = (
        execution_id
        or execution_trace.execution_id
    )

    record = SpanRecord(
        span_id=uuid4().hex,
        parent_span_id=(
            parent.record.span_id
            if parent is not None
            else None
        ),
        name=name,
        kind=kind,
        execution_id=resolved_execution_id,
        started_at=_utcnow(),
    )

    # Known first-class metadata fields.
    known_metadata_keys = {
        "agent",
        "specialist",
        "subtask_id",
        "tool_name",
        "provider",
        "model",
        "confidence",
    }

    for key in known_metadata_keys:
        value = metadata.get(key)

        if value is None:
            continue

        if key == "subtask_id":
            try:
                value = UUID(str(value))
            except (
                TypeError,
                ValueError,
            ):
                pass

        setattr(
            record,
            key,
            value,
        )

    # Everything else becomes a custom attribute.
    for key, value in metadata.items():
        if key not in known_metadata_keys:
            if value is not None:
                record.attributes[key] = value

    # Store the span in the execution trace before entering it.
    execution_trace.spans.append(record)

    # OpenTelemetry attributes.
    otel_attributes: dict[str, Any] = {
        "agentflow.execution_id": str(
            resolved_execution_id
        ),
        "agentflow.trace_id": (
            execution_trace.trace_id
        ),
        "agentflow.span_id": record.span_id,
        "agentflow.kind": kind,
        "agentflow.name": name,
    }

    for key, value in metadata.items():
        if value is not None:
            otel_attributes[
                f"agentflow.{key}"
            ] = str(value)

    try:
        otel_span = tracer.start_span(
            name,
            attributes=otel_attributes,
        )
    except Exception:
        # The tracing implementation should not prevent the
        # actual agent workflow from executing.
        otel_span = trace.INVALID_SPAN

    context = SpanContext(
        record=record,
        otel_span=otel_span,
    )

    token = _current_span.set(context)

    try:
        yield context

    except Exception as exc:
        context.finish(
            status="failure",
            error=exc,
        )
        raise

    else:
        context.finish()

    finally:
        _current_span.reset(token)


def annotate_current_span(
    *,
    input_value: Any = None,
    prompt: str | None = None,
    raw_response: Any = None,
    **attributes: Any,
) -> None:
    """
    Attach inputs, prompts, raw responses, and arbitrary metadata
    to the currently active span.
    """
    span = _current_span.get()

    if span is None:
        return

    if input_value is not None:
        span.record.input = _safe_json(
            input_value
        )

    if prompt is not None:
        span.record.prompt = _safe_json(
            prompt
        )

    if raw_response is not None:
        span.record.raw_response = _safe_json(
            raw_response
        )

    for key, value in attributes.items():
        if value is not None:
            span.record.attributes[key] = value


def record_llm_usage(
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    cost: float | None = None,
) -> None:
    """
    Record LLM token/cost information on the current span.

    This also finishes the span immediately.

    The operation is idempotent because SpanContext.finish()
    safely ignores subsequent finish attempts from the surrounding
    current_trace() context manager.
    """
    span = _current_span.get()

    if span is None:
        return

    span.finish(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost=cost,
    )