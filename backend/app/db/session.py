from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db import models as _models  # noqa: F401 - register all model metadata
from app.db.seed import seed_default_users


def create_database_engine(database_url: str) -> AsyncEngine:
    url = make_url(database_url)
    connect_args = {"check_same_thread": False} if url.get_backend_name() == "sqlite" else {}
    if url.get_backend_name() == "sqlite" and url.database not in {None, "", ":memory:"}:
        from pathlib import Path

        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    if url.get_backend_name() == "sqlite":
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


async def initialize_database(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await seed_default_users(engine)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        yield session
