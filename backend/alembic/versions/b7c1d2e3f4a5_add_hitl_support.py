"""add HITL support

Revision ID: b7c1d2e3f4a5
Revises: a1dac09fca43
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c1d2e3f4a5"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "a1dac09fca43"

branch_labels = None

depends_on = None


def upgrade() -> None:

    # ---------------------------------------------------------
    # Execution escalation metadata
    # ---------------------------------------------------------

    op.add_column(
        "executions",
        sa.Column(
            "escalation_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "executions",
        sa.Column(
            "human_escalation_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "executions",
        sa.Column(
            "escalation_reason",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "executions",
        sa.Column(
            "specialist_confidence",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "executions",
        sa.Column(
            "confidence_threshold",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "executions",
        sa.Column(
            "human_decision_status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
    )

    op.add_column(
        "executions",
        sa.Column(
            "human_decision",
            sa.String(length=30),
            nullable=True,
        ),
    )

    op.add_column(
        "executions",
        sa.Column(
            "human_feedback",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "executions",
        sa.Column(
            "human_decided_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "executions",
        sa.Column(
            "resume_node",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "executions",
        sa.Column(
            "resume_subtask_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # ---------------------------------------------------------
    # Human decisions
    # ---------------------------------------------------------

    op.create_table(
        "human_decisions",

        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "execution_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),

        sa.Column(
            "decision",
            sa.String(length=30),
            nullable=True,
        ),

        sa.Column(
            "feedback",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "decided_by",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_human_decisions_execution_id"),
        "human_decisions",
        ["execution_id"],
        unique=False,
    )


def downgrade() -> None:

    op.drop_index(
        op.f("ix_human_decisions_execution_id"),
        table_name="human_decisions",
    )

    op.drop_table(
        "human_decisions"
    )

    op.drop_column(
        "executions",
        "resume_subtask_id",
    )

    op.drop_column(
        "executions",
        "resume_node",
    )

    op.drop_column(
        "executions",
        "human_decided_at",
    )

    op.drop_column(
        "executions",
        "human_feedback",
    )

    op.drop_column(
        "executions",
        "human_decision",
    )

    op.drop_column(
        "executions",
        "human_decision_status",
    )

    op.drop_column(
        "executions",
        "confidence_threshold",
    )

    op.drop_column(
        "executions",
        "specialist_confidence",
    )

    op.drop_column(
        "executions",
        "escalation_reason",
    )

    op.drop_column(
        "executions",
        "human_escalation_required",
    )

    op.drop_column(
        "executions",
        "escalation_required",
    )