# CLAUDE.md

> Guidance for Claude Code (and humans) working in this repository.
> Read this fully before making changes. When local conventions here conflict
> with a generic pattern you'd reach for, the conventions here win.

---

## 1. Project: `intelli-pay` — Event-Driven Payment Lifecycle Platform

> `intelli-pay` is a placeholder codename — rename throughout when you pick the real one.

A microservices platform that models the **card-rail payment lifecycle** as a stream of
immutable domain events on **Apache Kafka**. Services are FastAPI apps. The **ledger is
event-sourced** (append-only event store = source of truth for money movement); the other
domain services own their own state and coordinate by **choreography**, while `payment-api`
runs an **orchestration saga** that drives the end-to-end flow.

The system is deliberately built to support a **Phase 2 semantic layer** (RAG +
ontology, anchored on FIBO) over the event history. That goal imposes constraints on how we
model events *today* — see §10. Do not violate them, even though Phase 2 code does not exist yet.

**Runs locally on Docker Compose now; targets AWS (ECS/EKS + MSK) later.** Keep every
service 12-factor (config from env, no host assumptions, stateless except via its own DB).

---

## Working mode — read this first

You write the implementation, but the bar is that I (the human) fully understand every
change before it lands. **Optimize for my comprehension, not for speed.** Code I can't
explain is a failure here, even if it passes tests — the point of this project is that I
learn event-driven architecture, not that the repo fills up.

- **Small, reviewable increments.** One vertical slice or one component at a time. Never a
  big-bang multi-file generation. After each increment, stop and wait for me.
- **Plan before you write.** Before a non-trivial piece, give me a 2–4 sentence plan: what
  you're about to build, why, and the key decisions. Let me say go.
- **Explain after you write.** Walk the important code, name the trade-offs you made and the
  alternatives you rejected, and tie it back to the guardrails below (§12) — outbox,
  append-only ledger, idempotency, typed contracts, lineage fields.
- **Spend the explanation budget where it matters.** Go deep on code that encodes a
  *decision* — the saga, the outbox relay, idempotency, projection logic. Keep it brief for
  boilerplate that encodes a *convention* — Compose, Alembic setup, registry wiring.
- **Surface the non-obvious.** Any place a reasonable person would write it differently, any
  subtlety that bites later, anything I'm likely to misread — say so explicitly.
- **I'll ask "why" a lot.** Those are genuine questions, not pushback. Answer plainly, and if
  I've misunderstood something, correct me directly.
- **Boring over clever.** Prefer readable code. If a clever version earns its complexity, say why.
- **No buried decisions.** Never leave a TODO or a silent assumption inside the code. Surface
  it in the chat where I'll see it, not in a comment I'll scroll past.
- **Explicit override:** if I say "just scaffold this" or "generate the boilerplate," do it
  without the full plan/explain ceremony for that turn, then return to this mode.

---

## 2. The lifecycle (canonical state machine)

```
initiated → validated → authorized → captured → cleared → settled
                 │           │
              declined    reversed → refunded
                                  └→ disputed → chargeback
```

| Transition           | Owning service               | Emits                          |
|----------------------|------------------------------|--------------------------------|
| initiated, validated | payment-api (saga)           | PaymentInitiated, PaymentValidated |
| authorized / declined| authorization-service        | PaymentAuthorized / PaymentDeclined |
| captured, cleared, settled | clearing-settlement-service | PaymentCaptured, PaymentCleared, PaymentSettled |
| reversed, refunded   | clearing-settlement-service  | PaymentReversed, PaymentRefunded |
| disputed, chargeback | dispute-service              | DisputeOpened, ChargebackRecorded, DisputeResolved |
| every money movement | ledger-service (sourced)     | LedgerEntryRecorded (append-only) |

The saga in `payment-api` is the **process manager**: it reacts to lifecycle events,
issues the next command, and runs compensations on failure. Domain services never call
each other synchronously — they communicate only through Kafka.

---

## 3. Core architecture principles (do not violate)

1. **Kafka is the only channel for inter-service domain events.** No synchronous
   service-to-service HTTP for lifecycle transitions. (Synchronous calls are allowed only
   at the public edge, in `payment-api`, for request/response with the client.)
2. **The ledger is append-only.** Never `UPDATE`/`DELETE` a ledger event. State is a fold
   over the event stream. Corrections are new compensating events, never edits.
3. **Transactional outbox for every state-change-that-emits.** Write the domain row and the
   outbox row in the same DB transaction; a relay (Debezium CDC) publishes to Kafka. **Never**
   publish to Kafka directly from a request handler — that is a dual-write bug waiting to happen.
4. **All events are typed Pydantic models from `libs/contracts`.** No ad-hoc `dict` payloads
   on any topic, ever. The model is the contract.
5. **Events are immutable and semantically rich.** Every event carries `event_id`,
   `correlation_id`, `causation_id`, `occurred_at`, `schema_version`, and a `semantic` metadata
   block (see §10). Do not strip or shortcut these.
