"""Core types used across Kelvin."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PerturbationKind = Literal["reorder", "pad_length", "pad_content", "swap"]


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


@dataclass
class ScoredPerturbation:
    """A perturbation after the pipeline ran and the scorer looked at it."""

    perturbation: Perturbation
    invocation: InvocationResult
    distance: float | None               # None when the invocation failed


@dataclass
class CaseScores:
    """Per-case scoring rollup."""

    case_name: str
    reorder: list[ScoredPerturbation] = field(default_factory=list)
    # Pad split (v0.2): pad_length probes presentation-length robustness,
    # pad_content probes distractor-content robustness. Both count as
    # invariance perturbations.
    pad_length: list[ScoredPerturbation] = field(default_factory=list)
    pad_content: list[ScoredPerturbation] = field(default_factory=list)
    swaps_by_type: dict[str, list[ScoredPerturbation]] = field(default_factory=dict)
    baseline_ok: bool = True
    baseline_error: str | None = None
    baseline_decision: Any = None
    # Dry-run: perturbation inputs were generated but the pipeline was
    # never invoked. baseline_ok stays False (no decision value produced)
    # but this flag distinguishes dry-run from real failures.
    dry_run: bool = False
    # Pillar 1 (v0.3): baseline replay decisions collected when
    # noise_floor.enabled is True. `baseline_replays` includes the
    # canonical baseline as the first entry (N total for N replications).
    # `noise_floor_sigma_c` is the mean pairwise distance across replays
    # — the per-case stochasticity. Both are None when noise floor is
    # disabled or replays couldn't complete.
    baseline_replays: list[Any] = field(default_factory=list)
    noise_floor_sigma_c: float | None = None
    warnings: list[str] = field(default_factory=list)
    caps: list[str] = field(default_factory=list)

    @property
    def invariance_distances(self) -> list[float]:
        return [
            sp.distance
            for sp in (*self.reorder, *self.pad_length, *self.pad_content)
            if sp.distance is not None
        ]

    @property
    def swap_distances(self) -> list[float]:
        return [
            sp.distance
            for swaps in self.swaps_by_type.values()
            for sp in swaps
            if sp.distance is not None
        ]


@dataclass
class RunScores:
    """Cross-case aggregate."""

    cases: list[CaseScores]
    seed: int
    invariance: float | None
    invariance_sample: int
    sensitivity: float | None
    sensitivity_sample: int
    # K = (1 - invariance) + (1 - sensitivity), range [0, 2], lower = more anchored.
    # None if either component is None (no contributing perturbations).
    kelvin_score: float | None
    sensitivity_by_type: dict[str, tuple[float, int]]   # {type: (mean, sample)}
    governing_types: list[str]
    # True when the corpus has exactly one case: pad_content and swap cannot
    # run (no peers). Surfaced in the report and as a terminal banner so
    # users don't silently get a partial run.
    single_case_run: bool = False
    # True when the run was invoked with --dry-run: perturbation inputs
    # are generated but the pipeline is never invoked. All distances are
    # null; scores are informational only.
    dry_run: bool = False
    # Pillar 1 (v0.3): noise-floor calibration. `noise_floor_eta` is the
    # mean per-case stochasticity across cases; calibrated scores
    # normalize the raw signals by subtracting η and rescaling. All are
    # None when noise floor is disabled or insufficient replay data
    # exists. Calibrated K can also be None when η >= 1 - Inv_raw
    # (stochasticity exceeds the invariance signal — unmeasurable).
    noise_floor_eta: float | None = None
    invariance_calibrated: float | None = None
    sensitivity_calibrated: float | None = None
    kelvin_score_calibrated: float | None = None
    warnings: list[str] = field(default_factory=list)
    caps: list[str] = field(default_factory=list)
