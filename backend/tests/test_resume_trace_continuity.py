from uuid import uuid4

import pytest

from app.observability.tracing import (
    ExecutionTrace,
    SpanRecord,
)


def test_resumed_trace_keeps_original_trace_id():
    execution_id = uuid4()
    task_id = uuid4()

    original_trace = ExecutionTrace(
        execution_id=execution_id,
        task_id=task_id,
        user_id="test-user",
    )

    original_trace_id = original_trace.trace_id

    original_trace.spans.append(
        SpanRecord(
            span_id=uuid4().hex,
            parent_span_id=None,
            name="execution",
            kind="workflow",
            execution_id=execution_id,
        )
    )

    restored_trace = ExecutionTrace(
        execution_id=execution_id,
        task_id=task_id,
        user_id="test-user",
        trace_id=original_trace_id,
    )

    assert restored_trace.trace_id == original_trace_id
    assert restored_trace.execution_id == execution_id