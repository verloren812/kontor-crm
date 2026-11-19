"""
Migrations: a fresh database can be built from scratch, the result matches
models.py, and the data migrations convert old values.

A broken baseline migration once made it impossible to deploy to a new
server at all; these tests make sure that cannot happen silently again.
"""
import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

import models

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture()
def alembic_db(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'migrations.db'}"
    if url.startswith("postgresql"):
        # Start from an empty schema: the migrations must build everything themselves.
        with create_engine(url).begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    monkeypatch.setenv("DATABASE_URL", url)
    import config

    config.get_settings.cache_clear()
    cfg = Config(os.path.join(PROJECT_ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(PROJECT_ROOT, "migrations"))
    engine = create_engine(url)
    yield cfg, engine
    engine.dispose()
    config.get_settings.cache_clear()


def test_upgrade_from_scratch_matches_models(alembic_db):
    cfg, engine = alembic_db
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), models.Base.metadata)
    assert diff == [], f"models.py and migrations differ: {diff}"


def test_downgrade_to_base_and_back(alembic_db):
    cfg, _ = alembic_db
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_old_values_are_converted(alembic_db):
    """Data written by version 0003 (Russian statuses, NULLs) survives the upgrade."""
    cfg, engine = alembic_db
    command.upgrade(cfg, "0003")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id, username, hashed_password, role) VALUES (1, 'u', 'x', 'manager')"))
        connection.execute(text(
            "INSERT INTO clients (id, name, phone, status, owner_id) VALUES "
            "(1, 'a', '+491', 'Постоянный', 1), (2, 'b', '+492', NULL, 1)"
        ))
        connection.execute(text(
            "INSERT INTO deals (id, title, amount, stage, client_id, owner_id) VALUES "
            "(1, 'd', 10, 'in_progress', 1, 1), (2, 'e', 20, NULL, 2, 1)"
        ))
        connection.execute(text("INSERT INTO tasks (id, title, is_done, deal_id) VALUES (1, 't', NULL, 1)"))

    command.upgrade(cfg, "head")

    with engine.connect() as connection:
        statuses = dict(connection.execute(text("SELECT id, status FROM clients")).all())
        stages = dict(connection.execute(text("SELECT id, stage FROM deals")).all())
        is_done = connection.execute(text("SELECT is_done FROM tasks")).scalar()
        history = connection.execute(text("SELECT deal_id, to_stage FROM deal_stage_changes ORDER BY deal_id")).all()

    assert statuses == {1: "regular", 2: "new"}
    assert stages == {1: "qualified", 2: "new"}
    assert is_done in (0, False)  # SQLite returns 0, PostgreSQL False
    assert [tuple(row) for row in history] == [(1, "qualified"), (2, "new")]
