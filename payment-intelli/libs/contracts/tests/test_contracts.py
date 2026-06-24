"""Contract tests for the event spine (CLAUDE.md §9 "Contract").

Covers: round-trip serialize/deserialize, the immutability and lineage invariants the
whole architecture leans on, money precision, and field validation.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from intellipay.contracts import EventEnvelope, PaymentInitiated, SemanticMeta


def _valid_payment() -> PaymentInitiated:
    return PaymentInitiated(
        correlation_id=uuid4(),
        payment_id=uuid4(),
        amount=Decimal("42.50"),
        currency="USD",
        merchant_id="merchant-123",
        payment_instrument_token="tok_abc123",
    )


def test_round_trip_is_lossless() -> None:
    original = _valid_payment()
    restored = PaymentInitiated.model_validate_json(original.model_dump_json())
    assert restored == original


def test_amount_serializes_as_string_not_float() -> None:
    # Decimal must survive the wire exactly; a float would corrupt cents.
    payload = _valid_payment().model_dump(mode="json")
    assert payload["amount"] == "42.50"
    assert isinstance(payload["amount"], str)


def test_events_are_immutable() -> None:
    payment = _valid_payment()
    with pytest.raises(ValidationError):
        payment.amount = Decimal("0.01")


def test_correlation_id_is_required() -> None:
    # The lineage guardrail (§10): no silent default may sever the causal graph.
    with pytest.raises(ValidationError):
        PaymentInitiated(  # type: ignore[call-arg]
            payment_id=uuid4(),
            amount=Decimal("1.00"),
            currency="USD",
            merchant_id="m",
            payment_instrument_token="tok",
        )


def test_envelope_defaults_are_populated() -> None:
    payment = _valid_payment()
    assert payment.event_id is not None
    assert payment.causation_id is None  # root of a chain
    assert payment.occurred_at.tzinfo is not None  # timezone-aware
    assert payment.schema_version == 1
    assert payment.event_type == "PaymentInitiated"


def test_event_ids_are_unique_per_instance() -> None:
    assert _valid_payment().event_id != _valid_payment().event_id


def test_semantic_default_is_not_empty() -> None:
    # §8: the semantic block must be filled in, never empty.
    semantic = _valid_payment().semantic
    assert semantic.entity_type
    assert semantic.ontology_terms


@pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
def test_currency_must_be_iso4217_alpha(bad_currency: str) -> None:
    # NB: construct fresh — model_copy(update=...) bypasses validation by design.
    with pytest.raises(ValidationError):
        PaymentInitiated(
            correlation_id=uuid4(),
            payment_id=uuid4(),
            amount=Decimal("1.00"),
            currency=bad_currency,
            merchant_id="m",
            payment_instrument_token="tok",
        )


@pytest.mark.parametrize("bad_amount", [Decimal("0"), Decimal("-1.00")])
def test_amount_must_be_positive(bad_amount: Decimal) -> None:
    with pytest.raises(ValidationError):
        PaymentInitiated(
            correlation_id=uuid4(),
            payment_id=uuid4(),
            amount=bad_amount,
            currency="USD",
            merchant_id="m",
            payment_instrument_token="tok",
        )


def test_unknown_fields_are_ignored_for_forward_compat() -> None:
    # §3.7: an old consumer must tolerate a newer event with an extra optional field.
    raw = _valid_payment().model_dump(mode="json")
    raw["some_future_field"] = "added later"
    restored = PaymentInitiated.model_validate(raw)
    assert not hasattr(restored, "some_future_field")


def test_schema_exposes_envelope_and_payload_fields() -> None:
    schema = PaymentInitiated.model_json_schema()
    props = schema["properties"].keys()
    for field in (
        "event_id",
        "correlation_id",
        "causation_id",
        "occurred_at",
        "schema_version",
        "semantic",
        "payment_id",
        "amount",
        "currency",
    ):
        assert field in props


def test_envelope_is_abstract_without_version_and_semantic() -> None:
    # The base requires schema_version + semantic; it isn't meant to be emitted bare.
    with pytest.raises(ValidationError):
        EventEnvelope(correlation_id=uuid4())  # type: ignore[call-arg]


def test_semantic_meta_round_trip() -> None:
    meta = SemanticMeta(entity_type="Payment", ontology_terms=["fibo:CardPayment"])
    assert SemanticMeta.model_validate_json(meta.model_dump_json()) == meta
