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

    Platform rule for PostgreSQL container integration:
      - ALWAYS read connection from db_connection.txt (typically contains: 'psql postgresql://...').

    Env vars are supported as a fallback for local development, but the canonical
    connection should come from db_connection.txt.

    Supported env overrides:
      - DB_CONNECTION_FILE: absolute or relative path to db_connection.txt
      - POSTGRES_URL: full SQLAlchemy-compatible URL (fallback only)
      - POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_HOST/POSTGRES_PORT/POSTGRES_DB (fallback only)
    """
    # Prefer an explicit path if provided by the orchestrator/runtime.
    explicit = os.getenv("DB_CONNECTION_FILE")
    candidate_paths = []
    if explicit:
        candidate_paths.append(Path(explicit))

    # Then check common repo/container locations.
    candidate_paths.extend(
        [
            # workspace root of the backend container
            Path(__file__).resolve().parents[2] / "db_connection.txt",  # .../zwiggy_backend/db_connection.txt
            # monorepo root (one level above zwiggy_backend/)
            Path(__file__).resolve().parents[3] / "db_connection.txt",
            # current working directory
            Path("db_connection.txt"),
            # sibling database container path in this multi-workspace setup
            Path(__file__).resolve().parents[4] / "gourmet-hub-321222-321232" / "zwiggy_database" / "db_connection.txt",
        ]
    )

    for p in candidate_paths:
        try:
            if p and p.exists():
                content = p.read_text(encoding="utf-8")
                url = _parse_psql_command_to_url(content)
                if url:
                    return url
        except Exception:
            # Ignore and continue to env fallback
            pass

    # ENV fallback (useful in some dev/CI setups). Do not assume values beyond
    # their presence; only build a connection string if all required fields exist.
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
        "Expected db_connection.txt with a 'psql postgresql://...' line (preferred), "
        "optionally pointed to by DB_CONNECTION_FILE, or POSTGRES_URL, "
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
