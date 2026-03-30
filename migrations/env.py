from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
from dotenv import load_dotenv
import sys
from pathlib import Path

load_dotenv()

# Add the backend directory to the path so we can import models
sys.path.insert(0, str(Path(__file__).parent.parent))

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import metadata from models
from app.models.database import Base
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_name="postgresql",
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = DATABASE_URL
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()