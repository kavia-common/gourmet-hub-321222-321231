import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _parse_psql_command_to_url(psql_command: str) -> Optional[str]:
    """
    Parse a db_connection.txt line that typically looks like:
      psql postgresql://user:pass@host:port/db

    Returns:
        The postgresql URL if found, else None.
    """
    if not psql_command:
        return None
    parts = psql_command.strip().split()
    for p in parts:
        if p.startswith("postgresql://") or p.startswith("postgres://"):
            return p
    return None


def _read_database_url() -> str:
    """
    Read database connection URL.

    Per platform rules, prefer db_connection.txt. If not present, fall back to env vars.
    """
    # Prefer db_connection.txt (expected for PostgreSQL container integration).
    candidate_paths = [
        Path(__file__).resolve().parents[3] / "db_connection.txt",  # repo root-ish
        Path(__file__).resolve().parents[2] / "db_connection.txt",  # zwiggy_backend/
        Path("db_connection.txt"),
    ]
    for p in candidate_paths:
        try:
            if p.exists():
                content = p.read_text(encoding="utf-8")
                url = _parse_psql_command_to_url(content)
                if url:
                    return url
        except Exception:
            # Ignore and continue to env fallback
            pass

    # ENV fallback (orchestrator provides these via .env)
    # NOTE: Do not assume values, only build a connection string if all exist.
    pg_url = os.getenv("POSTGRES_URL")
    if pg_url:
        return pg_url

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT")
    db = os.getenv("POSTGRES_DB")
    if user and password and port and db:
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    raise RuntimeError(
        "Database connection is not configured. "
        "Expected db_connection.txt with a 'psql postgresql://...' line, or POSTGRES_URL, "
        "or POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_PORT/POSTGRES_DB env vars."
    )


DATABASE_URL = _read_database_url()

# SQLAlchemy engine/session factory.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy Session and ensures it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for scripts or background jobs."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
