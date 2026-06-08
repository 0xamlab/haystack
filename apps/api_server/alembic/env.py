"""Alembic environment configuration — synchronous connection for migrations."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import apps.api_server.models.api_key  # noqa: F401
import apps.api_server.models.organization  # noqa: F401
import apps.api_server.models.simulation_run  # noqa: F401
import apps.api_server.models.user  # noqa: F401
from apps.api_server.db.base import Base

config = context.config

# Use the sync DB URL (psycopg2/no driver prefix for local, or explicit driver)
db_url = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://angel@localhost:5432/decision_engine",
)
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live synchronous DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    assert url is not None, "DATABASE_URL_SYNC must be set"
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
