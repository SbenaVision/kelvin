"""§11 success criteria as code (sealed).

Inputs:
  reports_by_draw:    list[list[AxisReport]] — K_D draws, each is the
                      per-pipeline per-axis classification on that draw
                      (using R^Ω only, after subsumption + n_eff filter).
  signatures_by_draw: list[set[(pipeline, t, r)]] — accepted (T, R^Ω)
                      pairs per draw.
  load_bearing_fired: bool — True if at least one (pipeline, T, R)
                      naive-accepted but R^Ω-rejected.

Returns: list[(name, ok)] — the eight criteria.
"""
from __future__ import annotations

from axis_classifier import AxisReport
from config import JACCARD_TARGET


SignatureKey = tuple[str, str, str]


def _axis(reports: list[AxisReport], pipeline: str, axis: str) -> AxisReport | None:
    for r in reports:
        if r.pipeline == pipeline and r.axis == axis:
            return r
    return None


def _pipeline_signature(sig: set[SignatureKey], pipeline: str) -> set[tuple[str, str]]:
    return {(t, r) for (p, t, r) in sig if p == pipeline}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def evaluate(
    reports_by_draw: list[list[AxisReport]],
    signatures_by_draw: list[set[SignatureKey]],
    load_bearing_fired: bool,
) -> list[tuple[str, bool, str]]:
    """Returns (name, ok, detail) for each criterion."""
    K_D = len(signatures_by_draw)
    assert K_D >= 2

    # Use draw 0's reports as the "primary" axis classifier results.
    primary_reports = reports_by_draw[0]
    track_sig_0 = _pipeline_signature(signatures_by_draw[0], "f_track")
    blind_sig_0 = _pipeline_signature(signatures_by_draw[0], "f_ruleblind")
    const_sig_0 = _pipeline_signature(signatures_by_draw[0], "f_constant")
    wrong_sig_0 = _pipeline_signature(signatures_by_draw[0], "f_wrongstatic")
    stoch_sig_0 = _pipeline_signature(signatures_by_draw[0], "f_wrongstochastic")

    track_signatures = [
        _pipeline_signature(s, "f_track") for s in signatures_by_draw
    ]

    # Pairwise Jaccards on f_track signatures across draws.
    jaccards: list[float] = []
    for i in range(K_D):
        for j in range(i + 1, K_D):
            jaccards.append(_jaccard(track_signatures[i], track_signatures[j]))
    min_jaccard = min(jaccards) if jaccards else 0.0

    # Triple intersection (informational).
    triple = set.intersection(*track_signatures) if K_D >= 2 else set()

    out: list[tuple[str, bool, str]] = []

    # Criterion 1: Σ(f_track) separates from each adversary on rule-bearing axes
    rule_axes = ("rule_threshold", "rule_clause")
    track_rule = {(t, r) for (t, r) in track_sig_0
                  if any(t.startswith(prefix)
                         for prefix in ("strengthen_", "weaken_", "add_strict_", "remove_last_"))}
    blind_rule = {(t, r) for (t, r) in blind_sig_0
                  if any(t.startswith(prefix)
                         for prefix in ("strengthen_", "weaken_", "add_strict_", "remove_last_"))}
    const_rule = {(t, r) for (t, r) in const_sig_0
                  if any(t.startswith(prefix)
                         for prefix in ("strengthen_", "weaken_", "add_strict_", "remove_last_"))}
    wrong_rule = {(t, r) for (t, r) in wrong_sig_0
                  if any(t.startswith(prefix)
                         for prefix in ("strengthen_", "weaken_", "add_strict_", "remove_last_"))}
    stoch_rule = {(t, r) for (t, r) in stoch_sig_0
                  if any(t.startswith(prefix)
                         for prefix in ("strengthen_", "weaken_", "add_strict_", "remove_last_"))}

    sep_track_blind = track_rule != blind_rule
    sep_track_const = track_rule != const_rule
    sep_track_wrong = track_rule != wrong_rule
    sep_track_stoch = track_rule != stoch_rule

    sep_all = sep_track_blind and sep_track_const and sep_track_wrong and sep_track_stoch
    out.append(("c1_sig_separates_each_adversary_on_rule_axes", sep_all,
                f"sep blind={sep_track_blind} const={sep_track_const} "
                f"wrong={sep_track_wrong} stoch={sep_track_stoch}"))

    # Criterion 2: f_ruleblind & f_constant are ignored-candidate on
    # ≥75% of rule-bearing T's.  Approximate by axis classification
    # (rule_threshold + rule_clause).
    def ignored_fraction(pipeline: str) -> float:
        rt = _axis(primary_reports, pipeline, "rule_threshold")
        rc = _axis(primary_reports, pipeline, "rule_clause")
        if rt is None or rc is None:
            return 0.0
        rt_ignored = rt.n_invariant if rt.classification == "ignored-candidate" else 0
        rc_ignored = rc.n_invariant if rc.classification == "ignored-candidate" else 0
        total = rt.n_transforms + rc.n_transforms
        return (rt_ignored + rc_ignored) / total if total > 0 else 0.0

    blind_frac = ignored_fraction("f_ruleblind")
    const_frac = ignored_fraction("f_constant")
    c2_ok = blind_frac >= 0.75 and const_frac >= 0.75
    out.append(("c2_ruleblind_constant_75pct_ignored", c2_ok,
                f"blind={blind_frac:.0%}  const={const_frac:.0%}"))

    # Criterion 3: f_wrongstatic shows wrong-direction on the corrupted clause
    wrong_rt = _axis(primary_reports, "f_wrongstatic", "rule_threshold")
    c3_ok = wrong_rt is not None and wrong_rt.classification == "responsive-wrong-direction"
    out.append(("c3_wrongstatic_wrong_direction_on_rule_threshold", c3_ok,
                f"axis={wrong_rt.classification if wrong_rt else 'N/A'} "
                f"({wrong_rt.n_wrong if wrong_rt else 0} wrong)"))

    # Criterion 4: f_wrongstochastic shows degraded rule-axis signature
    # AND is NOT classified as rule-tracking (responsive-correct on every axis).
    stoch_rt = _axis(primary_reports, "f_wrongstochastic", "rule_threshold")
    stoch_rc = _axis(primary_reports, "f_wrongstochastic", "rule_clause")
    rt_ok = stoch_rt is not None and stoch_rt.classification != "responsive-correct"
    rc_ok = stoch_rc is not None and stoch_rc.classification != "responsive-correct"
    c4_ok = rt_ok and rc_ok
    out.append(("c4_wrongstochastic_degraded_rule_axis", c4_ok,
                f"rule_threshold={stoch_rt.classification if stoch_rt else 'N/A'} "
                f"rule_clause={stoch_rc.classification if stoch_rc else 'N/A'}"))

    # Criterion 5: order + irrelevant axes invariant for f_track
    o = _axis(primary_reports, "f_track", "order")
    opt = _axis(primary_reports, "f_track", "optional")
    nrf = _axis(primary_reports, "f_track", "non_rule_fact")
    c5_ok = (
        o is not None and o.classification == "invariant-candidate"
        and opt is not None and opt.classification == "invariant-candidate"
        and nrf is not None and nrf.classification == "invariant-candidate"
    )
    out.append(("c5_track_order_optional_nonrule_invariant", c5_ok,
                f"order={o.classification if o else 'N/A'} "
                f"optional={opt.classification if opt else 'N/A'} "
                f"non_rule_fact={nrf.classification if nrf else 'N/A'}"))

    # Criterion 6: pairwise Jaccard ≥ 0.8 for f_track across all draws
    c6_ok = min_jaccard >= JACCARD_TARGET
    out.append((f"c6_track_pairwise_jaccard_geq_{JACCARD_TARGET:.2f}", c6_ok,
                f"min={min_jaccard:.3f}  triple_intersection_size={len(triple)}  "
                f"per-pair={[round(j,3) for j in jaccards]}"))

    # Criterion 7: load-bearing noise floor
    out.append(("c7_load_bearing_noise_floor", load_bearing_fired,
                f"naive accepted but R^Ω rejected on at least one (T,R,pipeline)"
                if load_bearing_fired else "no naive→omega divergence observed"))

    # Criterion 8: no adversary misclassified as rule-tracking
    def is_rule_tracking(reports: list[AxisReport], pipeline: str) -> bool:
        rt = _axis(reports, pipeline, "rule_threshold")
        rc = _axis(reports, pipeline, "rule_clause")
        return (rt is not None and rt.classification == "responsive-correct"
                and rc is not None and rc.classification == "responsive-correct")
    misclassified = [
        p for p in ("f_ruleblind", "f_constant", "f_wrongstatic", "f_wrongstochastic")
        if is_rule_tracking(primary_reports, p)
    ]
    c8_ok = len(misclassified) == 0
    out.append(("c8_no_adversary_misclassified_as_rule_tracking", c8_ok,
                f"misclassified={misclassified or 'none'}"))

    return out
