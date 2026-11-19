"""All database access. Routers never build queries themselves."""
from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

import models
import schemas
import security
from enums import DealStage, Role, stage_flags


class DuplicatePhoneError(Exception):
    """A client with this (normalized) phone number already exists."""


def _owned_or_unassigned(query, model, owner_id: Optional[int]):
    """
    Visibility rule for managers: their own records plus unassigned ones
    (owner_id IS NULL). For admins (owner_id=None on input) no filter is applied.
    """
    if owner_id is not None:
        query = query.filter((model.owner_id == owner_id) | (model.owner_id.is_(None)))
    return query


def _apply_changes(db_obj, data) -> dict:
    """Copy the fields that were actually sent in a PATCH request."""
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(db_obj, field, value)
    return changes


# --- Users ---

def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.get(models.User, user_id)


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[models.User]:
    return db.query(models.User).order_by(models.User.id).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(
        username=user.username,
        hashed_password=security.get_password_hash(user.password),
        role=Role(user.role).value,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_role(db: Session, db_user: models.User, role: str) -> models.User:
    db_user.role = role
    db.commit()
    db.refresh(db_user)
    return db_user


def count_admins(db: Session) -> int:
    """Needed so that the last admin cannot lose the role."""
    return db.query(models.User).filter(models.User.role == Role.ADMIN.value).count()


# --- Clients ---

def get_client(db: Session, client_id: int) -> Optional[models.Client]:
    return db.get(models.Client, client_id)


def get_client_by_phone(db: Session, phone: str) -> Optional[models.Client]:
    return db.query(models.Client).filter(models.Client.phone == phone).first()


def get_clients(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    search: Optional[str] = None,
    owner_id: Optional[int] = None,
) -> list[models.Client]:
    query = db.query(models.Client)
    if status:
        query = query.filter(models.Client.status == status)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            models.Client.name.ilike(like)
            | models.Client.phone.ilike(like)
            | models.Client.email.ilike(like)
        )
    query = _owned_or_unassigned(query, models.Client, owner_id)
    return query.order_by(models.Client.id.desc()).offset(skip).limit(limit).all()


