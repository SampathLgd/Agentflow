from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.human_decision import HumanDecisionModel


class HumanDecisionRepository:
    """
    Repository for HITL human decisions.

    Lifecycle:

        pending -> decided

    A pending decision contains the complete review packet
    required by the reviewer UI.
    """

    ALLOWED_DECISIONS = {
        "approve",
        "replan",
        "reject",
        "notify",
        "approve_action",
        "approve_plan",
        "take_over",
    }

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    # =========================================================
    # Normalization helpers
    # =========================================================

    @staticmethod
    def _normalize_approval_level(
        approval_level: Any,
    ) -> str | None:
        """
        Convert enum/string approval levels into the
        database representation.

        Examples:

            ApprovalLevel.TAKE_OVER -> "take_over"
            "take_over"             -> "take_over"
            None                    -> None
        """

        if approval_level is None:
            return None

        if isinstance(approval_level, Enum):
            return str(approval_level.value)

        return str(approval_level).strip().lower()

    # =========================================================
    # Pending decision creation
    # =========================================================

    async def create_pending(
        self,
        *,
        execution_id: UUID,
        approval_level: str | None = None,
        escalation_trigger: str | None = None,
        proposed_action: str | None = None,
        review_context: dict[str, Any] | None = None,
    ) -> HumanDecisionModel:
        """
        Create a pending HITL decision together with its
        complete review metadata.

        If a pending decision already exists for this
        execution, update its missing HITL metadata rather
        than returning an incomplete record.
        """

        normalized_approval_level = (
            self._normalize_approval_level(
                approval_level
            )
        )

        existing = await self.get_pending_for_execution(
            execution_id
        )

        if existing is not None:
            self._populate_review_metadata(
                existing,
                approval_level=(
                    normalized_approval_level
                ),
                escalation_trigger=(
                    escalation_trigger
                ),
                proposed_action=(
                    proposed_action
                ),
                review_context=(
                    review_context
                ),
            )

            await self.session.flush()

            return existing

        decision = HumanDecisionModel(
            execution_id=execution_id,
            status="pending",
            approval_level=(
                normalized_approval_level
            ),
            escalation_trigger=(
                escalation_trigger
            ),
            proposed_action=(
                proposed_action
            ),
            review_context=(
                review_context
            ),
        )

        self.session.add(decision)

        await self.session.flush()

        return decision

    # =========================================================
    # Get or create pending decision
    # =========================================================

    async def get_or_create_pending(
        self,
        *,
        execution_id: UUID,
        approval_level: str | None = None,
        escalation_trigger: str | None = None,
        proposed_action: str | None = None,
        review_context: dict[str, Any] | None = None,
    ) -> HumanDecisionModel:
        """
        Return the existing pending decision or create one.

        IMPORTANT:

        An existing pending decision is not blindly returned.

        If the existing record has incomplete HITL metadata,
        the supplied metadata is applied to it. This prevents
        stale pending decisions from remaining with NULL
        approval/escalation/review fields.
        """

        normalized_approval_level = (
            self._normalize_approval_level(
                approval_level
            )
        )

        existing = await self.get_pending_for_execution(
            execution_id
        )

        if existing is not None:
            self._populate_review_metadata(
                existing,
                approval_level=(
                    normalized_approval_level
                ),
                escalation_trigger=(
                    escalation_trigger
                ),
                proposed_action=(
                    proposed_action
                ),
                review_context=(
                    review_context
                ),
            )

            await self.session.flush()

            return existing

        return await self.create_pending(
            execution_id=execution_id,
            approval_level=(
                normalized_approval_level
            ),
            escalation_trigger=(
                escalation_trigger
            ),
            proposed_action=(
                proposed_action
            ),
            review_context=(
                review_context
            ),
        )

    # =========================================================
    # Metadata population
    # =========================================================

    @staticmethod
    def _populate_review_metadata(
        decision: HumanDecisionModel,
        *,
        approval_level: str | None,
        escalation_trigger: str | None,
        proposed_action: str | None,
        review_context: dict[str, Any] | None,
    ) -> None:
        """
        Populate/update the complete HITL review packet.

        New non-None values replace stale/missing values.
        Existing values are preserved when the caller does
        not provide a replacement.
        """

        if approval_level is not None:
            decision.approval_level = (
                approval_level
            )

        if escalation_trigger is not None:
            decision.escalation_trigger = (
                escalation_trigger
            )

        if proposed_action is not None:
            decision.proposed_action = (
                proposed_action
            )

        if review_context is not None:
            decision.review_context = (
                review_context
            )

    # =========================================================
    # Pending queue
    # =========================================================

    async def list_pending(
        self,
        *,
        limit: int = 50,
    ) -> list[HumanDecisionModel]:
        """
        Return pending human decisions for the reviewer queue.

        Results are ordered newest first.
        """

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        result = await self.session.execute(
            select(HumanDecisionModel)
            .where(
                HumanDecisionModel.status == "pending"
            )
            .order_by(
                HumanDecisionModel.created_at.desc()
            )
            .limit(limit)
        )

        return list(
            result.scalars().all()
        )

    # =========================================================
    # Get decision
    # =========================================================

    async def get(
        self,
        decision_id: UUID,
    ) -> HumanDecisionModel | None:
        result = await self.session.execute(
            select(HumanDecisionModel).where(
                HumanDecisionModel.id == decision_id
            )
        )

        return result.scalar_one_or_none()

    # =========================================================
    # Get pending decision for execution
    # =========================================================

    async def get_pending_for_execution(
        self,
        execution_id: UUID,
    ) -> HumanDecisionModel | None:
        result = await self.session.execute(
            select(HumanDecisionModel)
            .where(
                HumanDecisionModel.execution_id
                == execution_id
            )
            .where(
                HumanDecisionModel.status
                == "pending"
            )
            .order_by(
                HumanDecisionModel.created_at.desc()
            )
        )

        return result.scalars().first()

    # =========================================================
    # Get latest decision for execution
    # =========================================================

    async def get_latest_for_execution(
        self,
        execution_id: UUID,
    ) -> HumanDecisionModel | None:
        result = await self.session.execute(
            select(HumanDecisionModel)
            .where(
                HumanDecisionModel.execution_id
                == execution_id
            )
            .order_by(
                HumanDecisionModel.created_at.desc()
            )
        )

        return result.scalars().first()

    # =========================================================
    # Decide
    # =========================================================

    async def decide(
        self,
        *,
        decision_id: UUID,
        decision: str,
        feedback: str | None,
        decided_by: str | None,
    ) -> HumanDecisionModel:
        """
        Transition a pending decision to decided.
        """

        normalized_decision = (
            decision.strip().lower()
        )

        if (
            normalized_decision
            not in self.ALLOWED_DECISIONS
        ):
            allowed = ", ".join(
                sorted(
                    self.ALLOWED_DECISIONS
                )
            )

            raise ValueError(
                "Invalid human decision. "
                f"Expected one of: {allowed}."
            )

        human_decision = await self.get(
            decision_id
        )

        if human_decision is None:
            raise ValueError(
                "Human decision was not found."
            )

        if human_decision.status != "pending":
            raise ValueError(
                "This human decision has already "
                "been processed."
            )

        human_decision.status = "decided"

        human_decision.decision = (
            normalized_decision
        )

        human_decision.feedback = feedback

        human_decision.decided_by = (
            decided_by
        )

        human_decision.decided_at = (
            datetime.now(timezone.utc)
        )

        await self.session.flush()

        return human_decision