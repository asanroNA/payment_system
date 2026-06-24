"""Semantic metadata carried on every event (CLAUDE.md §10).

This is the write-side hook for the Phase 2 RAG + FIBO layer: it maps each event to a
controlled vocabulary now so the knowledge graph is cheap to build later instead of a
painful retrofit. It is intentionally small — richer mapping lives in docs/ontology.md,
referenced via ``glossary_ref``.
"""

from pydantic import BaseModel, ConfigDict


class SemanticMeta(BaseModel):
    """Ontology-mapping metadata attached to an event.

    Frozen because, like the events that carry it, it is part of the immutable historical
    record — a mutated mapping can't be trusted by a reasoning layer.
    """

    model_config = ConfigDict(frozen=True)

    entity_type: str
    """The domain entity this event is about, e.g. "Payment", "SettlementInstruction"."""

    ontology_terms: list[str]
    """FIBO IRIs/labels this event maps to. May be several; never empty in practice."""

    glossary_ref: str | None = None
    """Link into docs/ontology.md for the human-readable mapping, if one exists yet."""
