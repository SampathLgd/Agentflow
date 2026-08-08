import pytest

from app.config import Settings
from app.llm.router import LLMRouter


def create_test_settings() -> Settings:
    return Settings(
        llm_provider_order="gemini,openrouter",
        gemini_api_key="test-gemini-key",
        openrouter_api_key="test-openrouter-key",
        gemini_model="gemini-2.5-flash-lite",
        openrouter_model="openrouter/free",
        supervisor_provider="gemini",
        research_provider="gemini",
        writing_provider="gemini",
        reviewer_provider="gemini",
        data_analysis_provider="openrouter",
        code_execution_provider="openrouter",
    )


def test_provider_order() -> None:
    settings = create_test_settings()
    router = LLMRouter(settings)

    assert router._provider_order == [
        "gemini",
        "openrouter",
    ]


def test_supervisor_primary_provider() -> None:
    settings = create_test_settings()
    router = LLMRouter(settings)

    candidates = router._provider_candidates(
        "supervisor"
    )

    assert candidates == [
        "gemini",
        "openrouter",
    ]


def test_code_execution_primary_provider() -> None:
    settings = create_test_settings()
    router = LLMRouter(settings)

    candidates = router._provider_candidates(
        "code_execution"
    )

    assert candidates == [
        "openrouter",
        "gemini",
    ]


def test_retryable_status_codes() -> None:
    settings = create_test_settings()
    router = LLMRouter(settings)

    class RateLimitError(Exception):
        status_code = 429

    class ServerError(Exception):
        status_code = 503

    assert router._is_retryable_error(
        RateLimitError()
    )

    assert router._is_retryable_error(
        ServerError()
    )


def test_non_retryable_error() -> None:
    settings = create_test_settings()
    router = LLMRouter(settings)

    class InvalidRequestError(Exception):
        status_code = 400

    assert not router._is_retryable_error(
        InvalidRequestError()
    )