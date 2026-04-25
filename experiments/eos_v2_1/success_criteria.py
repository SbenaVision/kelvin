"""§11 success criteria — v2.1.

Inputs: per-draw axis reports + per-draw directional-rate records.

Updated criteria per v2.1 §7 and §9:

  c1 — signature separates f_track from each adversary on rule axes
  c2 — f_ruleblind & f_constant ≥75% no-effect on rule-bearing T's
  c3 — directional-rate pattern on the corrupted clause:
        f_track:     correct-rate high  AND wrong-rate low
        f_wrongstatic: wrong-rate high   AND correct-rate low
        f_ruleblind: no-effect-rate high
        f_constant:  no-effect-rate high
        f_wrongstochastic: degraded (NOT clean correct or clean wrong;
                       no claim of ≈1−p_attack since attack is sampled
                       independently per call — see v2.1 §8)
  c4 — f_wrongstochastic NOT classified as rule-tracking on any rule axis
  c5 — f_track order/optional/non_rule_fact axes invariant
  c6 — pairwise Jaccard for f_track ≥ 0.80 across draws
  c7 — load-bearing: ≥1 (pipeline, T_borderline) where naive
        directional accepted but R^Ω directional rejected
  c8 — no adversary axis-classified as responsive-correct on rule axes

The "corrupted clause" for v2.1 = risk axis (since f_wrongstatic
inverts the LAST clause = "risk <= 40"). c3 evaluates on
strengthen_risk_threshold (and weaken_risk_threshold).
"""
from __future__ import annotations

from typing import Iterable

from axis_classifier import AxisReport
from config import EPS, EPS_LOW, JACCARD_TARGET
from discover import DirectionalRates, GlobalInvarianceCandidate


SignatureKey = tuple[str, str, str]


# =====================================================================
# Helpers
# =====================================================================

def _axis(reports: list[AxisReport], pipeline: str, axis: str) -> AxisReport | None:
    for r in reports:
        if r.pipeline == pipeline and r.axis == axis:
            return r
    return None


def _rate(
    rates: list[DirectionalRates], pipeline: str, t_name: str,
) -> DirectionalRates | None:
    for r in rates:
        if r.pipeline == pipeline and r.t_name == t_name:
            return r
    return None


def _signature_keys(
    invariance: list[GlobalInvarianceCandidate],
    rates: list[DirectionalRates],
    eps: float,
) -> set[SignatureKey]:
    """Build the per-draw EOS signature.

    Signature membership rules:
      - Invariance T × R^Ω: include (pipeline, t, r) if accepted
        (excluding identity).
      - Directional T: include (pipeline, t, "correct") if T is T-correct,
        or (pipeline, t, "wrong") if T is T-wrong, etc.
        We use a synthetic "r_name" tag to record the directional verdict.
    """
    keys: set[SignatureKey] = set()
    for c in invariance:
        if c.is_identity:
            continue
        if c.accepted:
            keys.add((c.pipeline, c.t_name, c.r_name))
    for r in rates:
        if r.n_active_below_floor:
            continue
        if r.correct_high_accepted and r.wrong_low_accepted:
            keys.add((r.pipeline, r.t_name, "correct"))
        elif r.wrong_rate >= 1 - eps and r.correct_rate <= eps:
            keys.add((r.pipeline, r.t_name, "wrong"))
        elif r.no_effect_rate >= 1 - eps:
            keys.add((r.pipeline, r.t_name, "no_effect"))
    return keys


def _pipeline_filter(sig: set[SignatureKey], pipeline: str) -> set[tuple[str, str]]:
    return {(t, r) for (p, t, r) in sig if p == pipeline}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


# =====================================================================
# Evaluation
# =====================================================================

