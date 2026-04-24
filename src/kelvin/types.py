"""Core types used across Kelvin."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PerturbationKind = Literal[
    # v0.2 families
    "reorder", "pad_length", "pad_content", "swap",
    # v0.3 Pillar 2: counterfactual-controlled swap on governing rules
    "swap_condition",
    # v0.3 Pillar 3: presentation-layer invariance probes
    "whitespace_jitter", "punctuation_normalize", "bullet_reformat",
    "non_governing_duplication",
    # v0.3 Pillar 3: mechanical sensitivity probes
    "numeric_magnitude", "comparator_flip", "polarity_flip",
    # v0.3 Pillar 3: rule-based rhetorical invariance probes
    # (structural constraints, not labeling-validated)
    "hedge_injection", "politeness_injection",
    "discourse_marker_injection", "meta_commentary_injection",
]


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
    # Pillar 2: swap_condition perturbations, keyed by governing type.
    # Parallel structure to swaps_by_type; aggregator decomposes raw swap
    # sensitivity into Rule_Effect (Sens(swap_condition)) + Content_Effect
    # (Sens(swap_content) - Sens(swap_condition)).
    swap_conditions_by_type: dict[str, list[ScoredPerturbation]] = field(
        default_factory=dict
    )
    # Pillar 3 presentation-layer invariance families: decisions must not
    # move on whitespace/punctuation/bullet/duplication changes.
    whitespace_jitter: list[ScoredPerturbation] = field(default_factory=list)
    punctuation_normalize: list[ScoredPerturbation] = field(default_factory=list)
    bullet_reformat: list[ScoredPerturbation] = field(default_factory=list)
    non_governing_duplication: list[ScoredPerturbation] = field(default_factory=list)
    # Pillar 3 mechanical sensitivity families: decisions should move on
    # targeted numeric/comparator/polarity edits inside governing sections.
    numeric_magnitude: list[ScoredPerturbation] = field(default_factory=list)
    comparator_flip: list[ScoredPerturbation] = field(default_factory=list)
    polarity_flip: list[ScoredPerturbation] = field(default_factory=list)
    # Pillar 3 rule-based rhetorical invariance families: hedge/politeness/
    # discourse-marker/meta-commentary insertions with structural constraints.
    # Pooled into a single list because they're dispatched and aggregated
    # together — per-family breakdown available from sp.perturbation.kind.
    rhetorical: list[ScoredPerturbation] = field(default_factory=list)
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
        # Inter-slot (v0.2) + intra-slot presentation-layer (v0.3 Pillar 3)
        # are combined into the single aggregate invariance pool. A pipeline
        # that's supposed to be invariant under any of these probes is also
        # supposed to be invariant under all of them; the aggregate uses all
        # contributions.
        return [
            sp.distance
            for sp in (
                *self.reorder,
                *self.pad_length,
                *self.pad_content,
                *self.whitespace_jitter,
                *self.punctuation_normalize,
                *self.bullet_reformat,
                *self.non_governing_duplication,
                *self.rhetorical,
            )
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

    @property
    def swap_condition_distances(self) -> list[float]:
        """Rule_Effect approximation — distances from counterfactual-
        controlled swaps, aggregated across all governing types."""
        return [
            sp.distance
            for swaps in self.swap_conditions_by_type.values()
            for sp in swaps
            if sp.distance is not None
        ]

    @property
    def mechanical_sensitivity_distances(self) -> list[float]:
        """Mechanical sensitivity perturbations (Pillar 3): numeric,
        comparator, polarity edits inside governing sections."""
        return [
            sp.distance
            for sp in (
                *self.numeric_magnitude,
                *self.comparator_flip,
                *self.polarity_flip,
            )
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
    # Pillar 2 (v0.3): counterfactual-controlled swap decomposition.
    # sensitivity_content is Sens(swap) — same as v0.2's "sensitivity"
    # aggregate, repeated here for symmetry with sensitivity_condition.
    # sensitivity_condition is Sens(swap_condition) and approximates
    # Rule_Effect. content_effect = sensitivity_content -
    # sensitivity_condition (Content_Effect, may be negative with noise;
    # clamped to 0 for display). All three are None when counterfactual
    # swap is disabled or no swap_condition perturbations produced
    # contributing distances.
    sensitivity_content: float | None = None
    sensitivity_content_sample: int = 0
    sensitivity_condition: float | None = None
    sensitivity_condition_sample: int = 0
    content_effect: float | None = None
    swap_condition_clean_parse_rate: float | None = None
    # Pillar 3 (v0.3): mechanical sensitivity aggregate. Distinct from
    # swap-based sensitivity because the perturbations target numeric /
    # comparator / polarity tokens directly, not governing-unit swaps.
    mechanical_sensitivity: float | None = None
    mechanical_sensitivity_sample: int = 0
    warnings: list[str] = field(default_factory=list)
    caps: list[str] = field(default_factory=list)
