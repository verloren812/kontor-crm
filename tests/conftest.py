"""
Shared test fixtures.

Every test gets a FRESH database and there is no dependency between tests.
By default it is SQLite in memory. Set TEST_DATABASE_URL to run the same
suite against PostgreSQL (CI does both):

    TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost/crm_test pytest
"""
import os
import sys

# Make the project modules importable no matter where pytest is started from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Must be set BEFORE database is imported, otherwise the URL from .env is used.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-hs256")

from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import crud  # noqa: E402
import main  # noqa: E402
import models  # noqa: E402
import schemas  # noqa: E402
import security  # noqa: E402
from database import Base, get_db  # noqa: E402
from enums import Role  # noqa: E402

ADMIN_PASSWORD = "admin-password-1"
MANAGER_PASSWORD = "manager-password-1"
OTHER_PASSWORD = "other-password-1"


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _make_engine():
    if TEST_DATABASE_URL:
        return create_engine(TEST_DATABASE_URL)
    # StaticPool: every connection sees the same in-memory database;
    # otherwise each new connection would get an empty one.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


@pytest.fixture()
def db():
    engine = _make_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db):
    main.app.dependency_overrides[get_db] = lambda: db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


def create_user(db, username: str, password: str, role: Role) -> models.User:
    return crud.create_user(db, schemas.UserCreate(username=username, password=password, role=role))


def auth_header(user: models.User) -> dict:
    return {"Authorization": f"Bearer {security.create_access_token(user.id)}"}


@pytest.fixture()
def admin(db) -> models.User:
    return create_user(db, "boss", ADMIN_PASSWORD, Role.ADMIN)


@pytest.fixture()
def manager(db) -> models.User:
    return create_user(db, "anna", MANAGER_PASSWORD, Role.MANAGER)


@pytest.fixture()
def other_manager(db) -> models.User:
    return create_user(db, "jonas", OTHER_PASSWORD, Role.MANAGER)


@pytest.fixture()
def admin_header(admin) -> dict:
    return auth_header(admin)


@pytest.fixture()
def manager_header(manager) -> dict:
    return auth_header(manager)


_phone_counter = iter(range(1000, 100000))


def make_client(db, owner=None, name="Acme GmbH", phone=None, **extra) -> models.Client:
    phone = phone or f"+4915100{next(_phone_counter):06d}"
    return crud.create_client(
        db,
        schemas.ClientCreate(name=name, phone=phone, **extra),
        owner_id=owner.id if owner else None,
    )


def make_deal(db, client_obj, owner=None, title="Website", amount="1000", stage="new") -> models.Deal:
    return crud.create_deal(
        db,
        schemas.DealCreate(title=title, amount=Decimal(amount), stage=stage, client_id=client_obj.id),
        owner_id=owner.id if owner else None,
    )


def make_task(db, deal, title="Call back", due_date=None, is_done=False) -> models.Task:
    task = crud.create_task(db, schemas.TaskCreate(title=title, due_date=due_date, deal_id=deal.id))
    if is_done:
        crud.update_task(db, task, schemas.TaskUpdate(is_done=True))
    return task
