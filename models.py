from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    false,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator

from database import Base


def utcnow() -> datetime:
    """
    Current time WITH a time zone.

    ``datetime.utcnow()`` returns UTC without marking it as such, so the value
    cannot be told apart from local time and comparisons silently shift by an
    hour or two. For a CRM with task deadlines that is the worst kind of bug:
    nothing fails, reminders just fire at the wrong time. It is also
    deprecated since Python 3.12.
    """
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """
    TIMESTAMP WITH TIME ZONE that always returns aware datetimes in UTC.

    PostgreSQL handles time zones natively, SQLite does not: it stores the
    wall-clock time and drops the offset, so "10:00 Berlin" came back as
    "10:00 UTC". Converting to UTC on write and attaching UTC on read makes
    both databases behave the same.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:  # naive values are treated as UTC
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


# Money column: up to 10 digits before the decimal point and exactly 2 after.
# Float was a mistake here: 0.1 + 0.2 == 0.30000000000000004 in binary floating
# point, and over thousands of deals the report stops matching the accounting.
Money = Numeric(12, 2)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="manager", server_default="manager", nullable=False)
    created_at = Column(UTCDateTime(), default=utcnow)

    deals = relationship("Deal", back_populates="owner")
    clients = relationship("Client", back_populates="owner")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    # Stored normalized ("+491761234567"), so the UNIQUE constraint really
    # prevents duplicates regardless of how the number was typed.
    phone = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, index=True, nullable=True)
    # server_default as well as default: the ORM default does not apply to rows
    # inserted by migrations, raw SQL or imports.
    status = Column(String, default="new", server_default="new", nullable=False, index=True)
    created_at = Column(UTCDateTime(), default=utcnow)
    updated_at = Column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="clients")

    deals = relationship("Deal", back_populates="client", cascade="all, delete-orphan")

    # Indexes follow the real queries in crud.py (see migration 0002):
    # filter by owner_id, sort by id DESC.
    __table_args__ = (Index("ix_clients_owner_id", "owner_id", id.desc()),)


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    amount = Column(Money, default=0, server_default="0", nullable=False)
    stage = Column(String, default="new", server_default="new", nullable=False, index=True)
    created_at = Column(UTCDateTime(), default=utcnow)
    updated_at = Column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    client = relationship("Client", back_populates="deals")

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="deals")
    tasks = relationship("Task", back_populates="deal", cascade="all, delete-orphan")
    stage_history = relationship(
        "DealStageChange",
        back_populates="deal",
        cascade="all, delete-orphan",
        order_by="DealStageChange.id",
    )

    __table_args__ = (
        Index("ix_deals_owner_id", "owner_id", id.desc()),
        Index("ix_deals_owner_stage", "owner_id", "stage"),
        # PostgreSQL does not index foreign keys automatically.
        Index("ix_deals_client_id", "client_id"),
    )

    # Read-only helpers for the API responses (the routers eager-load these
    # relationships, so no extra query per row).
    @property
    def client_name(self):
        return self.client.name if self.client else None

    @property
    def owner_name(self):
        return self.owner.username if self.owner else None


class DealStageChange(Base):
    """
    One row per stage transition of a deal.

    ``updated_at`` alone only tells *that* a deal changed. With this table it is
    possible to calculate stage-to-stage conversion and how long deals stay in
    each stage.
    """

    __tablename__ = "deal_stage_changes"

    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    from_stage = Column(String, nullable=True)  # NULL for the initial stage
    to_stage = Column(String, nullable=False)
    changed_at = Column(UTCDateTime(), default=utcnow, nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    deal = relationship("Deal", back_populates="stage_history")
    changed_by = relationship("User")

    @property
    def changed_by_name(self):
        return self.changed_by.username if self.changed_by else None


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    due_date = Column(UTCDateTime(), nullable=True)
    is_done = Column(Boolean, default=False, server_default=false(), nullable=False)
    created_at = Column(UTCDateTime(), default=utcnow)
    updated_at = Column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    deal = relationship("Deal", back_populates="tasks")

    __table_args__ = (
        Index("ix_tasks_deal_id", "deal_id"),
        # Partial index: only open tasks, the only ones the dashboard looks at.
        Index("ix_tasks_pending_due", "due_date", postgresql_where=is_done == false()),
    )

    @property
    def deal_title(self):
        return self.deal.title if self.deal else None
