# Event catalog

The authoritative list of every event on every topic. Updating this file is part of the
definition of done for any new or changed event (CLAUDE.md §8, §11).

| Event | Topic | Owning service | Schema version | Status |
|-------|-------|----------------|----------------|--------|
| `PaymentInitiated` | `payments.lifecycle.events` | payment-api | 1 | Modeled (Slice 1) |

## `PaymentInitiated` (v1)

A payment has entered the lifecycle — a client asked us to move money. Root of a payment's
event chain (`causation_id` is `None`). Defined in
[`intellipay.contracts.payments`](../libs/contracts/src/intellipay/contracts/payments.py).

**Envelope (all events):** `event_id`, `correlation_id`, `causation_id`, `occurred_at`
(UTC, tz-aware), `schema_version`, `semantic` (see CLAUDE.md §6, §10).

**Payload:**

| Field | Type | Notes |
|-------|------|-------|
| `event_type` | `"PaymentInitiated"` | self-describing discriminator |
| `payment_id` | UUID | aggregate id + Kafka partition key |
| `amount` | Decimal (> 0) | serialized as a JSON string; never a float |
| `currency` | str | ISO 4217 alpha-3, uppercase |
| `merchant_id` | str | |
| `payment_instrument_token` | str | tokenized card reference — **never a raw PAN** |

**Semantic:** `entity_type="Payment"`, `ontology_terms=["fibo-fbc-pas-caa:CardPayment"]`
(FIBO IRI is a **placeholder**, pending real mapping in [ontology.md](ontology.md)),
`glossary_ref="docs/ontology.md#paymentinitiated"`.
