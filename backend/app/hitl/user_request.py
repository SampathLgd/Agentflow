from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class UserEscalationResult:
    escalation_required: bool
    reason: str | None = None
    matched_text: str | None = None


class UserEscalationDetector:
    """
    Detect explicit user requests for human intervention.

    This is intentionally deterministic. An explicit request from
    the user should not depend on an LLM interpretation.
    """

    _PATTERNS: tuple[str, ...] = (
        r"\bescalate\s+(?:this|it|the\s+(?:task|request|execution))"
        r"(?:\s+to\s+(?:a\s+)?human)?\b",

        r"\bask\s+(?:a\s+)?human\s+(?:to\s+)?"
        r"(?:review|approve|handle|take\s+over)\b",

        r"\blet\s+(?:a\s+)?human\s+"
        r"(?:review|approve|handle|take\s+over)\b",

        r"\bhuman\s+(?:review|approval|intervention)\b",

        r"\bi\s+want\s+(?:a\s+)?human\s+(?:to\s+)?"
        r"(?:review|approve|handle)\b",

        # Explicit request for human takeover/intervention.
        r"\b(?:i\s+)?(?:explicitly\s+)?request\s+(?:a\s+)?"
        r"human\s+(?:to\s+)?"
        r"(?:take\s+over|takeover|intervene|review|approve|handle)\b",

        r"\b(?:please\s+)?(?:have|get)\s+(?:a\s+)?human\s+(?:to\s+)?"
        r"(?:review|approve|handle|take\s+over)\b",

        r"\b(?:human|person)\s+should\s+"
        r"(?:review|approve|handle|take\s+over)\b",

        r"\b(?:hand|hand\s+this)\s+(?:this\s+)?(?:over\s+)?"
        r"to\s+(?:a\s+)?human\b",
    )

    def detect(
        self,
        request: str,
    ) -> UserEscalationResult:
        if not request or not request.strip():
            return UserEscalationResult(
                escalation_required=False,
            )

        text = request.strip()

        for pattern in self._PATTERNS:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                return UserEscalationResult(
                    escalation_required=True,
                    reason=(
                        "The user explicitly requested "
                        "human intervention."
                    ),
                    matched_text=match.group(0),
                )

        return UserEscalationResult(
            escalation_required=False,
        )

    def is_requested(
        self,
        request: str,
    ) -> bool:
        return self.detect(
            request
        ).escalation_required