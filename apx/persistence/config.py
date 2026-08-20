from __future__ import annotations

from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PersistenceSettings(BaseSettings):
    """Persistence configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="APX_PERSISTENCE_",
        case_sensitive=False,
        extra="ignore",
    )

    # Database URL (SQLite for dev/test, PostgreSQL for production)
    database_url: Optional[str] = Field(
        default=None,
        description="SQLAlchemy database URL. If not set, uses SQLite in data directory.",
    )

    # SQLite-specific settings
    sqlite_data_dir: str = Field(
        default="apx/data/datasets",
        description="Directory for SQLite database file (development only).",
    )
    sqlite_filename: str = Field(
        default="apx.db",
        description="SQLite database filename (development only).",
    )

    # Connection pool settings (for PostgreSQL)
    pool_size: int = Field(default=5, ge=1, le=100)
    max_overflow: int = Field(default=10, ge=0, le=100)
    pool_timeout: int = Field(default=30, ge=1, le=300)
    pool_recycle: int = Field(default=3600, ge=0, le=86400)

    # Migration settings
    auto_migrate: bool = Field(
        default=True,
        description="Automatically run migrations on startup (development only).",
    )
    migration_dir: str = Field(
        default="apx/persistence/migrations",
        description="Alembic migration directory.",
    )

    # Echo SQL for debugging
    echo_sql: bool = Field(default=False)

    def get_database_url(self) -> str:
        """Get the resolved database URL."""
        if self.database_url:
            return self.database_url

        # Default to SQLite in data directory
        data_dir = Path(self.sqlite_data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{data_dir / self.sqlite_filename}"

    def is_sqlite(self) -> bool:
        """Check if using SQLite."""
        url = self.get_database_url()
        return url.startswith("sqlite")


# Global settings instance
_persistence_settings: Optional[PersistenceSettings] = None


def get_persistence_settings() -> PersistenceSettings:
    """Get or create the global persistence settings."""
    global _persistence_settings
    if _persistence_settings is None:
        _persistence_settings = PersistenceSettings()
    return _persistence_settings


def reset_persistence_settings() -> None:
    """Reset the global persistence settings."""
    global _persistence_settings
    _persistence_settings = None