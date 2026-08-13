from app.schemas.human_decision import HumanDecisionCreate
from app.schemas.human_decision import HumanDecisionType


def test_existing_human_decisions_remain_supported():
    assert HumanDecisionType.APPROVE.value == "approve"
    assert HumanDecisionType.REPLAN.value == "replan"
    assert HumanDecisionType.REJECT.value == "reject"


def test_granular_human_decisions_exist():
    assert HumanDecisionType.NOTIFY.value == "notify"
    assert (
        HumanDecisionType.APPROVE_ACTION.value
        == "approve_action"
    )
    assert (
        HumanDecisionType.APPROVE_PLAN.value
        == "approve_plan"
    )
    assert HumanDecisionType.TAKE_OVER.value == "take_over"


def test_human_decision_payload_accepts_granular_decisions():
    payload = HumanDecisionCreate(
        decision=HumanDecisionType.APPROVE_ACTION,
        feedback="Approved the requested action.",
        decided_by="human",
    )

    assert payload.decision == (
        HumanDecisionType.APPROVE_ACTION
    )


def test_human_decision_payload_accepts_notify():
    payload = HumanDecisionCreate(
        decision="notify",
    )

    assert payload.decision == HumanDecisionType.NOTIFY


def test_human_decision_payload_rejects_unknown_decision():
    try:
        HumanDecisionCreate(
            decision="something_invalid",
        )
    except Exception:
        return

    raise AssertionError(
        "Unknown human decision should be rejected."
    )