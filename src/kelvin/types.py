"""Core types used across Kelvin."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PerturbationKind = Literal["reorder", "pad", "swap"]


@dataclass(frozen=True)
class Unit:
    """A typed content unit parsed from a case's markdown."""

    type: str           # normalized header (lowercase, whitespace → underscore)
    content: str        # body text between this header and the next
    raw_header: str     # original header as it appeared in the source
    index: int          # zero-based position in the original case


@dataclass
class Case:
    """A parsed case — preamble plus typed units."""

    name: str           # filename stem
    source_path: Path
    preamble: str       # text before the first header; never perturbed
    units: list[Unit]

    def units_of_type(self, type_: str) -> list[Unit]:
        return [u for u in self.units if u.type == type_]


@dataclass
class Perturbation:
    """A single generated perturbation ready to write to disk and invoke."""

    case_name: str
    kind: PerturbationKind
    variant_id: str             # e.g. "reorder-01", "swap-gate_rule-02"
    rendered_markdown: str
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerturbationBatch:
    """Output of a generator for a single case."""

    perturbations: list[Perturbation]
    warnings: list[str] = field(default_factory=list)
    caps: list[str] = field(default_factory=list)


@dataclass
class InvocationResult:
    """Outcome of a single pipeline shell invocation (baseline or perturbation)."""

    ok: bool
    exit_code: int | None
    input_path: Path
    output_path: Path
    parsed_output: dict[str, Any] | None = None
    decision_value: Any = None
    error: str | None = None             # populated when ok is False
    stderr_tail: str | None = None
