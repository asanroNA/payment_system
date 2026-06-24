"""Correlation/causation propagation via contextvars (CLAUDE.md §6, §10).

Lineage is what turns the event history into a causal graph (and makes Phase 2 cheap).
Threading ``correlation_id``/``causation_id`` through every function by hand is error-prone,
so we stash them in contextvars: a consumer opens a scope from the incoming event's headers,
and any event it emits within that scope reads the same ``correlation_id`` and sets its
``causation_id`` to the event being reacted to — no extra parameters, no dropped lineage.

Contextvars (not globals) so this is safe across concurrent async tasks: each task sees its
own values.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

_correlation_id: ContextVar[UUID | None] = ContextVar("correlation_id", default=None)
_causation_id: ContextVar[UUID | None] = ContextVar("causation_id", default=None)


def get_correlation_id() -> UUID | None:
    return _correlation_id.get()


def get_causation_id() -> UUID | None:
    return _causation_id.get()


@contextmanager
def correlation_scope(*, correlation_id: UUID, causation_id: UUID | None = None) -> Iterator[None]:
    """Bind lineage for the duration of the block, restoring the prior values on exit.

    Tokens + ``reset`` (rather than set-then-clear) so nested scopes restore correctly and a
    scope never leaks its values to whatever ran before it.
    """
    corr_token = _correlation_id.set(correlation_id)
    caus_token = _causation_id.set(causation_id)
    try:
        yield
    finally:
        _correlation_id.reset(corr_token)
        _causation_id.reset(caus_token)
