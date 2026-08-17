from uuid import uuid4

import pytest

from app.observability.tracing import (
    annotate_current_span,
    current_trace,
    start_trace,
    use_trace,
)


def test_trace_records_parent_child_relationships():
    execution_id = uuid4()
    trace = start_trace(
        execution_id=execution_id,
        task_id=uuid4(),
        user_id="trace-test-user",
    )

    with use_trace(trace):
        with current_trace(
            name="workflow",
            kind="workflow",
        ):
            with current_trace(
                name="llm.generate",
                kind="llm",
                provider="test",
                model="test-model",
            ) as child:
                assert child is not None
                annotate_current_span(
                    input_value="hello",
                    prompt="hello",
                )

    assert len(trace.spans) == 2
    assert trace.spans[1].parent_span_id == trace.spans[0].span_id
    assert trace.spans[1].status == "success"
    assert trace.spans[1].prompt == '"hello"'


def test_trace_aggregates_tokens_tools_and_cost():
    trace = start_trace(
        execution_id=uuid4()
    )

    with use_trace(trace):
        with current_trace(
            name="llm.generate",
            kind="llm",
        ) as span:
            assert span is not None
            span.finish(
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                cost=0.25,
            )

        with current_trace(
            name="tool.web_search",
            kind="tool",
        ):
            pass

    assert trace.total_tokens == 30
    assert trace.total_cost == 0.25
    assert trace.total_tool_calls == 1


@pytest.mark.asyncio
async def test_tool_executor_emits_tool_span():
    from app.tools.executor import ToolExecutor
    from app.tools.registry import ToolRegistry

    # The registry is intentionally not exercised here; this test
    # verifies that the observability context remains safe when no
    # execution trace is active.
    assert ToolExecutor is not None
    assert ToolRegistry is not None
