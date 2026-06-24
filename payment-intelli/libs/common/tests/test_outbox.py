"""Tests for the transactional outbox write helper (CLAUDE.md §3.3)."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from intellipay.common.outbox import OutboxRecord, enqueue_event
from intellipay.contracts import PaymentInitiated

pytestmark = pytest.mark.anyio


def _make_event() -> PaymentInitiated:
    return PaymentInitiated(
        correlation_id=uuid4(),
        payment_id=uuid4(),
        amount=Decimal("42.50"),
        currency="USD",
        merchant_id="merchant-123",
        payment_instrument_token="tok_abc123",
    )


async def _count(sessions: async_sessionmaker[AsyncSession]) -> int:
    async with sessions() as session:
        return (await session.execute(select(func.count()).select_from(OutboxRecord))).scalar_one()


async def test_enqueue_is_part_of_caller_transaction(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    # The atomicity guarantee: rolling back the caller's tx discards the event too.
    async with sessions() as session:
        enqueue_event(session, _make_event(), topic="t", partition_key="k")
        await session.rollback()
    assert await _count(sessions) == 0


async def test_enqueue_persists_on_commit(sessions: async_sessionmaker[AsyncSession]) -> None:
    event = _make_event()
    async with sessions() as session:
        enqueue_event(
            session,
            event,
            topic="payments.lifecycle.events",
            partition_key=str(event.payment_id),
        )
        await session.commit()

    async with sessions() as session:
        record = (await session.execute(select(OutboxRecord))).scalar_one()
    assert record.event_id == event.event_id
    assert record.published_at is None  # not yet relayed
    assert record.partition_key == str(event.payment_id)
    assert record.headers["correlation_id"] == str(event.correlation_id)
    assert record.headers["content-type"] == "application/json"
    # The stored payload round-trips back into the exact same contract instance.
    assert PaymentInitiated.model_validate_json(record.payload) == event


async def test_root_event_omits_causation_header(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    # PaymentInitiated is a chain root (causation_id is None) — no empty header smuggled in.
    event = _make_event()
    async with sessions() as session:
        enqueue_event(session, event, topic="t", partition_key="k")
        await session.commit()
    async with sessions() as session:
        record = (await session.execute(select(OutboxRecord))).scalar_one()
    assert "causation_id" not in record.headers
