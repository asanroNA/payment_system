"""Polling relay: moves committed outbox rows onto Kafka (CLAUDE.md §3.3).

This is the local stand-in for Debezium CDC. It reads the SAME outbox table Debezium would,
so swapping Debezium in later changes only *how* rows reach Kafka, never the write side.

Delivery is **at-least-once by design**: a row is published first and marked published only
on commit, so a crash between the two re-publishes the row next pass. That is the right
failure mode for money (never lose an event) and is exactly why consumers must dedupe on
``event_id`` (§3.6). The opposite order — mark then publish — could silently drop events.
"""

import asyncio
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from intellipay.common.outbox import OutboxRecord


class Producer(Protocol):
    """The narrow slice of a Kafka producer the relay needs.

    A Protocol (structural) so the relay depends on a capability, not a concrete client:
    tests pass a fake; Slice 2b passes the real FastStream-backed adapter.
    """

    async def publish(
        self, *, topic: str, key: str, value: str, headers: dict[str, str]
    ) -> None: ...


async def relay_once(
    session_factory: async_sessionmaker[AsyncSession],
    producer: Producer,
    *,
    batch_size: int = 100,
    skip_locked: bool = False,
) -> int:
    """Publish one batch of unpublished rows. Returns how many were published.

    ``skip_locked`` adds ``FOR UPDATE SKIP LOCKED`` so multiple relay workers can run without
    publishing the same row twice. It is a PostgreSQL feature, so it defaults to off and the
    service turns it on for Postgres; SQLite (tests) runs single-worker without it.
    """
    async with session_factory() as session:
        stmt = (
            select(OutboxRecord)
            .where(OutboxRecord.published_at.is_(None))
            .order_by(OutboxRecord.id)
            .limit(batch_size)
        )
        if skip_locked:
            stmt = stmt.with_for_update(skip_locked=True)

        rows = (await session.execute(stmt)).scalars().all()
        for row in rows:
            # Publish first, mark second. If publish raises, we exit the `async with` via the
            # exception, the session rolls back, published_at stays NULL, and the row retries.
            await producer.publish(
                topic=row.topic,
                key=row.partition_key,
                value=row.payload,
                headers=dict(row.headers),
            )
            row.published_at = datetime.now(UTC)

        await session.commit()
        return len(rows)


async def run_relay(
    session_factory: async_sessionmaker[AsyncSession],
    producer: Producer,
    *,
    poll_interval: float = 0.5,
    batch_size: int = 100,
    skip_locked: bool = False,
    stop: asyncio.Event | None = None,
) -> None:
    """Run the relay until ``stop`` is set. Sleeps ``poll_interval`` only when idle.

    Drains continuously while there is a backlog (so a burst clears fast) and backs off to
    polling when caught up. ``stop`` lets a service shut the loop down cleanly.
    """
    while stop is None or not stop.is_set():
        published = await relay_once(
            session_factory, producer, batch_size=batch_size, skip_locked=skip_locked
        )
        if published == 0:
            await asyncio.sleep(poll_interval)
