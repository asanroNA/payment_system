"""Tests for the polling relay (CLAUDE.md §3.3).

Exercises the two properties that matter: published rows get marked (no re-send on the happy
path), and a publish failure leaves the row unpublished so it retries (at-least-once).
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from intellipay.common.outbox import OutboxRecord, enqueue_event
from intellipay.common.relay import relay_once
from intellipay.contracts import PaymentInitiated

pytestmark = pytest.mark.anyio


class FakeProducer:
    """Records what it was asked to publish; never fails."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str, str, dict[str, str]]] = []

    async def publish(self, *, topic: str, key: str, value: str, headers: dict[str, str]) -> None:
        self.published.append((topic, key, value, headers))


class FailingProducer:
    """Always raises — stands in for Kafka being unreachable mid-publish."""

    def __init__(self) -> None:
        self.calls = 0

    async def publish(self, *, topic: str, key: str, value: str, headers: dict[str, str]) -> None:
        self.calls += 1
        raise RuntimeError("kafka unreachable")


def _make_event() -> PaymentInitiated:
    return PaymentInitiated(
        correlation_id=uuid4(),
        payment_id=uuid4(),
        amount=Decimal("10.00"),
        currency="USD",
        merchant_id="m",
        payment_instrument_token="tok",
    )


async def _seed(sessions: async_sessionmaker[AsyncSession], n: int) -> None:
    async with sessions() as session:
        for _ in range(n):
            event = _make_event()
            enqueue_event(
                session,
                event,
                topic="payments.lifecycle.events",
                partition_key=str(event.payment_id),
            )
        await session.commit()


async def _unpublished(sessions: async_sessionmaker[AsyncSession]) -> int:
    async with sessions() as session:
        stmt = (
            select(func.count())
            .select_from(OutboxRecord)
            .where(OutboxRecord.published_at.is_(None))
        )
        return (await session.execute(stmt)).scalar_one()


async def test_relay_publishes_then_marks(sessions: async_sessionmaker[AsyncSession]) -> None:
    await _seed(sessions, 2)
    producer = FakeProducer()

    published = await relay_once(sessions, producer)

    assert published == 2
    assert len(producer.published) == 2
    assert await _unpublished(sessions) == 0
    # Nothing left to do: a second pass is a no-op (no re-send).
    assert await relay_once(sessions, FakeProducer()) == 0


async def test_relay_keeps_row_for_retry_on_failure(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(sessions, 1)

    with pytest.raises(RuntimeError):
        await relay_once(sessions, FailingProducer())

    # At-least-once: the failed publish did not mark the row, so it remains pending.
    assert await _unpublished(sessions) == 1

    # A later pass with a working producer delivers it.
    producer = FakeProducer()
    assert await relay_once(sessions, producer) == 1
    assert len(producer.published) == 1
    assert await _unpublished(sessions) == 0
