from uuid import uuid4

from app.graph.workflow import route_after_review
from app.schemas.review import ReviewResult


def test_approved_review_routes_to_synthesis():
    state = {
        "review": ReviewResult(
            approved=True,
            quality_score=0.95,
            confidence=0.95,
        ),
        "review_retry_count": 0,
        "max_review_retries": 2,
    }

    assert route_after_review(state) == "synthesis"


def test_rejected_review_routes_to_retry():
    state = {
        "review": ReviewResult(
            approved=False,
            quality_score=0.40,
            confidence=0.90,
            feedback="Missing evidence.",
            issues=["Insufficient evidence"],
        ),
        "review_retry_count": 0,
        "max_review_retries": 2,
    }

    assert route_after_review(state) == "review_retry"


def test_rejected_review_stops_after_retry_limit():
    state = {
        "review": ReviewResult(
            approved=False,
            quality_score=0.40,
            confidence=0.90,
            feedback="Still incomplete.",
            issues=["Missing evidence"],
        ),
        "review_retry_count": 2,
        "max_review_retries": 2,
    }

    assert route_after_review(state) == "review_failed"