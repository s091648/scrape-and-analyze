import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from models.base import Base
from models.article import Article  # noqa: F401 — registers Article
from models.analysis import Analysis  # noqa: F401 — registers Analysis
from models.analysis_translation import AnalysisTranslation  # noqa: F401 — registers AnalysisTranslation
from models.failed_task import FailedTask  # noqa: F401 — registers FailedTask

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("DATABASE_URL", "")
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
