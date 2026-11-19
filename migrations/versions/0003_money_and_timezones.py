"""money: amount -> NUMERIC(12,2); all dates -> timestamptz

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-22

Two changes that are cheap now and expensive later.

1. deals.amount: DOUBLE PRECISION -> NUMERIC(12, 2)
   Binary floating point cannot represent even 0.10 exactly. On a single deal
   that is invisible; summed over thousands of deals the report drifts away
   from the accounting by cents nobody can explain. NUMERIC calculates in
   decimal digits. Existing values are rounded to cents. The column also
   becomes NOT NULL: a deal without an amount has amount 0, not "unknown".

2. All dates: TIMESTAMP -> TIMESTAMP WITH TIME ZONE
   UTC used to be stored without saying so. Such a value cannot be told apart
   from local time, and any comparison with "now" silently shifts by an hour
   or two (in Germany plus the daylight saving switch). For a CRM with
   deadlines that means reminders at the wrong time. Old values were written
   as UTC and are interpreted that way: USING created_at AT TIME ZONE 'UTC'.

On SQLite the same changes go through batch_alter_table (table rebuild),
because SQLite does not support ALTER COLUMN.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Date columns: table -> list of columns.
TZ_COLUMNS = {
    "users": ["created_at"],
    "clients": ["created_at", "updated_at"],
    "deals": ["created_at", "updated_at"],
    "tasks": ["due_date", "created_at", "updated_at"],
}


def _dialect() -> str:
    return op.get_context().dialect.name


def _convert_dates(to_timezone: bool) -> None:
    naive, aware = sa.DateTime(), sa.DateTime(timezone=True)
    new_type, old_type = (aware, naive) if to_timezone else (naive, aware)

    for table, columns in TZ_COLUMNS.items():
        if _dialect() == "postgresql":
            for column in columns:
                # USING is required: otherwise PostgreSQL does not know which
                # zone the old value was written in and assumes the server zone.
                using = (
                    f"{column} AT TIME ZONE 'UTC'"
                    if to_timezone
                    else f"{column} AT TIME ZONE 'UTC'"
                )
                op.alter_column(
                    table, column,
                    type_=new_type, existing_type=old_type,
                    postgresql_using=using,
                )
        else:
            with op.batch_alter_table(table) as batch:
                for column in columns:
                    batch.alter_column(column, type_=new_type, existing_type=old_type)


def upgrade() -> None:
    # A deal without an amount has amount 0. Must happen BEFORE NOT NULL.
    op.execute("UPDATE deals SET amount = 0 WHERE amount IS NULL")

    if _dialect() == "postgresql":
        op.alter_column(
            "deals", "amount",
            type_=sa.Numeric(12, 2), existing_type=sa.Float(),
            nullable=False, server_default="0",
            postgresql_using="ROUND(amount::numeric, 2)",
        )
    else:
        with op.batch_alter_table("deals") as batch:
            batch.alter_column(
                "amount",
                type_=sa.Numeric(12, 2), existing_type=sa.Float(),
                nullable=False, server_default="0",
            )

    _convert_dates(to_timezone=True)


def downgrade() -> None:
    _convert_dates(to_timezone=False)

    if _dialect() == "postgresql":
        op.alter_column(
            "deals", "amount",
            type_=sa.Float(), existing_type=sa.Numeric(12, 2),
            nullable=True, server_default="0.0",
            postgresql_using="amount::double precision",
        )
    else:
        with op.batch_alter_table("deals") as batch:
            batch.alter_column(
                "amount",
                type_=sa.Float(), existing_type=sa.Numeric(12, 2),
                nullable=True, server_default="0.0",
            )
