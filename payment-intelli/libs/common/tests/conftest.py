"""Shared fixtures for libs/common tests.

Runs the async SQLAlchemy code against a real (file-backed) SQLite database via aiosqlite —
real transactions, real commits across connections, no Postgres or Kafka required.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from intellipay.common.outbox import Base


@pytest.fixture
def anyio_backend() -> str:
    # Single backend keeps async tests fast and deterministic.
    return "asyncio"


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    # File-backed (not :memory:) so commits are visible across separate sessions/connections,
    # which is what the transactional-outbox tests actually exercise.
    db = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db.as_posix()}")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
