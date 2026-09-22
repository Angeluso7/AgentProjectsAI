import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Agregar ruta del backend al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.settings import settings
from app.db.session import Base
from app.db.models import * # Importa todos los modelos

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import alembic.ddl.impl
import sqlalchemy as sa
from sqlalchemy import text

# Ensure alembic_version table uses String(128) for long descriptive revision identifiers
_orig_version_table_impl = alembic.ddl.impl.DefaultImpl.version_table_impl

def _custom_version_table_impl(self, *, version_table, version_table_schema, version_table_pk, **kw):
    vt = _orig_version_table_impl(self, version_table=version_table, version_table_schema=version_table_schema, version_table_pk=version_table_pk, **kw)
    for col in vt.columns:
        if col.name == "version_num":
            col.type = sa.String(128)
    return vt

alembic.ddl.impl.DefaultImpl.version_table_impl = _custom_version_table_impl

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

def get_url():
    x_args = context.get_x_argument(as_dictionary=True)
    if "url" in x_args:
        return x_args["url"]
    url = os.environ.get("DATABASE_URL")
    if not url:
        url = config.get_main_option("sqlalchemy.url")
    if not url:
        url = settings.DATABASE_URL
    return url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_num_length=128,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        try:
            connection.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE character varying(128);"))
            connection.commit()
        except Exception:
            connection.rollback()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_num_length=128,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
