"""Payment lifecycle events (CLAUDE.md §2).

First event in the catalog: ``PaymentInitiated``, emitted by payment-api at the start of
the lifecycle. More events (validated, authorized, ...) are added one slice at a time.
"""

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from intellipay.contracts.envelope import EventEnvelope
from intellipay.contracts.semantic import SemanticMeta

CurrencyCode = Annotated[str, StringConstraints(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]
"""ISO 4217 alphabetic currency code, e.g. "USD". Uppercase, exactly three letters."""

PositiveAmount = Annotated[Decimal, Field(gt=0)]
"""Money amount. ``Decimal`` (never float) so we don't lose cents to binary rounding;
Pydantic serializes it as a JSON string, preserving exact precision on the wire."""


def _payment_initiated_semantics() -> SemanticMeta:
    # NOTE: the FIBO IRI below is a PLACEHOLDER and must be confirmed against a real FIBO
    # vocabulary when docs/ontology.md is fleshed out. Flagged here, not silently shipped.
    return SemanticMeta(
        entity_type="Payment",
        ontology_terms=["fibo-fbc-pas-caa:CardPayment"],
        glossary_ref="docs/ontology.md#paymentinitiated",
    )


class PaymentInitiated(EventEnvelope):
    """A payment has entered the lifecycle: a client asked us to move money.

    Emitted by payment-api via the outbox. Partition key on the topic is ``payment_id``
    so a single payment's events stay ordered (§6).
    """

    event_type: Literal["PaymentInitiated"] = "PaymentInitiated"
    """Self-describing tag. Makes the payload routable on a shared topic and is the
    discriminator a tagged union of events will key on once there is more than one."""

    schema_version: int = 1
    semantic: SemanticMeta = Field(default_factory=_payment_initiated_semantics)

    payment_id: UUID
    """The aggregate id; also the Kafka partition key for this payment's events."""

    amount: PositiveAmount
    currency: CurrencyCode
    merchant_id: str

    payment_instrument_token: str
    """A TOKENIZED reference to the card, never a raw PAN. The event log is immutable and
    feeds the Phase 2 knowledge base — putting cardholder data here would be an
    un-deletable PCI breach. Tokenization happens upstream, at the edge."""
