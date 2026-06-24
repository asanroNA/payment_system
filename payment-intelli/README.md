# intelli-pay

Event-driven **card-payment lifecycle** platform: immutable domain events on Apache Kafka,
an append-only event-sourced ledger, FastAPI services coordinating by choreography, and an
orchestration saga at the edge. Built to support a Phase 2 semantic layer (RAG + FIBO
ontology) over the event history.

> `intelli-pay` is the current codename. The authoritative design contract is
> [CLAUDE.md](CLAUDE.md) — read it before changing anything.

## Layout (monorepo, uv workspace)

```
libs/
  contracts/   # shared, typed event/command Pydantic models — the spine
  common/      # outbox, kafka wiring, idempotency, correlation context
services/
  payment-api/ # public FastAPI edge + orchestration saga (first reference service)
infra/         # docker-compose, kafka topic defs, schema registry
docs/          # architecture, event catalog, ontology notes, ADRs
```

Code is importable under the `intellipay` namespace, e.g.
`from intellipay.contracts import PaymentInitiated`.

## Getting started

```sh
uv sync          # create the shared .venv and install all workspace members
make lint        # ruff + mypy --strict   (see note on `make` below)
make test-unit   # fast tests, no infra
```

`make` is not installed on Windows by default — install it once with
`winget install ezwinports.make`, or run the wrapped `uv run ...` commands directly.
See [Makefile](Makefile) and CLAUDE.md §7 for the full command interface.

## Build status

Built in small, reviewable vertical slices (CLAUDE.md "Working mode").

- [x] Slice 0 — repo skeleton, uv workspace, tooling, Makefile interface
- [x] Slice 1 — `libs/contracts`: `EventEnvelope`, `SemanticMeta`, `PaymentInitiated`
- [x] Slice 2a — `libs/common`: transactional outbox + polling relay
- [x] Slice 2b — `libs/common`: kafka wiring, idempotency dedupe, correlation context
- [x] Slice 3 — `infra/docker-compose.yml`: kafka (KRaft), postgres, registry, ui
- [ ] Slice 4 — `payment-api` end-to-end outbox → kafka → idempotent consumer
