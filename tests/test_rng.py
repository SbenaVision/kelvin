"""Regression tests for the seed-derivation helper.

These lock in stability of `rng_for` across Python versions and
PYTHONHASHSEED settings. If someone accidentally reintroduces the built-in
`hash()` (which is not stable), these goldens will fail.
"""

from __future__ import annotations

from kelvin.perturbations import rng_for


def test_same_inputs_produce_same_sequence() -> None:
    a = rng_for(0, "reorder", "acme")
    b = rng_for(0, "reorder", "acme")
    assert [a.random() for _ in range(5)] == [b.random() for _ in range(5)]


def test_different_seeds_produce_different_sequences() -> None:
    a = rng_for(0, "reorder", "acme")
    b = rng_for(1, "reorder", "acme")
    assert [a.random() for _ in range(5)] != [b.random() for _ in range(5)]


def test_different_components_produce_different_sequences() -> None:
    a = rng_for(0, "reorder", "acme")
    b = rng_for(0, "swap", "acme")
    c = rng_for(0, "reorder", "zeta")
    seq_a = [a.random() for _ in range(5)]
    seq_b = [b.random() for _ in range(5)]
    seq_c = [c.random() for _ in range(5)]
    assert seq_a != seq_b
    assert seq_a != seq_c
    assert seq_b != seq_c


def test_golden_sequence_for_regression() -> None:
    """Golden values — will not change unless the derivation does.

    Locked in so that a change to `rng_for` surfaces visibly in the diff.
    If you need to intentionally change the derivation, regenerate these
    values along with the change.
    """
    rng = rng_for(0, "reorder", "acme")
    samples = [rng.randint(0, 1_000_000) for _ in range(3)]
    assert samples == [645899, 708847, 957792]
