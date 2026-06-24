"""Kafka wiring via FastStream (CLAUDE.md §4).

Supplies the real ``Producer`` the relay publishes through, plus a broker factory. FastStream
gives typed producers/consumers and AsyncAPI docs; we'd drop to confluent-kafka only if it
ever proves too high-level (§4). This module is thin on purpose — its real exercise is the
Slice 4 testcontainers integration test, not a unit test against a mock broker.
"""

from faststream.kafka import KafkaBroker


def make_broker(bootstrap_servers: str) -> KafkaBroker:
    """Create a broker pointed at ``bootstrap_servers``.

    Lifecycle (connect/start/stop) is the caller's responsibility — a service starts it on
    app startup; the relay just borrows it to publish. Config comes from env (§12), never
    hardcoded, so the bootstrap string is injected, not baked in.
    """
    return KafkaBroker(bootstrap_servers)


class KafkaProducerAdapter:
    """Adapts a FastStream ``KafkaBroker`` to the relay's ``Producer`` protocol (relay.py).

    The relay stays ignorant of FastStream — it only needs *something* it can ``.publish``
    on. Payload and key are sent as raw UTF-8 bytes (not re-serialized), so the exact bytes
    ``model_dump_json()`` produced land on the wire, consistent with the ``content-type``
    header. Keying by ``partition_key`` is what preserves per-aggregate ordering (§6).
    """

    def __init__(self, broker: KafkaBroker) -> None:
        self._broker = broker

    async def publish(self, *, topic: str, key: str, value: str, headers: dict[str, str]) -> None:
        await self._broker.publish(
            value.encode("utf-8"),
            topic=topic,
            key=key.encode("utf-8"),
            headers=headers,
        )
