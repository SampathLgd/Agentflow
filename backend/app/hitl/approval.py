from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ApprovalLevel(StrEnum):
    """
    Human review depth required for an escalation.

    notify:
        Continue execution while informing the human.

    approve_action:
        Human must approve the next proposed action.

    approve_plan:
        Human must review/approve the execution plan.

    take_over:
        Human takes control and the agents stand down.
    """

    NOTIFY = "notify"
    APPROVE_ACTION = "approve_action"
    APPROVE_PLAN = "approve_plan"
    TAKE_OVER = "take_over"


class EscalationTrigger(StrEnum):
    """
    Deterministic reasons why an execution entered HITL.
    """

    SUPERVISOR_LOW_CONFIDENCE = (
        "supervisor_low_confidence"
    )

    SPECIALIST_FAILURE = (
        "specialist_failure"
    )

    SENSITIVE_OPERATION = (
        "sensitive_operation"
    )

    REVIEWER_LOW_CONFIDENCE = (
        "reviewer_low_confidence"
    )

    USER_REQUEST = (
        "user_request"
    )


@dataclass(frozen=True)
class ApprovalPolicyResult:
    """
    Result of mapping an escalation trigger to the
    required human approval depth.
    """

    trigger: EscalationTrigger
    approval_level: ApprovalLevel
    reason: str


class ApprovalPolicy:
    """
    Maps deterministic escalation triggers to human
    approval levels.

    The mapping is explicit and configurable rather than
    being inferred by an LLM.
    """

    DEFAULT_LEVELS: dict[
        EscalationTrigger,
        ApprovalLevel,
    ] = {
        EscalationTrigger.SUPERVISOR_LOW_CONFIDENCE:
            ApprovalLevel.APPROVE_PLAN,

        EscalationTrigger.SPECIALIST_FAILURE:
            ApprovalLevel.APPROVE_ACTION,

        EscalationTrigger.SENSITIVE_OPERATION:
            ApprovalLevel.APPROVE_ACTION,

        EscalationTrigger.REVIEWER_LOW_CONFIDENCE:
            ApprovalLevel.APPROVE_ACTION,

        EscalationTrigger.USER_REQUEST:
            ApprovalLevel.TAKE_OVER,
    }

    def __init__(
        self,
        *,
        levels: dict[
            EscalationTrigger,
            ApprovalLevel,
        ] | None = None,
    ) -> None:
        configured = dict(
            self.DEFAULT_LEVELS
        )

        if levels is not None:
            configured.update(levels)

        missing = set(
            EscalationTrigger
        ) - set(configured)

        if missing:
            names = ", ".join(
                sorted(
                    trigger.value
                    for trigger in missing
                )
            )

            raise ValueError(
                "Approval policy is missing "
                f"trigger mappings: {names}"
            )

        self.levels = configured

    def level_for(
        self,
        trigger: EscalationTrigger,
    ) -> ApprovalLevel:
        try:
            return self.levels[trigger]
        except KeyError as exc:
            raise ValueError(
                f"No approval level configured for "
                f"trigger: {trigger.value}"
            ) from exc

    def evaluate(
        self,
        *,
        trigger: EscalationTrigger,
        reason: str,
    ) -> ApprovalPolicyResult:
        normalized_reason = (
            reason.strip()
            if reason
            else ""
        )

        if not normalized_reason:
            normalized_reason = (
                f"Human review required because "
                f"{trigger.value.replace('_', ' ')}."
            )

        return ApprovalPolicyResult(
            trigger=trigger,
            approval_level=self.level_for(
                trigger
            ),
            reason=normalized_reason,
        )