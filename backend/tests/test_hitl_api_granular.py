from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "decision",
    [
        "notify",
        "approve_action",
        "approve_plan",
        "take_over",
    ],
)
async def test_granular_decision_values_are_accepted_by_api_schema(
    decision: str,
):
    """
    Invalid execution is intentional here.

    The request must pass Pydantic/FastAPI validation first.
    Therefore a valid granular decision should produce 404
    for the nonexistent execution, rather than 422.
    """

    execution_id = uuid4()

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/executions/{execution_id}/human-decision",
            json={
                "decision": decision,
                "feedback": "Reviewed by human.",
                "decided_by": "test-user",
            },
        )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "decision",
    [
        "invalid",
        "approve_action_invalid",
        "human",
        "",
        "APPROVE_ACTION",
    ],
)
async def test_invalid_granular_decision_is_rejected_by_api(
    decision: str,
):
    execution_id = uuid4()

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/executions/{execution_id}/human-decision",
            json={
                "decision": decision,
            },
        )

    assert response.status_code == 422


def test_openapi_exposes_all_granular_decisions():
    paths = app.openapi()["paths"]

    schema = paths[
        "/api/executions/{execution_id}/human-decision"
    ]["post"]

    request_body = schema["requestBody"]

    content = request_body["content"]["application/json"]

    schema_ref = content["schema"]

    assert "$ref" in schema_ref

    components = app.openapi()["components"]["schemas"]

    human_decision_schema = components[
        "HumanDecisionCreate"
    ]

    decision_schema = human_decision_schema[
        "properties"
    ]["decision"]

    assert "$ref" in decision_schema

    enum_schema = components[
        "HumanDecisionType"
    ]

    assert set(enum_schema["enum"]) == {
        "approve",
        "replan",
        "reject",
        "notify",
        "approve_action",
        "approve_plan",
        "take_over",
    }


@pytest.mark.asyncio
async def test_existing_approve_decision_remains_api_compatible():
    execution_id = uuid4()

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/executions/{execution_id}/human-decision",
            json={
                "decision": "approve",
            },
        )

    assert response.status_code == 404