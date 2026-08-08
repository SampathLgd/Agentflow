from uuid import uuid4

import pytest

from app.config import Settings
from app.llm.router import LLMRouter
from app.schemas.execution import Complexity, ExecutionPlan, Specialist, SubTask


class FakeRateLimitError(Exception):
    status_code = 429


class FakeStructuredModel:
    def __init__(self, result: ExecutionPlan):
        self.result = result

    async def ainvoke(self, prompt: str) -> ExecutionPlan:
        return self.result


class FakeFailingModel:
    def with_structured_output(self, schema, method="json_schema"):
        raise FakeRateLimitError("Gemini quota exceeded")


class FakeSuccessfulModel:
    def __init__(self, result: ExecutionPlan):
        self.result = result

    def with_structured_output(self, schema, method="json_schema"):
        return FakeStructuredModel(self.result)


def create_test_settings() -> Settings:
    return Settings(
        llm_provider_order="gemini,openrouter",
        gemini_api_key="test-gemini-key",
        openrouter_api_key="test-openrouter-key",
        gemini_model="gemini-3.5-flash-lite",
        openrouter_model="openrouter/free",
        supervisor_provider="gemini",
        research_provider="gemini",
        writing_provider="gemini",
        reviewer_provider="gemini",
        data_analysis_provider="openrouter",
        code_execution_provider="openrouter",
    )


@pytest.mark.asyncio
async def test_gemini_quota_falls_back_to_openrouter(
    monkeypatch,
) -> None:
    settings = create_test_settings()

    router = LLMRouter(settings)

    task_id = uuid4()

    expected_plan = ExecutionPlan(
        task_id=task_id,
        subtasks=[
            SubTask(
                id=uuid4(),
                description="Research the topic",
                assigned_specialist=Specialist.RESEARCH,
                required_inputs=["user task"],
                expected_output="Research findings",
                estimated_complexity=Complexity.MEDIUM,
            )
        ],
    )

    def fake_create_llm(settings, provider):
        if provider == "gemini":
            return FakeFailingModel()

        if provider == "openrouter":
            return FakeSuccessfulModel(expected_plan)

        raise AssertionError(
            f"Unexpected provider: {provider}"
        )

    monkeypatch.setattr(
        "app.llm.router.create_llm",
        fake_create_llm,
    )

    result = await router.ainvoke_structured(
        task_type="supervisor",
        prompt="Create an execution plan.",
        schema=ExecutionPlan,
    )

    assert isinstance(result, ExecutionPlan)
    assert result.task_id == task_id
    assert len(result.subtasks) == 1
    assert result.subtasks[0].assigned_specialist == Specialist.RESEARCH

def test_invalid_request_does_not_trigger_fallback() -> None:
    settings = create_test_settings()

    router = LLMRouter(settings)

    class InvalidRequestError(Exception):
        status_code = 400

    error = InvalidRequestError(
        "Invalid request"
    )

    assert not router._is_retryable_error(error)