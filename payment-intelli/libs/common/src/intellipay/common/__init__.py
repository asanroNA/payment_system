"""intelli-pay shared infrastructure helpers (CLAUDE.md §5).

The transactional outbox (write domain row + outbox row in one tx), the polling relay,
idempotent-consumer dedupe, and correlation-context propagation live here.

Note: the Kafka adapter is intentionally NOT re-exported here. Import it explicitly via
``from intellipay.common.kafka import ...`` so that merely importing this package (e.g. for
the outbox in a unit test) does not pull in FastStream/aiokafka.
"""

from intellipay.common.context import (
    correlation_scope,
    get_causation_id,
    get_correlation_id,
)
from intellipay.common.idempotency import (
    ProcessedEvent,
    already_processed,
    mark_processed,
    process_once,
)
from intellipay.common.outbox import Base, OutboxRecord, enqueue_event
from intellipay.common.relay import Producer, relay_once, run_relay

__all__ = [
    "Base",
    "OutboxRecord",
    "ProcessedEvent",
    "Producer",
    "already_processed",
    "correlation_scope",
    "enqueue_event",
    "get_causation_id",
    "get_correlation_id",
    "mark_processed",
    "process_once",
    "relay_once",
    "run_relay",
]
