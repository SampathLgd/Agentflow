from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecialistFailureResult:
    """
    Result of evaluating a specialist failure.
    """

    escalation_required: bool
    failure_count: int
    max_retries: int
    specialist: str | None = None
    reason: str | None = None


class SpecialistFailureEscalator:
    """
    Determines when repeated specialist failures should
    escalate execution to a human.

    The policy is deterministic and does not involve an LLM.
    """

    def __init__(
        self,
        *,
        max_retries: int = 2,
    ) -> None:
        if max_retries < 1:
            raise ValueError(
                "max_retries must be at least 1."
            )

        self.max_retries = max_retries

    def evaluate(
        self,
        *,
        specialist: str,
        failure_count: int,
        reason: str | None = None,
    ) -> SpecialistFailureResult:
        if failure_count < 1:
            raise ValueError(
                "failure_count must be at least 1."
            )

        specialist_name = (
            specialist.strip()
            if specialist
            else ""
        )

        if not specialist_name:
            raise ValueError(
                "specialist cannot be empty."
            )

        escalation_required = (
            failure_count > self.max_retries
        )

        if escalation_required:
            escalation_reason = (
                reason
                or (
                    f"Specialist '{specialist_name}' "
                    f"failed {failure_count} times."
                )
            )
        else:
            escalation_reason = reason

        return SpecialistFailureResult(
            escalation_required=(
                escalation_required
            ),
            failure_count=failure_count,
            max_retries=self.max_retries,
            specialist=specialist_name,
            reason=escalation_reason,
        )

    def should_escalate(
        self,
        *,
        failure_count: int,
    ) -> bool:
        if failure_count < 1:
            raise ValueError(
                "failure_count must be at least 1."
            )

        return failure_count > self.max_retries