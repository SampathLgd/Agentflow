from uuid import uuid4

from app.observability.tracing import (
    SpanRecord,
    start_trace,
)
from app.tasks.execution import _apply_trace_statuses


def test_execution_span_matches_escalated_execution_status():
    execution_id = uuid4()

    trace = start_trace(
        execution_id=execution_id,
        task_id=uuid4(),
        user_id="test-user",
    )

    trace.spans.append(
        SpanRecord(
            span_id=uuid4().hex,
            parent_span_id=None,
            name="execution",
            kind="workflow",
            execution_id=execution_id,
            started_at=trace.started_at,
        )
    )

    _apply_trace_statuses(
        trace=trace,
        execution_status="escalated",
        specialist_confidence=0.3,
        confidence_threshold=0.5,
        resume_subtask_id=None,
    )

    assert trace.spans[0].status == "escalated"
    assert (
        trace.spans[0].attributes["execution_status"]
        == "escalated"
    )


def test_low_confidence_specialist_is_warning():
    execution_id = uuid4()
    subtask_id = uuid4()

    trace = start_trace(
        execution_id=execution_id,
        task_id=uuid4(),
        user_id="test-user",
    )

    trace.spans.append(
        SpanRecord(
            span_id=uuid4().hex,
            parent_span_id=None,
            name="execution",
            kind="workflow",
            execution_id=execution_id,
            started_at=trace.started_at,
        )
    )

    trace.spans.append(
        SpanRecord(
            span_id=uuid4().hex,
            parent_span_id=trace.spans[0].span_id,
            name="specialist",
            kind="specialist",
            execution_id=execution_id,
            started_at=trace.started_at,
            subtask_id=subtask_id,
        )
    )

    _apply_trace_statuses(
        trace=trace,
        execution_status="escalated",
        specialist_confidence=0.3,
        confidence_threshold=0.5,
        resume_subtask_id=subtask_id,
    )

    specialist_span = trace.spans[1]

    assert specialist_span.status == "warning"
    assert specialist_span.confidence == 0.3
    assert (
        specialist_span.attributes[
            "confidence_threshold"
        ]
        == 0.5
    )


def test_high_confidence_specialist_remains_success():
    execution_id = uuid4()
    subtask_id = uuid4()

    trace = start_trace(
        execution_id=execution_id,
        task_id=uuid4(),
        user_id="test-user",
    )

    trace.spans.append(
        SpanRecord(
            span_id=uuid4().hex,
            parent_span_id=None,
            name="execution",
            kind="workflow",
            execution_id=execution_id,
            started_at=trace.started_at,
        )
    )

    trace.spans.append(
        SpanRecord(
            span_id=uuid4().hex,
            parent_span_id=trace.spans[0].span_id,
            name="specialist",
            kind="specialist",
            execution_id=execution_id,
            started_at=trace.started_at,
            subtask_id=subtask_id,
            status="success",
        )
    )

    _apply_trace_statuses(
        trace=trace,
        execution_status="completed",
        specialist_confidence=0.8,
        confidence_threshold=0.5,
        resume_subtask_id=subtask_id,
    )

    assert trace.spans[0].status == "completed"
    assert trace.spans[1].status == "success"