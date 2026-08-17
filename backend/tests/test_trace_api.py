from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import trace


class FakeAsyncSessionContext:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False


class FakeSession:
    pass


class FakeTraceRepository:
    trace_model = None
    spans = []

    def __init__(self, session) -> None:
        self.session = session

    async def get_by_execution(
        self,
        execution_id,
    ):
        if (
            self.trace_model is not None
            and self.trace_model.execution_id
            == execution_id
        ):
            return self.trace_model

        return None

    async def get_spans(
        self,
        trace_id: str,
    ):
        return [
            span
            for span in self.spans
            if span.trace_id == trace_id
        ]


def build_app(
    monkeypatch,
) -> FastAPI:
    app = FastAPI()

    app.include_router(
        trace.router
    )

    monkeypatch.setattr(
        trace,
        "AsyncSessionLocal",
        lambda: FakeAsyncSessionContext(
            FakeSession()
        ),
    )

    monkeypatch.setattr(
        trace,
        "TraceRepository",
        FakeTraceRepository,
    )

    return app


def make_trace_data():
    execution_id = uuid4()
    task_id = uuid4()
    trace_id = "trace-test-001"

    started_at = datetime(
        2026,
        8,
        13,
        10,
        0,
        tzinfo=timezone.utc,
    )

    completed_at = datetime(
        2026,
        8,
        13,
        10,
        0,
        5,
        tzinfo=timezone.utc,
    )

    FakeTraceRepository.trace_model = (
        SimpleNamespace(
            execution_id=execution_id,
            task_id=task_id,
            trace_id=trace_id,
            user_id="user-123",
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            wall_clock_ms=5000.0,
            total_input_tokens=100,
            total_output_tokens=50,
            total_tokens=150,
            total_tool_calls=2,
            total_cost=0.01,
            attributes={
                "environment": "test",
            },
        )
    )

    root_span_id = "span-root"
    child_span_id = "span-child"

    FakeTraceRepository.spans = [
        SimpleNamespace(
            trace_id=trace_id,
            span_id=root_span_id,
            parent_span_id=None,
            execution_id=execution_id,
            name="planning",
            kind="planning",
            status="success",
            agent="supervisor",
            specialist=None,
            subtask_id=None,
            tool_name=None,
            provider=None,
            model=None,
            confidence=None,
            started_at=started_at,
            ended_at=completed_at,
            duration_ms=5000.0,
            input='"task"',
            output='"plan"',
            prompt="create plan",
            raw_response='"plan"',
            error=None,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            cost=None,
            attributes={},
        ),
        SimpleNamespace(
            trace_id=trace_id,
            span_id=child_span_id,
            parent_span_id=root_span_id,
            execution_id=execution_id,
            name="llm.generate_structured",
            kind="llm",
            status="success",
            agent="supervisor",
            specialist=None,
            subtask_id=None,
            tool_name=None,
            provider="openai",
            model="gpt",
            confidence=None,
            started_at=started_at,
            ended_at=completed_at,
            duration_ms=1200.0,
            input='"task"',
            output='"plan"',
            prompt="create plan",
            raw_response='"plan"',
            error=None,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost=0.01,
            attributes={
                "schema": "ExecutionPlan",
            },
        ),
    ]

    return execution_id


def test_get_execution_trace(
    monkeypatch,
):
    app = build_app(
        monkeypatch
    )

    execution_id = make_trace_data()

    client = TestClient(app)

    response = client.get(
        f"/api/executions/"
        f"{execution_id}/trace"
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["trace_id"]
        == "trace-test-001"
    )

    assert (
        body["execution_id"]
        == str(execution_id)
    )

    assert (
        body["status"]
        == "completed"
    )

    assert (
        body["total_input_tokens"]
        == 100
    )

    assert (
        body["total_output_tokens"]
        == 50
    )

    assert (
        body["total_tokens"]
        == 150
    )

    assert (
        body["total_tool_calls"]
        == 2
    )

    assert (
        body["total_cost"]
        == 0.01
    )

    assert len(body["spans"]) == 2

    root = body["spans"][0]
    child = body["spans"][1]

    assert (
        root["name"]
        == "planning"
    )

    assert (
        root["parent_span_id"]
        is None
    )

    assert (
        child["name"]
        == "llm.generate_structured"
    )

    assert (
        child["parent_span_id"]
        == "span-root"
    )

    assert (
        child["provider"]
        == "openai"
    )

    assert (
        child["model"]
        == "gpt"
    )

    assert (
        child["input_tokens"]
        == 100
    )

    assert (
        child["output_tokens"]
        == 50
    )

    assert (
        child["total_tokens"]
        == 150
    )


def test_get_execution_trace_spans(
    monkeypatch,
):
    app = build_app(
        monkeypatch
    )

    execution_id = make_trace_data()

    client = TestClient(app)

    response = client.get(
        f"/api/executions/"
        f"{execution_id}/trace/spans"
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["trace_id"]
        == "trace-test-001"
    )

    assert (
        body["execution_id"]
        == str(execution_id)
    )

    assert len(body["spans"]) == 2

    assert (
        body["spans"][0]["name"]
        == "planning"
    )

    assert (
        body["spans"][1]["name"]
        == "llm.generate_structured"
    )


def test_get_execution_trace_not_found(
    monkeypatch,
):
    app = build_app(
        monkeypatch
    )

    client = TestClient(app)

    response = client.get(
        f"/api/executions/"
        f"{uuid4()}/trace"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Execution trace not found."
    )