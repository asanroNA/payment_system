"""Tests for consumer idempotency (CLAUDE.md §3.6)."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from intellipay.common.idempotency import already_processed, process_once

pytestmark = pytest.mark.anyio


class Counter:
    """A side effect we can observe: counts how many times the handler actually ran."""

    def __init__(self) -> None:
        self.runs = 0

    async def handler(self, _session: AsyncSession) -> None:
        self.runs += 1


async def test_handler_runs_on_first_delivery(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    counter = Counter()
    event_id = uuid4()
    async with sessions() as session:
        ran = await process_once(
            session, event_id=event_id, consumer="ledger", handler=counter.handler
        )
    assert ran is True
    assert counter.runs == 1


async def test_duplicate_delivery_is_skipped(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    counter = Counter()
    event_id = uuid4()
    for _ in range(3):  # same event delivered three times
        async with sessions() as session:
            await process_once(
                session, event_id=event_id, consumer="ledger", handler=counter.handler
            )
    assert counter.runs == 1  # exactly-once effect


async def test_same_event_processed_once_per_consumer(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    # Fan-out: independent consumers each handle the same event exactly once.
    counter = Counter()
    event_id = uuid4()
    for consumer in ("ledger", "notifications"):
        async with sessions() as session:
            ran = await process_once(
                session, event_id=event_id, consumer=consumer, handler=counter.handler
            )
        assert ran is True
    assert counter.runs == 2


async def test_handler_failure_leaves_event_unprocessed(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    event_id = uuid4()

    async def boom(_session: AsyncSession) -> None:
        raise RuntimeError("side effect failed")

    async with sessions() as session:
        with pytest.raises(RuntimeError):
            await process_once(session, event_id=event_id, consumer="ledger", handler=boom)

    # Not marked, so a retry re-runs it: the side effect and the dedupe row are atomic.
    async with sessions() as session:
        assert await already_processed(session, event_id=event_id, consumer="ledger") is False

    counter = Counter()
    async with sessions() as session:
        ran = await process_once(
            session, event_id=event_id, consumer="ledger", handler=counter.handler
        )
    assert ran is True
    assert counter.runs == 1