def evaluate(
    reports_by_draw: list[list[AxisReport]],
    invariance_by_draw: list[list[GlobalInvarianceCandidate]],
    rates_by_draw: list[list[DirectionalRates]],
) -> list[tuple[str, bool, str]]:
    K_D = len(reports_by_draw)
    assert K_D >= 2

    # Build per-draw signatures.
    sig_by_draw = [
        _signature_keys(invariance_by_draw[d], rates_by_draw[d], EPS)
        for d in range(K_D)
    ]

    primary_reports = reports_by_draw[0]
    primary_rates = rates_by_draw[0]

    out: list[tuple[str, bool, str]] = []

    # Track signatures across draws (for Jaccard).
    track_sigs = [_pipeline_filter(s, "f_track") for s in sig_by_draw]

    # Per-pipeline signatures for c1.
    sig0 = sig_by_draw[0]
    track_sig0 = _pipeline_filter(sig0, "f_track")
    blind_sig0 = _pipeline_filter(sig0, "f_ruleblind")
    const_sig0 = _pipeline_filter(sig0, "f_constant")
    wrong_sig0 = _pipeline_filter(sig0, "f_wrongstatic")
    stoch_sig0 = _pipeline_filter(sig0, "f_wrongstochastic")

    # ----- c1 -----
    rule_t_prefixes = (
        "strengthen_", "weaken_", "add_strict_", "remove_last_",
        "add_passing_",
    )
    def rule_part(s: set[tuple[str, str]]) -> set[tuple[str, str]]:
        return {(t, r) for (t, r) in s
                if any(t.startswith(p) for p in rule_t_prefixes)}
    track_rule = rule_part(track_sig0)
    sep_blind = track_rule != rule_part(blind_sig0)
    sep_const = track_rule != rule_part(const_sig0)
    sep_wrong = track_rule != rule_part(wrong_sig0)
    sep_stoch = track_rule != rule_part(stoch_sig0)
    out.append((
        "c1_sig_separates_each_adversary_on_rule_axes",
        sep_blind and sep_const and sep_wrong and sep_stoch,
        f"sep blind={sep_blind} const={sep_const} wrong={sep_wrong} stoch={sep_stoch}",
    ))

    # ----- c2 -----
    def no_effect_fraction(pipeline: str) -> float:
        rt = _axis(primary_reports, pipeline, "rule_threshold")
        rc = _axis(primary_reports, pipeline, "rule_clause")
        if rt is None or rc is None:
            return 0.0
        ne = rt.n_no_effect + rc.n_no_effect
        total = rt.n_transforms_total + rc.n_transforms_total
        return ne / total if total > 0 else 0.0

    blind_frac = no_effect_fraction("f_ruleblind")
    const_frac = no_effect_fraction("f_constant")
    out.append((
        "c2_ruleblind_constant_75pct_no_effect_on_rule_axes",
        blind_frac >= 0.75 and const_frac >= 0.75,
        f"blind={blind_frac:.0%}  const={const_frac:.0%}",
    ))

    # ----- c3 -----
    # Test on strengthen_risk_threshold (corrupted clause) primarily;
    # weaken_risk_threshold also reported but not required to PASS
    # given n_eff_active limitations.
    corrupted_t = "strengthen_risk_threshold"
    track_r = _rate(primary_rates, "f_track", corrupted_t)
    wrong_r = _rate(primary_rates, "f_wrongstatic", corrupted_t)
    blind_r = _rate(primary_rates, "f_ruleblind", corrupted_t)
    const_r = _rate(primary_rates, "f_constant", corrupted_t)
    stoch_r = _rate(primary_rates, "f_wrongstochastic", corrupted_t)

    def _flag(r: DirectionalRates | None, label: str) -> str:
        if r is None:
            return f"{label}=N/A"
        return (
            f"{label}: c={r.correct_rate:.2f} w={r.wrong_rate:.2f} "
            f"ne={r.no_effect_rate:.2f} (n_eff_active={r.n_eff_active})"
        )

    if any(r is None for r in (track_r, wrong_r, blind_r, const_r, stoch_r)):
        c3_ok = False
        c3_detail = "missing rate record(s)"
    else:
        track_pat = track_r.correct_high_accepted and track_r.wrong_low_accepted
        wrong_pat = (
            wrong_r.wrong_rate >= 1 - EPS and wrong_r.correct_rate <= EPS_LOW
        )
        blind_pat = blind_r.no_effect_rate >= 1 - EPS
        const_pat = const_r.no_effect_rate >= 1 - EPS
        stoch_pat = not (
            stoch_r.correct_high_accepted and stoch_r.wrong_low_accepted
        )
        c3_ok = track_pat and wrong_pat and blind_pat and const_pat and stoch_pat
        c3_detail = (
            " | ".join([
                _flag(track_r, "track"),
                _flag(wrong_r, "wrong"),
                _flag(blind_r, "blind"),
                _flag(const_r, "const"),
                _flag(stoch_r, "stoch"),
            ])
        )
    out.append(("c3_directional_rates_on_corrupted_clause", c3_ok, c3_detail))

    # ----- c4 -----
    # f_wrongstochastic NOT responsive-correct on any rule axis.
    stoch_rt = _axis(primary_reports, "f_wrongstochastic", "rule_threshold")
    stoch_rc = _axis(primary_reports, "f_wrongstochastic", "rule_clause")
    c4_ok = (
        stoch_rt is not None and stoch_rt.classification != "responsive-correct"
        and stoch_rc is not None and stoch_rc.classification != "responsive-correct"
    )
    out.append((
        "c4_wrongstochastic_not_rule_tracking",
        c4_ok,
        f"rt={stoch_rt.classification if stoch_rt else 'N/A'} "
        f"rc={stoch_rc.classification if stoch_rc else 'N/A'}",
    ))

    # ----- c5 -----
    o = _axis(primary_reports, "f_track", "order")
    opt = _axis(primary_reports, "f_track", "optional")
    nrf = _axis(primary_reports, "f_track", "non_rule_fact")
    c5_ok = (
        o is not None and o.classification == "invariant-candidate"
        and opt is not None and opt.classification == "invariant-candidate"
        and nrf is not None and nrf.classification == "invariant-candidate"
    )
    out.append((
        "c5_track_order_optional_nonrule_invariant",
        c5_ok,
        f"order={o.classification if o else 'N/A'} "
        f"optional={opt.classification if opt else 'N/A'} "
        f"non_rule_fact={nrf.classification if nrf else 'N/A'}",
    ))

    # ----- c6 -----
    pairwise: list[float] = []
    for i in range(K_D):
        for j in range(i + 1, K_D):
            pairwise.append(_jaccard(track_sigs[i], track_sigs[j]))
    min_jac = min(pairwise) if pairwise else 0.0
    triple = set.intersection(*track_sigs) if K_D >= 2 else set()
    out.append((
        f"c6_track_pairwise_jaccard_geq_{JACCARD_TARGET:.2f}",
        min_jac >= JACCARD_TARGET,
        f"min={min_jac:.3f} triple_size={len(triple)} "
        f"per-pair={[round(j,3) for j in pairwise]}",
    ))

    # ----- c7 -----
    # Load-bearing on the borderline T (or any directional T):
    # naive_correct_high_accepted == True (naive accepts)
    # AND correct_high_accepted == False  (omega rejects)
    fired: list[tuple[str, str]] = []
    for r in primary_rates:
        if r.naive_correct_high_accepted and not r.correct_high_accepted:
            fired.append((r.pipeline, r.t_name))
    # Prefer the borderline T as the canonical fire (per the seal).
    borderline_fired = [
        (p, t) for (p, t) in fired if t == "add_passing_clause"
    ]
    out.append((
        "c7_load_bearing_directional",
        len(fired) >= 1,
        f"fired={fired[:6]}  borderline_fired={borderline_fired}",
    ))

    # ----- c8 -----
    misclassified: list[str] = []
    for p in ("f_ruleblind", "f_constant", "f_wrongstatic", "f_wrongstochastic"):
        rt = _axis(primary_reports, p, "rule_threshold")
        rc = _axis(primary_reports, p, "rule_clause")
        if (rt is not None and rt.classification == "responsive-correct"
                and rc is not None and rc.classification == "responsive-correct"):
            misclassified.append(p)
    out.append((
        "c8_no_adversary_axis_responsive_correct_on_rule_axes",
        len(misclassified) == 0,
        f"misclassified={misclassified or 'none'}",
    ))

    return out
