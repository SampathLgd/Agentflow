import pytest

from app.graph.workflow import (
    escalate,
    route_after_review,
)
from app.schemas.review import ReviewResult


def make_review(
    *,
    approved: bool,
    confidence: float,
    quality_score: float = 0.9,
    feedback: str = "",
) -> ReviewResult:
    return ReviewResult(
        approved=approved,
        quality_score=quality_score,
        confidence=confidence,
        feedback=feedback,
    )


def test_low_confidence_review_routes_to_escalation():
    review = make_review(
        approved=True,
        confidence=0.3,
    )

    state = {
        "review": review,
        "confidence_threshold": 0.5,
    }

    assert route_after_review(state) == "escalate"


def test_high_confidence_approved_review_routes_to_synthesis():
    review = make_review(
        approved=True,
        confidence=0.9,
    )

    state = {
        "review": review,
        "confidence_threshold": 0.5,
    }

    assert route_after_review(state) == "synthesis"


@pytest.mark.asyncio
async def test_low_confidence_escalation_sets_replan():
    review = make_review(
        approved=True,
        confidence=0.2,
    )

    state = {
        "review": review,
        "confidence_threshold": 0.5,
    }

    result = await escalate(state)

    assert result["escalation_required"] is True
    assert result["replan_required"] is True

    assert (
        "Reviewer confidence"
        in result["escalation_reason"]
    )


def test_confidence_at_threshold_does_not_escalate():
    review = make_review(
        approved=True,
        confidence=0.5,
    )

    state = {
        "review": review,
        "confidence_threshold": 0.5,
    }

    assert route_after_review(state) == "synthesis"


@pytest.mark.asyncio
async def test_escalation_preserves_low_confidence_reason():
    review = make_review(
        approved=True,
        confidence=0.25,
    )

    state = {
        "review": review,
        "confidence_threshold": 0.5,
    }

    result = await escalate(state)

    assert result["escalation_required"] is True
    assert result["replan_required"] is True
    assert "0.25" in result["escalation_reason"]