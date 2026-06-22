# ADR 0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-06-22

## Context

CLAUDE.md (§13) asks that non-trivial design choices be written down rather than decided
silently. We need a lightweight, durable place for them.

## Decision

Use Architecture Decision Records (ADRs) in `docs/adr/`, numbered sequentially. Each ADR
captures Context, Decision, and Consequences. Decisions deferred during the foundation
slices (e.g. schema registry choice, Debezium swap-in) will each get their own ADR when
they are made.

## Consequences

The reasoning behind the system is reviewable and survives turnover; "why is it like this?"
has a written answer instead of living only in chat history.