def _commit_client(db: Session, db_client: models.Client) -> models.Client:
    """
    Commit and translate the UNIQUE violation on phone.

    The router checks for a duplicate first, but two parallel requests can
    both pass that check; the database constraint is the real guarantee.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicatePhoneError from exc
    db.refresh(db_client)
    return db_client


def create_client(db: Session, client: schemas.ClientCreate, owner_id: Optional[int]) -> models.Client:
    db_client = models.Client(
        name=client.name,
        phone=client.phone,
        email=client.email,
        status=client.status,
        owner_id=owner_id,
    )
    db.add(db_client)
    return _commit_client(db, db_client)


def update_client(db: Session, db_client: models.Client, data: schemas.ClientUpdate) -> models.Client:
    _apply_changes(db_client, data)
    return _commit_client(db, db_client)


def delete_client(db: Session, db_client: models.Client) -> None:
    db.delete(db_client)
    db.commit()


# --- Deals ---

def _deal_query(db: Session):
    # client and owner are shown in every deal response (client_name,
    # owner_name); loading them in the same query avoids N+1 selects.
    return db.query(models.Deal).options(
        joinedload(models.Deal.client), joinedload(models.Deal.owner)
    )


def get_deal(db: Session, deal_id: int) -> Optional[models.Deal]:
    return _deal_query(db).filter(models.Deal.id == deal_id).first()


def get_deals(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    stage: Optional[str] = None,
    client_id: Optional[int] = None,
    owner_id: Optional[int] = None,
) -> list[models.Deal]:
    query = _deal_query(db)
    if stage:
        query = query.filter(models.Deal.stage == stage)
    if client_id:
        query = query.filter(models.Deal.client_id == client_id)
    query = _owned_or_unassigned(query, models.Deal, owner_id)
    return query.order_by(models.Deal.id.desc()).offset(skip).limit(limit).all()


def _record_stage(deal: models.Deal, from_stage, to_stage, user_id) -> None:
    deal.stage_history.append(
        models.DealStageChange(from_stage=from_stage, to_stage=to_stage, changed_by_id=user_id)
    )


def create_deal(db: Session, deal: schemas.DealCreate, owner_id: Optional[int]) -> models.Deal:
    db_deal = models.Deal(
        title=deal.title,
        amount=deal.amount,
        stage=deal.stage,
        client_id=deal.client_id,
        owner_id=owner_id,
    )
    _record_stage(db_deal, None, deal.stage, owner_id)
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def update_deal(
    db: Session, db_deal: models.Deal, data: schemas.DealUpdate, user_id: Optional[int] = None
) -> models.Deal:
    old_stage = db_deal.stage
    changes = _apply_changes(db_deal, data)
    if "stage" in changes and changes["stage"] != old_stage:
        _record_stage(db_deal, old_stage, changes["stage"], user_id)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def delete_deal(db: Session, db_deal: models.Deal) -> None:
    db.delete(db_deal)
    db.commit()


def get_stage_history(db: Session, deal_id: int) -> list[models.DealStageChange]:
    return (
        db.query(models.DealStageChange)
        .options(joinedload(models.DealStageChange.changed_by))
        .filter(models.DealStageChange.deal_id == deal_id)
        .order_by(models.DealStageChange.id)
        .all()
    )


# --- Tasks ---

def _task_query(db: Session):
    return db.query(models.Task).options(joinedload(models.Task.deal))


def get_task(db: Session, task_id: int) -> Optional[models.Task]:
    return _task_query(db).filter(models.Task.id == task_id).first()


def get_tasks(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    deal_id: Optional[int] = None,
    is_done: Optional[bool] = None,
    owner_id: Optional[int] = None,
) -> list[models.Task]:
    query = _task_query(db).join(models.Task.deal)
    if deal_id:
        query = query.filter(models.Task.deal_id == deal_id)
    if is_done is not None:
        query = query.filter(models.Task.is_done == is_done)
    query = _owned_or_unassigned(query, models.Deal, owner_id)
    # Tasks without a deadline go last instead of first.
    return (
        query.order_by(models.Task.due_date.is_(None), models.Task.due_date, models.Task.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_task(db: Session, task: schemas.TaskCreate) -> models.Task:
    db_task = models.Task(
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        deal_id=task.deal_id,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def update_task(db: Session, db_task: models.Task, data: schemas.TaskUpdate) -> models.Task:
    _apply_changes(db_task, data)
    db.commit()
    db.refresh(db_task)
    return db_task


def delete_task(db: Session, db_task: models.Task) -> None:
    db.delete(db_task)
    db.commit()


# --- Analytics ---

def get_dashboard_data(db: Session, owner_id: Optional[int] = None, overdue_limit: int = 50) -> dict:
    """
    owner_id=None -> figures for the whole company (admin).
    owner_id=<id> -> only the deals this manager can see.

    All aggregates are computed by the database (GROUP BY / SUM) instead of
    loading every deal into Python and summing in a loop.
    """
    stage_rows = (
        _owned_or_unassigned(
            db.query(
                models.Deal.stage.label("stage"),
                func.count(models.Deal.id).label("count"),
                func.coalesce(func.sum(models.Deal.amount), 0).label("total_amount"),
            ),
            models.Deal,
            owner_id,
        )
        .group_by(models.Deal.stage)
        .all()
    )

    order = {stage.value: index for index, stage in enumerate(DealStage)}
    deals_by_stage = []
    for row in sorted(stage_rows, key=lambda r: (order.get(r.stage, len(order)), r.stage)):
        is_won, is_closed = stage_flags(row.stage)
        deals_by_stage.append(
            {
                "stage": row.stage,
                "count": row.count,
                # float only for JSON output; the database did the exact sum.
                "total_amount": float(row.total_amount),
                "is_won": is_won,
                "is_closed": is_closed,
            }
        )

    total_deals_count = sum(row["count"] for row in deals_by_stage)
    total_amount = sum(row["total_amount"] for row in deals_by_stage)
    won_amount = sum(row["total_amount"] for row in deals_by_stage if row["is_won"])
    open_amount = sum(row["total_amount"] for row in deals_by_stage if not row["is_closed"])
    won_count = sum(row["count"] for row in deals_by_stage if row["is_won"])
    closed_count = sum(row["count"] for row in deals_by_stage if row["is_closed"])
    win_rate = round(won_count / closed_count, 4) if closed_count else None

    clients_count = _owned_or_unassigned(
        db.query(func.count(models.Client.id)), models.Client, owner_id
    ).scalar()

    # Task deadlines are timestamptz; comparing them with a naive value fails
    # on PostgreSQL instead of silently assuming UTC.
    now = models.utcnow()
    pending = _owned_or_unassigned(
        _task_query(db).join(models.Task.deal), models.Deal, owner_id
    ).filter(models.Task.is_done == False)  # noqa: E712  (matches the partial index condition)

    overdue_query = pending.filter(models.Task.due_date < now)
    overdue_total = overdue_query.count()
    overdue_tasks = overdue_query.order_by(models.Task.due_date).limit(overdue_limit).all()

    upcoming_tasks = (
        pending.filter((models.Task.due_date >= now) | (models.Task.due_date.is_(None)))
        .order_by(models.Task.due_date.is_(None), models.Task.due_date)
        .limit(10)
        .all()
    )

    result = {
        "deals_by_stage": deals_by_stage,
        "total_deals_count": total_deals_count,
        "total_amount": total_amount,
        "open_amount": open_amount,
        "won_amount": won_amount,
        "win_rate": win_rate,
        "clients_count": clients_count,
        "overdue_tasks": overdue_tasks,
        "overdue_total": overdue_total,
        "upcoming_tasks": upcoming_tasks,
        "revenue_by_manager": None,
    }

    if owner_id is None:
        # One LEFT JOIN with GROUP BY instead of a SELECT per deal (N+1).
        won_sum = func.coalesce(
            func.sum(case((models.Deal.stage == DealStage.WON.value, models.Deal.amount), else_=0)), 0
        )
        total_sum = func.coalesce(func.sum(models.Deal.amount), 0)
        manager_rows = (
            db.query(
                models.Deal.owner_id.label("manager_id"),
                models.User.username.label("username"),
                func.count(models.Deal.id).label("deals_count"),
                total_sum.label("total_amount"),
                won_sum.label("won_amount"),
            )
            .outerjoin(models.User, models.User.id == models.Deal.owner_id)
            .group_by(models.Deal.owner_id, models.User.username)
            .order_by(won_sum.desc(), total_sum.desc())
            .all()
        )
        result["revenue_by_manager"] = [
            {
                "manager_id": row.manager_id,
                "username": row.username or "Unassigned",
                "deals_count": row.deals_count,
                "total_amount": float(row.total_amount),
                "won_amount": float(row.won_amount),
            }
            for row in manager_rows
        ]

    return result
