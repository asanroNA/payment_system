"""intelli-pay event & command contracts — the shared spine (CLAUDE.md §3.4, §5).

Every Kafka payload on every topic is a typed model defined here; no ad-hoc dicts. A
producer and its consumers import the SAME class, so contract drift is a type error, not a
2am incident.
"""

from intellipay.contracts.envelope import EventEnvelope
from intellipay.contracts.payments import PaymentInitiated
from intellipay.contracts.semantic import SemanticMeta

__all__ = ["EventEnvelope", "PaymentInitiated", "SemanticMeta"]
