"""Tests for correlation-context propagation (CLAUDE.md §6, §10)."""

from uuid import uuid4

from intellipay.common.context import (
    correlation_scope,
    get_causation_id,
    get_correlation_id,
)


def test_no_scope_returns_none() -> None:
    assert get_correlation_id() is None
    assert get_causation_id() is None


def test_scope_binds_then_restores() -> None:
    corr = uuid4()
    caus = uuid4()
    with correlation_scope(correlation_id=corr, causation_id=caus):
        assert get_correlation_id() == corr
        assert get_causation_id() == caus
    # Restored to the prior (empty) state on exit — no leakage.
    assert get_correlation_id() is None
    assert get_causation_id() is None


def test_causation_defaults_to_none() -> None:
    corr = uuid4()
    with correlation_scope(correlation_id=corr):
        assert get_correlation_id() == corr
        assert get_causation_id() is None


def test_nested_scopes_restore_outer_on_exit() -> None:
    outer_corr = uuid4()
    inner_corr = uuid4()
    inner_caus = uuid4()
    with correlation_scope(correlation_id=outer_corr):
        assert get_correlation_id() == outer_corr
        with correlation_scope(correlation_id=inner_corr, causation_id=inner_caus):
            assert get_correlation_id() == inner_corr
            assert get_causation_id() == inner_caus
        # Inner unwound; outer values are back.
        assert get_correlation_id() == outer_corr
        assert get_causation_id() is None
