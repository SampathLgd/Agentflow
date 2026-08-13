import pytest

from app.hitl.failure import (
    SpecialistFailureEscalator,
)


@pytest.fixture
def escalator():
    return SpecialistFailureEscalator(
        max_retries=2,
    )


def test_first_failure_does_not_escalate(
    escalator,
):
    result = escalator.evaluate(
        specialist="researcher",
        failure_count=1,
        reason="Tool timeout.",
    )

    assert result.escalation_required is False
    assert result.failure_count == 1
    assert result.max_retries == 2
    assert result.specialist == "researcher"
    assert result.reason == "Tool timeout."


def test_second_failure_does_not_escalate(
    escalator,
):
    result = escalator.evaluate(
        specialist="researcher",
        failure_count=2,
        reason="Tool timeout.",
    )

    assert result.escalation_required is False


def test_repeated_failure_escalates(
    escalator,
):
    result = escalator.evaluate(
        specialist="researcher",
        failure_count=3,
        reason="Tool timeout.",
    )

    assert result.escalation_required is True
    assert result.failure_count == 3
    assert result.specialist == "researcher"
    assert result.reason == "Tool timeout."


def test_escalation_without_reason_generates_reason(
    escalator,
):
    result = escalator.evaluate(
        specialist="coder",
        failure_count=3,
    )

    assert result.escalation_required is True
    assert result.reason is not None
    assert "coder" in result.reason
    assert "3" in result.reason


def test_failure_count_is_preserved(
    escalator,
):
    result = escalator.evaluate(
        specialist="planner",
        failure_count=7,
        reason="Repeated failure.",
    )

    assert result.failure_count == 7
    assert result.max_retries == 2


def test_success_does_not_escalate(
    escalator,
):
    assert (
        escalator.should_escalate(
            failure_count=1,
        )
        is False
    )


def test_threshold_is_deterministic(
    escalator,
):
    assert (
        escalator.should_escalate(
            failure_count=2,
        )
        is False
    )

    assert (
        escalator.should_escalate(
            failure_count=3,
        )
        is True
    )


def test_invalid_failure_count_is_rejected(
    escalator,
):
    with pytest.raises(
        ValueError,
        match="failure_count",
    ):
        escalator.evaluate(
            specialist="researcher",
            failure_count=0,
        )


def test_empty_specialist_is_rejected(
    escalator,
):
    with pytest.raises(
        ValueError,
        match="specialist",
    ):
        escalator.evaluate(
            specialist="   ",
            failure_count=1,
        )


def test_invalid_retry_configuration_is_rejected():
    with pytest.raises(
        ValueError,
        match="max_retries",
    ):
        SpecialistFailureEscalator(
            max_retries=0,
        )