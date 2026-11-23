"""One SQLAlchemy session per request or background analysis transaction."""

from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import ROOT, settings


def make_engine(database_url: str):
    url = make_url(database_url)
    options = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        if url.database and url.database != ":memory:":
            path = Path(url.database)
            if not path.is_absolute():
                path = ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=path.as_posix())
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
    result = create_engine(url, **options)
    if url.get_backend_name() == "sqlite":

        @event.listens_for(result, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return result


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database():
    """Apply versioned migrations before accepting uploads or database requests."""
    config = Config(str(ROOT / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
