"""Transactional outbox: the only sanctioned way to emit an event (CLAUDE.md §3.3, §12).

The rule this module exists to enforce: NEVER publish to Kafka from a request handler.
Instead, write the domain row and an outbox row in the SAME database transaction, then let
the relay (``relay.py``) publish committed rows. That turns "did my event actually get
out?" from a dual-write race into a property of one atomic commit.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from intellipay.contracts import EventEnvelope


class Base(DeclarativeBase):
    """Shared declarative base for every persistent table in the system.

    Services define their own domain tables on this same Base so a single ``metadata`` (and
    one Alembic run per service) covers the domain tables *and* the outbox together — which
    is what makes the domain-row + outbox-row write a single transaction in Slice 4.
    """


class OutboxRecord(Base):
    """One pending (or published) event, awaiting/handled by the relay.

    Deliberately dumb: it stores the already-serialized event plus the routing it needs
    (``topic``, ``partition_key``) and the Kafka ``headers``. The relay never re-derives any
    of this — the row is the complete instruction to publish.
    """

    __tablename__ = "outbox"

    # BIGINT on Postgres for headroom; INTEGER on SQLite so it aliases rowid and
    # autoincrements (SQLite only auto-assigns an INTEGER PRIMARY KEY, never a BIGINT one).
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    """Monotonic sequence. The relay publishes in ``id`` order, preserving per-aggregate
    ordering for rows written by one producer."""

    event_id: Mapped[UUID] = mapped_column(Uuid, unique=True, index=True)
    """Mirrors the event's own id. ``unique`` stops an event being enqueued twice; it is
    also the key consumers dedupe on (§3.6)."""

    topic: Mapped[str] = mapped_column(String(255))
    partition_key: Mapped[str] = mapped_column(String(255))
    """Kafka message key — e.g. ``payment_id`` — so one aggregate's events stay ordered (§6)."""

    payload: Mapped[str] = mapped_column(Text)
    """The event, already serialized via ``model_dump_json()``. Stored as text so the relay
    is a pure byte-mover and the contract lives in ``libs/contracts``, not here."""

    headers: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    """Kafka headers (correlation_id, schema_version, content-type, optionally causation_id)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    """``NULL`` means "not yet on Kafka". The relay's entire job is to flip this."""


def enqueue_event(
    session: AsyncSession,
    event: EventEnvelope,
    *,
    topic: str,
    partition_key: str,
) -> OutboxRecord:
    """Stage ``event`` for publication as part of the caller's transaction.

    Crucially this does NOT flush or commit. It only ``session.add``s the row, joining
    whatever unit of work the caller already has open. The caller commits the domain change
    and this outbox row together — that single commit is the atomicity guarantee. If the
    caller rolls back, the event is never enqueued. (If this function committed on its own,
    we'd be back to a dual write.)
    """
    headers = {
        "correlation_id": str(event.correlation_id),
        "schema_version": str(event.schema_version),
        "content-type": "application/json",
    }
    if event.causation_id is not None:
        headers["causation_id"] = str(event.causation_id)

    record = OutboxRecord(
        event_id=event.event_id,
        topic=topic,
        partition_key=partition_key,
        payload=event.model_dump_json(),
        headers=headers,
    )
    session.add(record)
    return record
