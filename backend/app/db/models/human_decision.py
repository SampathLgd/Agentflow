from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HumanDecisionModel(Base):
    __tablename__ = "human_decisions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    execution_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "executions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Decision lifecycle
    # ---------------------------------------------------------

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    decision: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ---------------------------------------------------------
    # HITL escalation metadata
    # ---------------------------------------------------------

    approval_level: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    escalation_trigger: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    proposed_action: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    review_context: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Audit information
    # ---------------------------------------------------------

    decided_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    execution: Mapped["ExecutionModel"] = relationship(
        "ExecutionModel",
        back_populates="human_decisions",
    )
