import pytest

from app.hitl.sensitivity import (
    SensitiveOperationDetector,
    SensitiveOperationType,
)


@pytest.fixture
def detector():
    return SensitiveOperationDetector()


def test_safe_operation_is_not_sensitive(detector):
    result = detector.detect(
        "Read the project documentation."
    )

    assert result.sensitive is False
    assert result.operation_type is None
    assert result.reason is None


@pytest.mark.parametrize(
    ("operation", "operation_type"),
    [
        (
            "Transfer money to the supplier.",
            SensitiveOperationType.FINANCIAL,
        ),
        (
            "Send an email to the customer.",
            SensitiveOperationType.EXTERNAL_COMMUNICATION,
        ),
        (
            "Delete the production record.",
            SensitiveOperationType.DESTRUCTIVE,
        ),
        (
            "Reset the password.",
            SensitiveOperationType.CREDENTIAL,
        ),
        (
            "Grant admin access to the user.",
            SensitiveOperationType.PERMISSION,
        ),
        (
            "Export customer data.",
            SensitiveOperationType.PERSONAL_DATA,
        ),
    ],
)
def test_sensitive_operations_are_detected(
    detector,
    operation,
    operation_type,
):
    result = detector.detect(operation)

    assert result.sensitive is True
    assert result.operation_type == operation_type
    assert result.reason
    assert result.matched_text


def test_detection_is_case_insensitive(detector):
    result = detector.detect(
        "DELETE the production database."
    )

    assert result.sensitive is True
    assert (
        result.operation_type
        == SensitiveOperationType.DESTRUCTIVE
    )


def test_empty_operation_is_safe(detector):
    assert detector.is_sensitive("") is False
    assert detector.is_sensitive("   ") is False


def test_result_contains_matched_operation(detector):
    result = detector.detect(
        "Please send an email to the customer."
    )

    assert result.sensitive is True
    assert result.matched_text == "send an email"


def test_detector_does_not_flag_normal_read_operations(
    detector,
):
    operations = [
        "Read the file.",
        "Search the documentation.",
        "Calculate the total.",
        "Analyze the report.",
        "Summarize the results.",
    ]

    for operation in operations:
        assert (
            detector.is_sensitive(operation)
            is False
        )