import pytest
from pydantic import ValidationError

from app.schemas.review import ReviewResult


def test_approved_review():
    result = ReviewResult(
        approved=True,
        quality_score=0.95,
        confidence=0.90,
        feedback="",
        issues=[],
    )

    assert result.approved is True
    assert result.quality_score == 0.95
    assert result.confidence == 0.90


def test_rejected_review_contains_feedback():
    result = ReviewResult(
        approved=False,
        quality_score=0.45,
        confidence=0.92,
        feedback=(
            "The research output does not provide "
            "enough supporting evidence."
        ),
        issues=[
            "Missing sources",
            "Insufficient evidence",
        ],
    )

    assert result.approved is False
    assert result.quality_score == 0.45
    assert len(result.issues) == 2
    assert result.feedback


def test_quality_score_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        ReviewResult(
            approved=True,
            quality_score=1.5,
            confidence=0.9,
        )


def test_confidence_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        ReviewResult(
            approved=True,
            quality_score=0.9,
            confidence=-0.1,
        )


def test_feedback_defaults_to_empty_string():
    result = ReviewResult(
        approved=True,
        quality_score=0.9,
        confidence=0.9,
    )

    assert result.feedback == ""
    assert result.issues == []