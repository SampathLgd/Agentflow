from types import SimpleNamespace

from app.api.routes.trace import (
    _compare_spans,
    _normalize_execution_status,
)


def make_span(
    *,
    span_id,
    name,
    kind,
    status="success",
    agent=None,
    specialist=None,
    tool_name=None,
    duration_ms=100.0,
    total_tokens=None,
    cost=None,
    input=None,
    output=None,
    error=None,
):
    return SimpleNamespace(
        span_id=span_id,
        name=name,
        kind=kind,
        status=status,
        agent=agent,
        specialist=specialist,
        subtask_id=None,
        tool_name=tool_name,
        provider=None,
        model=None,
        confidence=None,
        duration_ms=duration_ms,
        input_tokens=None,
        output_tokens=None,
        total_tokens=total_tokens,
        cost=cost,
        input=input,
        output=output,
        prompt=None,
        raw_response=None,
        error=error,
    )


def test_status_aliases_are_semantically_equal():
    assert _normalize_execution_status("success") == "completed"
    assert _normalize_execution_status("completed") == "completed"
    assert _normalize_execution_status("failure") == "failed"
    assert _normalize_execution_status("failed") == "failed"


def test_runtime_uuid_noise_does_not_make_span_changed():
    original = [
        make_span(
            span_id="original-span",
            name="planning",
            kind="planning",
            input='{"task_id":"11111111-1111-1111-1111-111111111111","description":"same"}',
            output='{"subtask_id":"22222222-2222-2222-2222-222222222222","value":"same"}',
        )
    ]

    replay = [
        make_span(
            span_id="replay-span",
            name="planning",
            kind="planning",
            input='{"task_id":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa","description":"same"}',
            output='{"subtask_id":"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb","value":"same"}',
        )
    ]

    result = _compare_spans(
        original,
        replay,
        "success",
    )

    assert len(result) == 1
    assert result[0]["change"] == "unchanged"


def test_failed_replay_marks_downstream_spans_not_reached():
    original = [
        make_span(
            span_id="1",
            name="planning",
            kind="planning",
        ),
        make_span(
            span_id="2",
            name="specialist",
            kind="specialist",
            specialist="research",
        ),
        make_span(
            span_id="3",
            name="review",
            kind="workflow_node",
        ),
    ]

    replay = [
        make_span(
            span_id="r1",
            name="planning",
            kind="planning",
            status="failure",
            error="planner failed",
        ),
    ]

    result = _compare_spans(
        original,
        replay,
        "failure",
    )

    assert [item["change"] for item in result] == [
        "changed",
        "not_reached",
        "not_reached",
    ]


def test_successful_replay_can_report_removed_span():
    original = [
        make_span(
            span_id="1",
            name="planning",
            kind="planning",
        ),
        make_span(
            span_id="2",
            name="review",
            kind="workflow_node",
        ),
    ]

    replay = [
        make_span(
            span_id="r1",
            name="planning",
            kind="planning",
        ),
    ]

    result = _compare_spans(
        original,
        replay,
        "success",
    )

    assert result[-1]["change"] == "removed"


def test_new_replay_span_is_added():
    original = [
        make_span(
            span_id="1",
            name="planning",
            kind="planning",
        ),
    ]

    replay = [
        make_span(
            span_id="r1",
            name="planning",
            kind="planning",
        ),
        make_span(
            span_id="r2",
            name="new_step",
            kind="workflow_node",
        ),
    ]

    result = _compare_spans(
        original,
        replay,
        "success",
    )

    assert result[-1]["change"] == "added"