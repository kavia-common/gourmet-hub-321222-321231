from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.db import engine
from src.api.models import Base


# PUBLIC_INTERFACE
def init_db() -> None:
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def db_healthcheck(db: Session) -> None:
    """Run a simple query to validate DB connectivity."""
    db.execute(text("SELECT 1"))
