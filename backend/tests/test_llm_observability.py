from types import SimpleNamespace

from app.llm.router import LLMRouter


def test_extract_gemini_usage_metadata():
    response = SimpleNamespace(
        usage_metadata={
            "prompt_token_count": 120,
            "candidates_token_count": 45,
            "total_token_count": 165,
        },
        response_metadata={},
    )

    result = LLMRouter._extract_usage(response)

    assert result == (
        120,
        45,
        165,
        None,
    )


def test_extract_openai_usage_metadata():
    response = SimpleNamespace(
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 25,
            "total_tokens": 125,
        },
        response_metadata={},
    )

    result = LLMRouter._extract_usage(response)

    assert result == (
        100,
        25,
        125,
        None,
    )


def test_extract_provider_reported_cost():
    response = SimpleNamespace(
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 25,
            "total_tokens": 125,
            "cost": 0.0125,
        },
        response_metadata={},
    )

    result = LLMRouter._extract_usage(response)

    assert result == (
        100,
        25,
        125,
        0.0125,
    )


def test_extract_usage_calculates_total_tokens():
    response = SimpleNamespace(
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 25,
        },
        response_metadata={},
    )

    result = LLMRouter._extract_usage(response)

    assert result == (
        100,
        25,
        125,
        None,
    )