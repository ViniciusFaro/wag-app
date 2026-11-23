"""Use the same configured database for the CLI and the application lifespan."""

from alembic import context

from API.FASTAPI.app.db import models  # noqa: F401 - register mapped tables
from API.FASTAPI.app.db.base import Base
from API.FASTAPI.app.db.session import engine

config = context.config
target_metadata = Base.metadata


def run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=engine.url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    run_migrations(config.attributes["connection"])
else:
    with engine.connect() as connection:
        run_migrations(connection)
