"""The base envelope every event inherits (CLAUDE.md §5, §6, §10).

One model to rule the cross-cutting concerns: identity (``event_id``), lineage
(``correlation_id`` / ``causation_id``), time (``occurred_at``), versioning
(``schema_version``), and semantics (``semantic``). Concrete events add their payload.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from intellipay.contracts.semantic import SemanticMeta


class EventEnvelope(BaseModel):
    """Common fields on every domain event.

    ``frozen=True`` enforces the §3.5 / §12 guardrail that events are immutable: once
    constructed, an instance cannot be mutated (and is hashable). Unknown fields are
    *ignored* on parse (Pydantic's default), not rejected — that is deliberate: it lets an
    old consumer read a newer event that added an optional field, which is exactly the
    backward-compatible evolution §3.7 requires.
    """

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    """Unique per event instance. The dedupe key idempotent consumers key on (§3.6)."""

    correlation_id: UUID
    """Ties every event of one payment together. REQUIRED and never auto-generated: a
    silent default here would let a downstream event start a fresh correlation and sever
    the causal graph Phase 2 depends on (§10). Producers must wire it through explicitly."""

    causation_id: UUID | None = None
    """The event/command that directly caused this one. ``None`` only for a chain's root
    (e.g. PaymentInitiated, caused by an external request rather than another event)."""

    occurred_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    """When the event happened, UTC and timezone-aware. ``AwareDatetime`` rejects naive
    datetimes so we never record an ambiguous, un-orderable timestamp."""

    schema_version: int
    """Bumped (with a new model) on any breaking change; additive changes keep it (§3.7).
    No default here — each concrete event declares its own current version."""

    semantic: SemanticMeta
    """Ontology mapping (§10). No default here; concrete events supply their own, since the
    mapping is a property of the event *type*, not something a producer should reinvent."""
