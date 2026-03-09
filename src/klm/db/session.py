from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from dotenv import load_dotenv
load_dotenv()


@dataclass(frozen=True)
class DatabaseHealth:
    ok: bool
    message: str


def create_db_engine(
    database_url: str | None = None,
    *,
    echo: bool | None = None,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    pool_timeout: int | None = None,
    pool_recycle: int | None = None,
    pool_pre_ping: bool = True,
) -> Engine:
    """Create a SQLAlchemy engine.

    Supported env vars:
    - DATABASE_URL
    - DB_ECHO
    - DB_POOL_SIZE
    - DB_MAX_OVERFLOW
    - DB_POOL_TIMEOUT
    - DB_POOL_RECYCLE
    - DB_POOL_PRE_PING

    Notes:
    - pool_pre_ping helps avoid stale/broken connections
    - pool_recycle helps with DB connections closed by server/network
    - for Alembic, reuse the same DATABASE_URL / engine configuration pattern
    """

    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    if echo is None:
        echo = os.getenv("DB_ECHO", "false").lower() in {"1", "true", "yes", "on"}

    if pool_size is None:
        pool_size = int(os.getenv("DB_POOL_SIZE", "5"))

    if max_overflow is None:
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))

    if pool_timeout is None:
        pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))

    if pool_recycle is None:
        pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "1800"))

    pool_pre_ping_env = os.getenv("DB_POOL_PRE_PING")
    if pool_pre_ping_env is not None:
        pool_pre_ping = pool_pre_ping_env.lower() in {"1", "true", "yes", "on"}

    return create_engine(
        url,
        future=True,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def test_connection(engine: Engine) -> DatabaseHealth:
    """Run a minimal DB connectivity check."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return DatabaseHealth(ok=True, message="Database connection is healthy")
    except SQLAlchemyError as exc:
        return DatabaseHealth(ok=False, message=f"Database connection failed: {exc}")


def create_engine_and_test(database_url: str | None = None) -> tuple[Engine, DatabaseHealth]:
    """Helper useful for CLI health-check commands."""
    engine = create_db_engine(database_url)
    health = test_connection(engine)
    return engine, health