6. **Consumers are idempotent.** Dedupe on `event_id` / `idempotency_key`. Payments must be
   exactly-once-*effect*, even under at-least-once delivery and redelivery.
7. **Backward-compatible schema evolution only.** Adding an optional field is fine. Removing,
   renaming, or retyping a field requires a new event version (`schema_version` bump + a new
   model), never a breaking change to an existing one.

---

## 4. Tech stack

| Concern              | Choice                                              |
|----------------------|-----------------------------------------------------|
| Language / runtime   | Python 3.12+                                         |
| Web framework        | FastAPI (public surfaces), Pydantic v2 models        |
| Event framework      | FastStream (Kafka backend) — typed producers/consumers, AsyncAPI docs |
| Low-level Kafka      | `confluent-kafka-python` only where FastStream is too high-level |
| Broker               | Apache Kafka (KRaft mode, no Zookeeper)             |
| Schema registry      | Apicurio (Confluent SR also fine) — compat enforced in CI |
| Persistence          | PostgreSQL per service (schema-per-service locally) |
| ORM / migrations     | SQLAlchemy 2.x (async) + Alembic                    |
| Outbox relay         | Debezium CDC (local: a polling relay is acceptable) |
| Dependency mgmt      | `uv`                                                |
| Lint / type / format | `ruff`, `mypy --strict`, `ruff format`              |
| Tests                | `pytest`, `testcontainers` (real Kafka + Postgres)  |
| Local orchestration  | Docker Compose                                      |
| Target deploy        | AWS ECS/EKS + MSK + RDS (later)                     |

Don't pin versions in this file — pins live in each service's `pyproject.toml` / `uv.lock`.

---

## 5. Repository layout (monorepo)

```
app/
├── services/
│   ├── payment-api/                 # public FastAPI surface + orchestration saga
│   ├── ledger-service/              # EVENT-SOURCED. append-only event store + projections
│   ├── authorization-service/       # issuer/network auth decision (mocked locally)
│   ├── clearing-settlement-service/ # capture → clearing → settlement, reversals, refunds
│   ├── dispute-service/             # disputes, chargebacks, refund initiation
│   └── notification-service/        # pure choreography consumer (good reference example)
├── libs/
│   ├── contracts/                   # SHARED event/command Pydantic models — single source of truth
│   └── common/                      # outbox helpers, kafka wiring, idempotency, correlation context
├── infra/
│   ├── docker-compose.yml           # kafka, schema-registry, postgres(es), debezium, kafka-ui
│   ├── kafka/                       # topic definitions, partitions, retention
│   └── schema-registry/             # registered schemas + compat config
└── docs/
    ├── architecture.md
    ├── events.md                    # the event catalog — keep this current (see §8)
    ├── ontology.md                  # FIBO mapping notes for Phase 2
    └── adr/                         # architecture decision records
```

Each service directory is self-contained: `app/` (api, domain, consumers, projections),
`migrations/`, `tests/`, `Dockerfile`, `pyproject.toml`.

`libs/contracts` is the spine. A producer and its consumers import the **same** model — so
contract drift shows up as a type error, not a 2am incident.

---

## 6. Event model & topic conventions

- **Topic naming:** `<domain>.<aggregate>.events` — e.g. `payments.lifecycle.events`,
  `ledger.entries.events`, `disputes.events`. Command topics (if used by the saga):
  `<domain>.<aggregate>.commands`.
- **Keying:** partition by `payment_id` (or `account_id` for ledger) so per-aggregate
  ordering is preserved.
- **Dead-letter:** every consumer group has a `<topic>.dlq`. Failed messages go there with
  the failure reason and original headers; they are never silently dropped.
- **Headers:** `correlation_id`, `causation_id`, `schema_version`, `content-type` on every
  message. These propagate through the saga and are what makes the event history traceable
  (and, later, queryable — see §10).

Base envelope (in `libs/contracts`, all events inherit it):

```python
class EventEnvelope(BaseModel):
    event_id: UUID
    correlation_id: UUID            # ties all events of one payment together
    causation_id: UUID | None       # the event/command that caused this one
    occurred_at: datetime           # UTC, set at creation, never mutated
    schema_version: int
    semantic: SemanticMeta          # see §10 — ontology-mapping metadata
```

---

## 7. Commands (Makefile targets)

```
make up                # docker compose up: kafka, schema-registry, postgres, debezium, ui
make down              # tear down (keeps volumes)
make reset             # tear down + wipe volumes (clean slate)
make run svc=ledger    # run one service locally against the compose infra
make migrate svc=ledger# alembic upgrade head for one service
make topics            # create/declare topics from infra/kafka/
make schema-register   # register libs/contracts schemas with the registry
make schema-check      # FAIL if any schema change is backward-incompatible (run in CI)
make produce e=PaymentInitiated  # emit a sample event for manual testing
make consume t=payments.lifecycle.events  # tail a topic
make test              # full suite (unit + contract + integration via testcontainers)
make test-unit         # fast, no infra
make lint              # ruff + mypy --strict
```

