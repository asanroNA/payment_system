"""Consumer idempotency: exactly-once *effect* under at-least-once delivery (CLAUDE.md §3.6).

Kafka redelivers, and our relay re-publishes on failure (relay.py), so a consumer WILL see
the same event more than once and must not double-apply its side effect. The guarantee here
is structural, not best-effort: the side effect and the dedupe insert happen in ONE
transaction, and a composite primary key ``(event_id, consumer)`` makes a second apply
impossible at the database level — not merely unlikely.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, String, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from intellipay.common.outbox import Base


class ProcessedEvent(Base):
    """Dedupe ledger: "consumer X has handled event Y".

    The PK is composite so one event can be processed once PER consumer — independent
    consumers each get their own exactly-once handling (fan-out), while a single consumer
    never repeats.
    """

    __tablename__ = "processed_events"

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    consumer: Mapped[str] = mapped_column(String(255), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


async def already_processed(session: AsyncSession, *, event_id: UUID, consumer: str) -> bool:
    stmt = select(
        exists().where(
            ProcessedEvent.event_id == event_id,
            ProcessedEvent.consumer == consumer,
        )
    )
    return bool((await session.execute(stmt)).scalar())


def mark_processed(session: AsyncSession, *, event_id: UUID, consumer: str) -> None:
    """Record handling as part of the caller's transaction.

    Like ``enqueue_event``, this only ``add``s — it must commit together with the side
    effect, never on its own, or the dedupe and the effect could diverge.
    """
    session.add(ProcessedEvent(event_id=event_id, consumer=consumer))


async def process_once(
    session: AsyncSession,
    *,
    event_id: UUID,
    consumer: str,
    handler: Callable[[AsyncSession], Awaitable[None]],
) -> bool:
    """Run ``handler`` exactly once for ``(event_id, consumer)``.

    Returns ``True`` if the handler ran, ``False`` if this delivery was a duplicate and was
    skipped. The handler does its work on the SAME ``session``; then we mark and commit
    atomically, so the side effect and the dedupe row are all-or-nothing.

    Concurrency: if two deliveries race, both can pass the pre-check, but only one can insert
    the composite PK. The loser raises ``IntegrityError``, rolls back (undoing its side
    effect too), and returns ``False``. The pre-check is just an optimization to avoid doing
    work we'll throw away; the unique constraint is the actual guarantee.
    """
    if await already_processed(session, event_id=event_id, consumer=consumer):
        return False
    try:
        await handler(session)
        mark_processed(session, event_id=event_id, consumer=consumer)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        if await already_processed(session, event_id=event_id, consumer=consumer):
            return False  # lost the race; the winner applied it
        raise  # a different integrity problem — don't swallow it
    return True
