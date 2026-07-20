"""Alembic migration environment for the industry-research-assistant.

The migration uses the same database connection as the running
application (``core.database.engine``) so no ``sqlalchemy.url`` needs
to be set in ``alembic.ini``. All application models must be imported
before ``target_metadata`` is referenced so ``autogenerate`` can
discover every table.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Let the migration find the ``app`` package without hard-coding an
# absolute path. The ``alembic.ini`` file already prepends ``.`` to
# ``sys.path``, but we make the import explicit so autogenerate works
# inside a CI checkout too.
_svcdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_appdir = os.path.join(_svcdir, "app")
if _appdir not in sys.path:
    sys.path.insert(0, _appdir)

# Load the project's .env so the database URL and other secrets are
# available when running ``alembic upgrade head`` outside Docker.
_dotenv_path = os.path.join(_svcdir, ".env")
if os.path.isfile(_dotenv_path):
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---- application imports (must happen before target_metadata) ----
from core.database import Base  # noqa: E402
import models  # noqa: E402 — registers all table mappings via side-effects

target_metadata = Base.metadata

# Alembic 1.18 moved autogenerate comparison into plugins. ORM comments are
# developer documentation rather than executable schema, so the drift gate
# intentionally enables every structural plugin while excluding comments.
AUTOGENERATE_PLUGINS = (
    "alembic.autogenerate.schemas",
    "alembic.autogenerate.tables",
    "alembic.autogenerate.types",
    "alembic.autogenerate.constraints",
    "alembic.autogenerate.defaults",
)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or ""
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        autogenerate_plugins=AUTOGENERATE_PLUGINS,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configured_url = config.get_main_option("sqlalchemy.url") or ""
    if configured_url:
        connectable = create_engine(configured_url, poolclass=pool.NullPool)
    else:
        from core.database import engine  # noqa: E402 — local import to avoid circularity

        connectable = engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            autogenerate_plugins=AUTOGENERATE_PLUGINS,
        )
        with context.begin_transaction():
            context.run_migrations()

    if configured_url:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
