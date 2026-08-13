from uuid import uuid4

import pytest

from app.db.repositories.human_decision import (
    HumanDecisionRepository,
)


@pytest.mark.parametrize(
    "decision",
    [
        "approve",
        "replan",
        "reject",
        "notify",
        "approve_action",
        "approve_plan",
        "take_over",
    ],
)
def test_granular_decision_is_allowed(
    decision,
):
    assert (
        decision
        in HumanDecisionRepository.ALLOWED_DECISIONS
    )


def test_all_granular_decisions_are_allowed():
    expected = {
        "approve",
        "replan",
        "reject",
        "notify",
        "approve_action",
        "approve_plan",
        "take_over",
    }

    assert (
        HumanDecisionRepository.ALLOWED_DECISIONS
        == expected
    )


def test_invalid_decision_is_not_allowed():
    assert (
        "invalid_decision"
        not in HumanDecisionRepository.ALLOWED_DECISIONS
    )


def test_decision_values_fit_database_column():
    decisions = (
        HumanDecisionRepository.ALLOWED_DECISIONS
    )

    assert all(
        len(decision) <= 30
        for decision in decisions
    )