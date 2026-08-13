from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Column,
    ForeignKey,
    JSON,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


subtask_dependencies = Table(
    "subtask_dependencies",
    Base.metadata,
    Column(
        "subtask_id",
        PGUUID(as_uuid=True),
        ForeignKey(
            "subtasks.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    Column(
        "dependency_id",
        PGUUID(as_uuid=True),
        ForeignKey(
            "subtasks.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
)


class SubTaskModel(Base):
    __tablename__ = "subtasks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
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

    description: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    assigned_specialist: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    expected_output: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    estimated_complexity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    required_inputs: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    execution: Mapped["ExecutionModel"] = relationship(
        "ExecutionModel",
        back_populates="subtasks",
    )

    dependencies: Mapped[list["SubTaskModel"]] = relationship(
        "SubTaskModel",
        secondary=subtask_dependencies,
        primaryjoin=id == subtask_dependencies.c.subtask_id,
        secondaryjoin=id == subtask_dependencies.c.dependency_id,
    )