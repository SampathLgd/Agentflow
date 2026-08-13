import pytest

from app.hitl.user_request import (
    UserEscalationDetector,
)


@pytest.fixture
def detector():
    return UserEscalationDetector()


@pytest.mark.parametrize(
    "user_input",
    [
        "Escalate this to a human.",
        "Please escalate this.",
        "Ask a human to review this.",
        "Ask a human to approve this.",
        "Let a human review this.",
        "I want a human to review this.",
        "Have a human approve this.",
        "Human review required.",
        "A person should handle this.",
        "Hand this over to a human.",
    ],
)
def test_explicit_user_request_requires_escalation(
    detector,
    user_input,
):
    result = detector.detect(user_input)

    assert result.escalation_required is True
    assert result.reason is not None
    assert result.matched_text is not None


def test_user_request_detection_is_case_insensitive(
    detector,
):
    result = detector.detect(
        "ESCALATE THIS TO A HUMAN."
    )

    assert result.escalation_required is True


def test_empty_request_does_not_escalate(
    detector,
):
    assert (
        detector.is_requested("")
        is False
    )

    assert (
        detector.is_requested("   ")
        is False
    )


@pytest.mark.parametrize(
    "user_input",
    [
        "Review the report.",
        "Analyze the task.",
        "Ask the specialist to review this.",
        "Check whether the task is correct.",
        "Human resources documentation.",
        "This task needs careful review.",
        "Send the report to the team.",
    ],
)
def test_normal_requests_do_not_escalate(
    detector,
    user_input,
):
    assert (
        detector.is_requested(user_input)
        is False
    )


def test_result_preserves_matched_phrase(
    detector,
):
    result = detector.detect(
        "Please ask a human to review this execution."
    )

    assert result.escalation_required is True
    assert result.matched_text is not None
    assert "human" in result.matched_text.lower()


def test_result_contains_explicit_reason(
    detector,
):
    result = detector.detect(
        "Escalate this to a human."
    )

    assert (
        result.reason
        == "The user explicitly requested human intervention."
    )