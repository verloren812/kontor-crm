"""deal_stage_changes: history of deal stage transitions

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-19

With only ``updated_at`` it is impossible to calculate stage-to-stage
conversion or how long deals stay in a stage. Existing deals get one entry
with their current stage, dated at their creation time.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deal_stage_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_stage", sa.String(), nullable=True),
        sa.Column("to_stage", sa.String(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )
    op.create_index("ix_deal_stage_changes_deal_id", "deal_stage_changes", ["deal_id"])

    op.execute(
        "INSERT INTO deal_stage_changes (deal_id, from_stage, to_stage, changed_at, changed_by_id) "
        "SELECT id, NULL, stage, COALESCE(created_at, CURRENT_TIMESTAMP), owner_id FROM deals"
    )


def downgrade() -> None:
    op.drop_index("ix_deal_stage_changes_deal_id", table_name="deal_stage_changes")
    op.drop_table("deal_stage_changes")