If a target doesn't exist yet, add it to the Makefile rather than running raw commands
inline — keep the interface stable.

---

## 8. Workflow: adding a new event

1. **Model it** in `libs/contracts` as a Pydantic class inheriting `EventEnvelope`. Fill in
   the `semantic` block (§10) — don't leave it empty.
2. **Register the schema** (`make schema-register`) and confirm compat (`make schema-check`).
3. **Produce it via the outbox**, never directly: write the domain row + outbox row in one
   transaction; the relay publishes it.
4. **Add an idempotent consumer** (dedupe on `event_id`). New side effects must be safe under
   redelivery.
5. **Write a contract test** asserting the schema and a round-trip serialize/deserialize.
6. **Update `docs/events.md`** — the event catalog is part of the definition of done.

---

## 9. Testing

- **Unit:** the state machine and domain logic are pure functions — test them without infra.
  The lifecycle transitions in §2 should have exhaustive transition + guard tests.
- **Contract:** every event model has a schema + round-trip test; `make schema-check` gates
  backward-compatibility in CI.
- **Integration:** `testcontainers` spins up real Kafka + Postgres. Test the outbox →
  Kafka → consumer path end-to-end, including idempotency under redelivery.
- **Saga / e2e:** cover the happy path *and* the compensation paths (auth declined after
  capture queued, settlement failure, dispute mid-flight). Failure paths are where payment
  systems actually break — they are not optional.

---

## 10. Forward-looking: RAG + Ontology (Phase 2) — constraints to respect NOW

Phase 2 will project the event history into (a) a **vector store** for retrieval and (b) a
**knowledge graph mapped to FIBO** (Financial Industry Business Ontology) for reasoning,
behind a natural-language query service. None of that exists yet — but these write-side
constraints make it cheap later instead of a painful retrofit:

- **Keep events immutable and append-only.** The event log *is* the future knowledge base.
  A mutated history can't be trusted by a reasoning layer.
- **Preserve lineage.** `correlation_id` + `causation_id` on every event give Phase 2 a
  causal graph for free. Don't drop them, don't reuse them loosely.
- **Carry semantic metadata** on every event via the `semantic` block — a controlled
  vocabulary that maps domain concepts to ontology terms:

  ```python
  class SemanticMeta(BaseModel):
      entity_type: str        # e.g. "PaymentInstrument", "SettlementInstruction"
      ontology_terms: list[str]  # FIBO IRIs/labels this event maps to
      glossary_ref: str | None   # link into docs/ontology.md
  ```

- **Don't bleed query/presentation concerns into the write side.** Read models and
  embeddings are built by *projection consumers* on the read side, never baked into producers.
- **Maintain `docs/ontology.md`** as the human source of truth for the FIBO mapping; the
  `semantic` block references it.

The single most expensive mistake here is shipping events that are thin, untyped, or
mutable. If an event would be hard to reason about in two years, fix it before it ships.

---

## 11. Definition of done

A change is done when:
- [ ] New behavior is covered by tests (unit + contract; integration if it crosses Kafka).
- [ ] `make schema-check` passes (no breaking schema changes without a version bump).
- [ ] Any new consumer is idempotent.
- [ ] Any new emission goes through the outbox, not a direct publish.
- [ ] Migrations are included and reversible.
- [ ] `docs/events.md` is updated for any new/changed event.
- [ ] `make lint` (ruff + mypy --strict) is clean.

---

## 12. Guardrails — never do these

- ❌ Publish to Kafka directly from a request handler (use the outbox).
- ❌ `UPDATE` or `DELETE` ledger events, or any event already on a topic.
- ❌ Introduce synchronous service-to-service calls for lifecycle transitions.
- ❌ Put an untyped `dict` on a topic — every payload is a `contracts` model.
- ❌ Make a backward-incompatible schema change without a `schema_version` bump.
- ❌ Strip `correlation_id` / `causation_id` / `semantic` to "simplify" an event.
- ❌ Commit secrets. Config and credentials come from env only (and from Secrets Manager
  on AWS later). Never hardcode connection strings or keys.
- ❌ Assume host specifics — services must run unchanged in Compose and on ECS/EKS.

---

## 13. How to work in this repo (for the agent)

- Start from `docs/architecture.md` and `docs/events.md` to orient before touching code.
- When adding a feature, trace it through the lifecycle in §2 first — decide which service
  owns the transition and which event it emits *before* writing code.
- Prefer small, vertical slices: model in `contracts` → outbox emit → idempotent consumer →
  tests → docs. One event end-to-end beats five half-wired ones.
- When unsure between two designs, write a short ADR in `docs/adr/` rather than deciding silently.