from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    Float,
    Boolean,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExecutionModel(Base):
    __tablename__ = "executions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )

    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="planned",
    )

    # ---------------------------------------------------------
    # Human-in-the-loop / escalation metadata
    # ---------------------------------------------------------

    escalation_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    human_escalation_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    escalation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    specialist_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    confidence_threshold: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # ---------------------------------------------------------
    # HITL state
    # ---------------------------------------------------------

    human_decision_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    human_decision: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    human_feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    human_decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Workflow resume information
    # ---------------------------------------------------------

    resume_node: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    resume_subtask_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
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

    task: Mapped["TaskModel"] = relationship(
        "TaskModel",
        back_populates="executions",
    )

    subtasks: Mapped[list["SubTaskModel"]] = relationship(
        "SubTaskModel",
        back_populates="execution",
        cascade="all, delete-orphan",
    )

    reviews: Mapped[list["ReviewModel"]] = relationship(
        "ReviewModel",
        back_populates="execution",
        cascade="all, delete-orphan",
    )

    human_decisions: Mapped[list["HumanDecisionModel"]] = relationship(
        "HumanDecisionModel",
        back_populates="execution",
        cascade="all, delete-orphan",
    )