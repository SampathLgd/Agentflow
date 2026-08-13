"""add hitl review context

Revision ID: 76537556b265
Revises: b7c1d2e3f4a5
Create Date: 2026-08-11 21:20:14.946814

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "76537556b265"
down_revision: Union[str, Sequence[str], None] = "b7c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "human_decisions",
        sa.Column(
            "approval_level",
            sa.String(length=30),
            nullable=True,
        ),
    )

    op.add_column(
        "human_decisions",
        sa.Column(
            "escalation_trigger",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "human_decisions",
        sa.Column(
            "proposed_action",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "human_decisions",
        sa.Column(
            "review_context",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "human_decisions",
        "review_context",
    )

    op.drop_column(
        "human_decisions",
        "proposed_action",
    )

    op.drop_column(
        "human_decisions",
        "escalation_trigger",
    )

    op.drop_column(
        "human_decisions",
        "approval_level",
    )