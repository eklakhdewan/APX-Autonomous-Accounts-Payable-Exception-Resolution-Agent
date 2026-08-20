from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apx.persistence.models import Base
from apx.persistence.config import get_persistence_settings


_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def init_database(
    database_url: Optional[str] = None,
    echo: bool = False,
    create_tables: bool = True,
) -> Engine:
    """Initialize the database engine and create tables.

    Args:
        database_url: SQLAlchemy database URL. If not provided, uses PersistenceSettings.
        echo: Enable SQL logging.
        create_tables: Whether to create tables on initialization.

    Returns:
        The SQLAlchemy engine.
    """
    global _engine, _session_factory

    # Always close existing engine if we're re-initializing with a different URL
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _session_factory = None

    persistence_settings = get_persistence_settings()

    if database_url is None:
        database_url = persistence_settings.get_database_url()

    if echo is False:
        echo = persistence_settings.echo_sql

    # Configure engine based on database type
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # Use StaticPool for in-memory SQLite to maintain connection
        if ":memory:" in database_url or "mode=memory" in database_url:
            _engine = create_engine(
                database_url,
                echo=echo,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        else:
            _engine = create_engine(database_url, echo=echo, connect_args=connect_args)

        # Enable foreign keys for SQLite
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        # PostgreSQL or other databases
        _engine = create_engine(
            database_url,
            echo=echo,
            pool_size=persistence_settings.pool_size,
            max_overflow=persistence_settings.max_overflow,
            pool_timeout=persistence_settings.pool_timeout,
            pool_recycle=persistence_settings.pool_recycle,
        )

    _session_factory = sessionmaker(
        bind=_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    if create_tables:
        Base.metadata.create_all(_engine)

    return _engine


def get_engine() -> Engine:
    """Get the database engine, initializing if necessary."""
    global _engine
    if _engine is None:
        init_database()
    return _engine


def get_session_factory() -> sessionmaker:
    """Get the session factory, initializing if necessary."""
    global _session_factory
    if _session_factory is None:
        init_database()
    return _session_factory


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_database() -> None:
    """Close the database engine and clean up."""
    global _engine, _session_factory
    if _engine:
        _engine.dispose()
        _engine = None
    _session_factory = None


def reset_database() -> None:
    """Drop all tables and recreate them. Useful for testing."""
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)