from app.schemas.hitl_review import (
    HITLReviewContext,
)


def test_review_context_contains_required_fields():
    context = HITLReviewContext(
        original_task=(
            "Send the customer an email."
        ),
        proposed_action=(
            "Send customer email"
        ),
        reasoning=(
            "External communication "
            "requires approval."
        ),
    )

    assert (
        context.original_task
        == "Send the customer an email."
    )

    assert (
        context.proposed_action
        == "Send customer email"
    )

    assert (
        context.reasoning
        == (
            "External communication "
            "requires approval."
        )
    )


def test_review_context_defaults_collections():
    context = HITLReviewContext(
        original_task="Test task",
        proposed_action="Test action",
    )

    assert context.completed_steps == []

    assert context.relevant_memories == []

    assert context.past_decisions == []