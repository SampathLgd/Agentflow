from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


class SensitiveOperationType(StrEnum):
    FINANCIAL = "financial"
    EXTERNAL_COMMUNICATION = "external_communication"
    DESTRUCTIVE = "destructive"
    CREDENTIAL = "credential"
    PERMISSION = "permission"
    PERSONAL_DATA = "personal_data"


@dataclass(frozen=True)
class SensitiveOperationResult:
    sensitive: bool
    operation_type: SensitiveOperationType | None = None
    reason: str | None = None
    matched_text: str | None = None


class SensitiveOperationDetector:
    """
    Deterministic policy-based detector for operations that
    require human approval.

    This intentionally does not use an LLM. HITL policy decisions
    must remain predictable and testable.
    """

    _RULES: tuple[
        tuple[SensitiveOperationType, tuple[str, ...], str],
        ...
    ] = (
        (
            SensitiveOperationType.FINANCIAL,
            (
                r"\btransfer\s+(?:money|funds)\b",
                r"\bsend\s+(?:money|funds)\b",
                r"\bmake\s+(?:a\s+)?payment\b",
                r"\bpay\s+(?:an?\s+)?invoice\b",
                r"\brefund\b",
                r"\bpurchase\b",
                r"\bbuy\b",
                r"\bcharge\s+(?:a\s+)?card\b",
            ),
            "Financial action requires human approval.",
        ),
        (
            SensitiveOperationType.EXTERNAL_COMMUNICATION,
            (
                r"\bsend\s+(?:an?\s+)?email\b",
                r"\bsend\s+(?:a\s+)?message\b",
                r"\bsend\s+(?:a\s+)?text\b",
                r"\bpost\s+to\b",
                r"\bpublish\b",
                r"\bcontact\s+(?:the\s+)?customer\b",
                r"\bcontact\s+(?:the\s+)?client\b",
            ),
            "External communication requires human approval.",
        ),
        (
            SensitiveOperationType.DESTRUCTIVE,
            (
                r"\bdelete\b",
                r"\bremove\b",
                r"\bdestroy\b",
                r"\bdrop\s+(?:the\s+)?database\b",
                r"\berase\b",
                r"\bterminate\b",
            ),
            "Destructive action requires human approval.",
        ),
        (
            SensitiveOperationType.CREDENTIAL,
            (
                r"\bcreate\s+(?:an?\s+)?api\s+key\b",
                r"\bcreate\s+(?:an?\s+)?access\s+token\b",
                r"\brotate\s+(?:the\s+)?credentials?\b",
                r"\breset\s+(?:the\s+)?password\b",
                r"\bchange\s+(?:the\s+)?password\b",
                r"\brevoke\s+(?:the\s+)?token\b",
                r"\bexpose\s+(?:the\s+)?secret\b",
            ),
            "Credential or secret operation requires human approval.",
        ),
        (
            SensitiveOperationType.PERMISSION,
            (
                r"\bgrant\s+(?:admin|administrator)\s+(?:access|permission)\b",
                r"\bgrant\s+permission\b",
                r"\bchange\s+(?:user\s+)?permissions?\b",
                r"\bmodify\s+(?:user\s+)?roles?\b",
                r"\badd\s+(?:a\s+)?user\b",
                r"\bremove\s+(?:a\s+)?user\b",
            ),
            "Permission change requires human approval.",
        ),
        (
            SensitiveOperationType.PERSONAL_DATA,
            (
                r"\bexport\s+(?:customer|user|personal)\s+data\b",
                r"\bdownload\s+(?:customer|user|personal)\s+data\b",
                r"\bdelete\s+(?:customer|user)\s+data\b",
                r"\baccess\s+(?:customer|user)\s+personal\s+data\b",
                r"\bshare\s+(?:customer|user)\s+personal\s+data\b",
            ),
            "Personal-data operation requires human approval.",
        ),
    )

    def detect(
        self,
        operation: str,
    ) -> SensitiveOperationResult:
        if not operation or not operation.strip():
            return SensitiveOperationResult(
                sensitive=False,
            )

        text = operation.strip()

        for operation_type, patterns, reason in self._RULES:
            for pattern in patterns:
                match = re.search(
                    pattern,
                    text,
                    flags=re.IGNORECASE,
                )

                if match:
                    return SensitiveOperationResult(
                        sensitive=True,
                        operation_type=operation_type,
                        reason=reason,
                        matched_text=match.group(0),
                    )

        return SensitiveOperationResult(
            sensitive=False,
        )

    def is_sensitive(
        self,
        operation: str,
    ) -> bool:
        return self.detect(operation).sensitive