"""intelli-pay shared infrastructure helpers (CLAUDE.md §5).

The transactional outbox (write domain row + outbox row in one tx), the polling relay,
Kafka wiring, idempotent-consumer dedupe, and correlation-context propagation live here.
Populated in Slice 2.
"""
