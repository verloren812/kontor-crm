"""indexes: foreign keys and composite indexes for the real queries

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22

Unlike MySQL, PostgreSQL does NOT index foreign keys automatically. The
baseline indexed status/stage/phone but not owner_id, which is exactly what
the main query of the system filters on ("show my clients / deals"). Without
an index that is a full table scan for every request of every manager.

Indexes follow the actual queries in crud.py, not "just in case": every extra
index slows down INSERT and UPDATE.

  get_clients()  -> WHERE owner_id = ? ORDER BY id DESC
  get_deals()    -> WHERE owner_id = ? [AND stage = ?] ORDER BY id DESC
  get_tasks()    -> JOIN deals ON tasks.deal_id = deals.id
  dashboard      -> WHERE is_done = false AND due_date < now() ORDER BY due_date

On a live database with data, index creation locks the table for writes. For
large tables build them manually with CREATE INDEX CONCURRENTLY.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- clients ---
    # Column order matters: first the filter column (owner_id), then the sort
    # column (id DESC). PostgreSQL then reads rows from the index already in
    # the right order and skips a separate sort step.
    op.create_index(
        "ix_clients_owner_id",
        "clients",
        ["owner_id", sa.text("id DESC")],
        unique=False,
    )

    # --- deals ---
    op.create_index(
        "ix_deals_owner_id",
        "deals",
        ["owner_id", sa.text("id DESC")],
        unique=False,
    )
    # For the "my deals in stage X" filter.
    op.create_index("ix_deals_owner_stage", "deals", ["owner_id", "stage"], unique=False)
    # Foreign key: used by the JOIN and keeps deleting a client from scanning deals.
    op.create_index("ix_deals_client_id", "deals", ["client_id"], unique=False)

    # --- tasks ---
    op.create_index("ix_tasks_deal_id", "tasks", ["deal_id"], unique=False)
    # Partial index: only open tasks. The dashboard only looks at those, and
    # finished tasks will soon be 95% of the table.
    op.create_index(
        "ix_tasks_pending_due",
        "tasks",
        ["due_date"],
        unique=False,
        postgresql_where=sa.text("is_done = false"),
    )

    # An index on a single boolean column is almost useless (two values);
    # ix_tasks_pending_due does its job now.
    op.drop_index("ix_tasks_is_done", table_name="tasks")

    # Duplicate indexes on primary keys (ix_users_id, ...). A PRIMARY KEY
    # already creates a unique index; a second one only slows down writes.
    # They made the baseline fail on a clean database ("index ix_users_id
    # already exists"). New databases do not have them, hence IF EXISTS.
    for index_name in ("ix_users_id", "ix_clients_id", "ix_deals_id", "ix_tasks_id"):
        op.execute(f"DROP INDEX IF EXISTS {index_name}")


def downgrade() -> None:
    # The duplicate primary key indexes are intentionally not restored.
    op.create_index("ix_tasks_is_done", "tasks", ["is_done"], unique=False)
    op.drop_index("ix_tasks_pending_due", table_name="tasks")
    op.drop_index("ix_tasks_deal_id", table_name="tasks")
    op.drop_index("ix_deals_client_id", table_name="deals")
    op.drop_index("ix_deals_owner_stage", table_name="deals")
    op.drop_index("ix_deals_owner_id", table_name="deals")
    op.drop_index("ix_clients_owner_id", table_name="clients")
