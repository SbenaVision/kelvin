"""Distance function + aggregation.

Distance is the pluggable piece (Protocol). v1 ships `DefaultScorer` matching
the spec:

    enum / string  → 0 if equal else 1    (exact match — case- and
                                            whitespace-sensitive)
    numeric        → min(1, |a-b| / max(|a|, |b|, 1))
    other          → raises; only scalar decision fields are supported in v1
"""

from __future__ import annotations

from typing import Any, Protocol


class DecisionFieldTypeError(ValueError):
    """Raised when the decision field is not a supported scalar."""


class Scorer(Protocol):
    """Pluggable distance function on the declared decision field."""

    def distance(self, baseline: Any, perturbed: Any) -> float: ...


class DefaultScorer:
    """Spec-faithful scorer. Implemented in PR 2."""

    def distance(self, baseline: Any, perturbed: Any) -> float:
        raise NotImplementedError("default scorer arrives in PR 2")
