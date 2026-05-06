from collections.abc import AsyncGenerator
import os

from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agent_canvas.db")

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_owner_columns)


def _ensure_owner_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    for table_name in ("graphs", "mcp_servers"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "owner_id" not in columns:
            sync_conn.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN owner_id VARCHAR DEFAULT 'local-user' NOT NULL")
            )
        sync_conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table_name}_owner_id ON {table_name} (owner_id)"))
