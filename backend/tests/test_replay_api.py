from uuid import uuid4

import pytest


def test_replay_schema_accepts_basic_request():
    from app.schemas.replay import (
        ReplayExecutionRequest,
    )

    execution_id = uuid4()

    request = ReplayExecutionRequest(
        source_execution_id=execution_id,
        source_span_id="abc123",
        input_override={
            "description": "Changed research question"
        },
    )

    assert (
        request.source_execution_id
        == execution_id
    )

    assert (
        request.source_span_id
        == "abc123"
    )

    assert (
        request.input_override[
            "description"
        ]
        == "Changed research question"
    )


def test_replay_schema_allows_no_override():
    from app.schemas.replay import (
        ReplayExecutionRequest,
    )

    request = ReplayExecutionRequest(
        source_execution_id=uuid4(),
    )

    assert (
        request.source_span_id
        is None
    )

    assert (
        request.input_override
        is None
    )
