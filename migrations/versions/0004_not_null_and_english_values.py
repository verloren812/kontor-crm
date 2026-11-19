"""NOT NULL + server defaults; English client statuses; richer deal pipeline

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-19

1. clients.status, deals.stage, tasks.is_done were declared with an ORM
   ``default`` but stayed nullable. The ORM default does not apply to rows
   written by migrations, raw SQL or imports, so NULLs could appear, and the
   response schemas (which declare these fields as required) then failed with
   a 500. Existing NULLs are filled in first, then the columns become
   NOT NULL with a server-side default.

2. Client statuses were stored in Russian ("Новый") while deal stages were in
   English ("new"). Everything is English now. The pipeline also gets the
   usual B2B stages; the old "in_progress" stage maps to "qualified".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUS_MAP = {
    "Новый": "new",
    "В работе": "in_progress",
    "Постоянный": "regular",
    "Отказ": "rejected",
}
STAGE_MAP = {"in_progress": "qualified"}


def _remap(table: str, column: str, mapping: dict) -> None:
    statement = sa.text(f"UPDATE {table} SET {column} = :new WHERE {column} = :old")
    for old, new in mapping.items():
        op.execute(statement.bindparams(old=old, new=new))


def upgrade() -> None:
    _remap("clients", "status", STATUS_MAP)
    _remap("deals", "stage", STAGE_MAP)

    op.execute("UPDATE clients SET status = 'new' WHERE status IS NULL")
    op.execute("UPDATE deals SET stage = 'new' WHERE stage IS NULL")
    op.execute("UPDATE tasks SET is_done = false WHERE is_done IS NULL")

    # batch_alter_table: plain ALTER on PostgreSQL, table rebuild on SQLite
    # (SQLite cannot ALTER COLUMN).
    with op.batch_alter_table("clients") as batch:
        batch.alter_column("status", existing_type=sa.String(), nullable=False, server_default="new")
    with op.batch_alter_table("deals") as batch:
        batch.alter_column("stage", existing_type=sa.String(), nullable=False, server_default="new")
    with op.batch_alter_table("tasks") as batch:
        batch.alter_column("is_done", existing_type=sa.Boolean(), nullable=False, server_default=sa.false())


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.alter_column("is_done", existing_type=sa.Boolean(), nullable=True, server_default=sa.false())
    with op.batch_alter_table("deals") as batch:
        batch.alter_column("stage", existing_type=sa.String(), nullable=True, server_default="new")
    with op.batch_alter_table("clients") as batch:
        batch.alter_column("status", existing_type=sa.String(), nullable=True, server_default="Новый")

    # New pipeline stages have no equivalent in the old version.
    _remap("deals", "stage", {"qualified": "in_progress", "proposal": "in_progress", "negotiation": "in_progress"})
    _remap("clients", "status", {new: old for old, new in STATUS_MAP.items()})
