# Architecture

Start here to orient before touching code (CLAUDE.md §13).

The canonical design lives in [CLAUDE.md](../CLAUDE.md): the lifecycle state machine (§2),
the core principles — Kafka-only inter-service events, append-only ledger, transactional
outbox, typed contracts, idempotent consumers (§3) — and the repository layout (§5).

This document will expand as services land. For now it is a pointer; the contract is law.
