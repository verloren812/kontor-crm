"""
Alembic environment.

Alembic does NOT keep its own DATABASE_URL: it takes it from the same place as
the application, config.get_settings() (environment / .env). Change
DATABASE_URL once and both the app and the migrations use the same database,
SQLite or PostgreSQL.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make "import config" / "import models" work: add the project root
# (the folder with alembic.ini) to sys.path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import get_settings  # noqa: E402
import models  # noqa: E402  (imports ALL models so they are part of Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

# Used by --autogenerate to compare the models with the real database.
target_metadata = models.Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting to a database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and apply the migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detect column type changes in --autogenerate
            render_as_batch=connection.dialect.name == "sqlite",  # SQLite cannot ALTER COLUMN
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
