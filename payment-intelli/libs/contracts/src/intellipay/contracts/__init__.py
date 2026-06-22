"""intelli-pay event & command contracts — the shared spine (CLAUDE.md §3.4, §5).

Every Kafka payload on every topic is a typed model defined here; no ad-hoc dicts.
The base ``EventEnvelope``, ``SemanticMeta``, and the first concrete event land in Slice 1.
"""
